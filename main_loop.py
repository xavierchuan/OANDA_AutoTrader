# main_loop.py  — High-Frequency AI Signal + MA/ATR risk controls
import os, time, traceback, datetime as dt
from engine.oanda_api import OandaAPI
from engine.risk import compute_atr, position_size_by_risk_eurusd, pip_size
from engine.model_infer import AISignalModel

# === 基本配置 ===
ACCESS_TOKEN = os.getenv("OANDA_TOKEN", "your_access_token_here")
ACCOUNT_ID   = os.getenv("OANDA_ACCOUNT", "your_account_id_here")
ENVIRONMENT  = os.getenv("OANDA_ENV", "practice")   # practice / live
INSTRUMENT   = os.getenv("OANDA_SYMBOL", "EUR_USD")
GRANULARITY  = os.getenv("OANDA_GRAN", "M1")        # M1 高频

# 策略参数（更灵敏）
MA_FAST, MA_SLOW = 5, 15
ATR_PERIOD       = 10
MIN_ATR          = 0.00004

# 交易与风控
SL_ATR_MULT, TP_ATR_MULT = 1.2, 1.8
RISK_PCT       = float(os.getenv("RISK_PCT", "0.005"))
UNITS_MIN_CAP  = int(os.getenv("UNITS_MIN_CAP", "100"))
MAX_SPREAD_PIPS = float(os.getenv("MAX_SPREAD_PIPS", "2.0"))
SLEEP_SEC      = int(os.getenv("SLEEP_SEC", "20"))

LOGFILE = "run.log"

def log(msg: str):
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOGFILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def _parse_order_fill(resp: dict, fallback_price: float) -> tuple[str, str]:
    """
    返回 (status, price_str)
      - status: 'FILLED' / 'PENDING' / 'CANCELED' / 'UNKNOWN'
      - price_str: 字符串化的成交/创建价格
    """
    if not isinstance(resp, dict):
        return "UNKNOWN", f"{fallback_price:.5f}"

    if "orderFillTransaction" in resp:
        return "FILLED", str(resp["orderFillTransaction"].get("price", f"{fallback_price:.5f}"))
    if "orderCancelTransaction" in resp:
        return "CANCELED", str(resp["orderCancelTransaction"].get("price", f"{fallback_price:.5f}"))
    if "orderCreateTransaction" in resp:
        return "PENDING", str(resp["orderCreateTransaction"].get("price", f"{fallback_price:.5f}"))
    # 某些情况下只有 'lastTransactionID' 等
    return "UNKNOWN", f"{fallback_price:.5f}"

def run_once(api: OandaAPI, last_done_time, ai_model: AISignalModel):
    """M1 高频：AI 产生交易信号；点差/ATR/头寸控制在本函数统一处理。"""
    last_time = None

    # === 报价 & 点差保护 ===
    px  = api.get_price(INSTRUMENT)
    bid, ask = px["bid"], px["ask"]
    mid = (bid + ask) / 2.0

    pip = pip_size(INSTRUMENT)                 # 对 EUR_USD 为 0.0001
    spread_pips = (ask - bid) / pip
    if spread_pips > MAX_SPREAD_PIPS:
        log(f"⏸️ Spread too wide: {spread_pips:.2f} pips > {MAX_SPREAD_PIPS}. Skip.")
        return last_done_time

    # === 历史K线 & 指标（供ATR与特征使用）===
    df = api.get_candles(INSTRUMENT, granularity=GRANULARITY, count=300)

    # 预先算均线，便于特征与可视化（AI内部也会做自己的特征）
    df["ma_fast"] = df["c"].rolling(MA_FAST, min_periods=MA_FAST).mean()
    df["ma_slow"] = df["c"].rolling(MA_SLOW, min_periods=MA_SLOW).mean()

    # 只用完结K线
    done = df[df["complete"]].copy()
    if len(done) < max(MA_SLOW, ATR_PERIOD) + 2:
        log("ℹ️ 数据不足（均线/ATR 尚未形成），跳过。")
        return last_done_time

    prev = done.iloc[-2]
    last = done.iloc[-1]
    last_time = last.name

    # 没有新K线就不重复判断
    if last_done_time is not None and last_time <= last_done_time:
        log(f"⏳ No new closed candle. LastDone={last_done_time}")
        return last_done_time

    # === 用 AI 模型预测信号 ===
    signal, edge = ai_model.predict_signal(done)
    log(f"[AI] signal={signal}, edge={edge:.4f}")

    if signal not in ("BUY", "SELL"):
        log("ℹ️ 无有效信号（AI 置信度不足或给出 NONE）。")
        return last_time

    # === ATR 波动率保护 ===
    atr = compute_atr(df, ATR_PERIOD)
    if atr < MIN_ATR:
        log(f"⏸️ ATR too small ({atr:.5f} < {MIN_ATR:.5f}). Skip.")
        return last_time

    # === 生成 SL/TP ===
    if signal == "BUY":
        sl_price = round(mid - SL_ATR_MULT * atr, 5)
        tp_price = round(mid + TP_ATR_MULT * atr, 5)
        units_sign = +1
    else:
        sl_price = round(mid + SL_ATR_MULT * atr, 5)
        tp_price = round(mid - TP_ATR_MULT * atr, 5)
        units_sign = -1

    log(
        f"📈 Signal: {signal} | mid={mid:.5f}, SL={sl_price:.5f}, TP={tp_price:.5f}, "
        f"ATR={atr:.5f}, spread={ask - bid:.5f}"
    )

    # === 头寸规模 ===
    summary = api.account_summary()
    nav_gbp = float(summary["NAV"])
    gbp_usd = api.mid_price("GBP_USD")

    units = position_size_by_risk_eurusd(
        nav_gbp=nav_gbp,
        risk_pct=RISK_PCT,
        entry_price=mid,
        sl_price=sl_price,
        gbp_usd=gbp_usd,
    )
    units = max(units, UNITS_MIN_CAP) * units_sign

    # === 下单（更稳健的返回解析）===
    if ENVIRONMENT == "practice":
        resp = api.market_order(INSTRUMENT, units=units, sl_price=sl_price, tp_price=tp_price)
        status, px_str = _parse_order_fill(resp, fallback_price=mid)
        if status == "FILLED":
            log(f"✅ Executed {signal} @ {px_str} | units={units}")
        elif status == "PENDING":
            log(f"🕓 Order accepted (pending fill) @ {px_str} | keys={list(resp.keys())}")
        elif status == "CANCELED":
            reason = resp.get("orderCancelTransaction", {}).get("reason", "UNKNOWN")
            log(f"❌ Order canceled: reason={reason} | @ {px_str}")
        else:
            log(f"ℹ️ Order response ambiguous: keys={list(resp.keys())} @ {px_str}")
    else:
        log("⚠️ Live 环境不自动下单。")

    return last_time

def main_loop():
    api = OandaAPI(ACCESS_TOKEN, ACCOUNT_ID, environment=ENVIRONMENT)
    # 没有模型文件也能跑（启发式）；有模型文件可通过 env 或默认路径加载
    model_path = os.getenv("AI_MODEL_PATH", "models/lgb_model.pkl")
    ai_model = AISignalModel(model_path=model_path, threshold=float(os.getenv("AI_THRESHOLD", "0.55")))
    log("🚀 Daemon started.")
    last_done_time = None

    while True:
        try:
            last_done_time = run_once(api, last_done_time, ai_model)
        except Exception as e:
            log("❌ Exception: " + repr(e))
            log(traceback.format_exc())
        time.sleep(SLEEP_SEC)

if __name__ == "__main__":
    main_loop()
