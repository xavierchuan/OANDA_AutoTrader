# main_loop.py
import os, time, traceback, datetime as dt
from engine.oanda_api import OandaAPI
from engine.risk import compute_atr, position_size_by_risk_eurusd, pip_size

# === 基本配置 ===
ACCESS_TOKEN = os.getenv("OANDA_TOKEN", "your_access_token_here")
ACCOUNT_ID   = os.getenv("OANDA_ACCOUNT", "your_account_id_here")
ENVIRONMENT  = "practice"            # 先只在 Demo
INSTRUMENT   = "EUR_USD"
GRANULARITY  = "M5"                  # 5分钟
MA_FAST, MA_SLOW = 10, 30
ATR_PERIOD   = 14
SL_ATR_MULT, TP_ATR_MULT = 1.5, 2.5
RISK_PCT     = 0.005                 # 每笔风险占净值0.5%
UNITS_MIN_CAP = 100

LOGFILE = "run.log"
SLEEP_SEC = 60                       # 每 60 秒检查一次，避免错过K线收盘


def log(msg):
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOGFILE, "a") as f:
        f.write(line + "\n")


def run_once(api, last_done_time):
    """仅在“新完成K线”出现均线交叉时下单；否则跳过。"""
    last_time = None  # ✅ 提前定义，防止未定义错误

    # 获取当前行情
    px = api.get_price(INSTRUMENT)
    bid, ask = px["bid"], px["ask"]
    mid = (bid + ask) / 2.0

    # 历史K线
    df = api.get_candles(INSTRUMENT, granularity=GRANULARITY, count=300)

    # ✅ 在完整 df 上计算均线
    df["ma_fast"] = df["c"].rolling(MA_FAST, min_periods=MA_FAST).mean()
    df["ma_slow"] = df["c"].rolling(MA_SLOW, min_periods=MA_SLOW).mean()

    # ✅ 只保留已完成的K线
    done = df[df["complete"]].copy()

    if len(done) < max(MA_SLOW, ATR_PERIOD) + 2:
        log("ℹ️ 数据不足（均线/ATR 尚未形成），跳过。")
        return last_done_time

    last = done.iloc[-1]
    prev = done.iloc[-2]
    last_time = last.name  # ✅ 在这里定义

    # 若还没有新K线完成，则跳过
    if last_done_time is not None and last_time <= last_done_time:
        log(f"⏳ No new closed candle. LastDone={last_done_time}")
        return last_done_time

    # 均线交叉信号
    signal = None
    if prev["ma_fast"] <= prev["ma_slow"] and last["ma_fast"] > last["ma_slow"]:
        signal = "BUY"
    elif prev["ma_fast"] >= prev["ma_slow"] and last["ma_fast"] < last["ma_slow"]:
        signal = "SELL"

    atr = compute_atr(df, ATR_PERIOD)

    if signal:
        pip = pip_size(INSTRUMENT)
        if signal == "BUY":
            sl_price = round(mid - SL_ATR_MULT * atr, 5)
            tp_price = round(mid + TP_ATR_MULT * atr, 5)
        else:
            sl_price = round(mid + SL_ATR_MULT * atr, 5)
            tp_price = round(mid - TP_ATR_MULT * atr, 5)

        # 账户净值（GBP）+ 汇率
        summary = api.account_summary()
        nav_gbp = float(summary["NAV"])
        gbp_usd = api.mid_price("GBP_USD")

        # 按风险计算仓位
        units = position_size_by_risk_eurusd(
            nav_gbp=nav_gbp,
            risk_pct=RISK_PCT,
            entry_price=mid,
            sl_price=sl_price,
            gbp_usd=gbp_usd,
        )
        units = max(units, UNITS_MIN_CAP)
        units = units if signal == "BUY" else -units

        if ENVIRONMENT == "practice":
            resp = api.market_order(INSTRUMENT, units=units, sl_price=sl_price, tp_price=tp_price)
            fill = resp["orderFillTransaction"]["price"]
            log(f"✅ {signal} @ {fill} | units={units} SL={sl_price} TP={tp_price} ATR={atr:.5f}")
        else:
            log("⚠️ Live 环境不自动下单。")
    else:
        log("ℹ️ 无信号（新K线已完成）。")

    return last_time  # ✅ 保证总是定义好的变量


def main_loop():
    api = OandaAPI(ACCESS_TOKEN, ACCOUNT_ID, environment=ENVIRONMENT)
    log("🚀 Daemon started.")
    last_done_time = None

    while True:
        try:
            last_done_time = run_once(api, last_done_time)
        except Exception as e:
            log("❌ Exception: " + repr(e))
            log(traceback.format_exc())
        time.sleep(SLEEP_SEC)


if __name__ == "__main__":
    main_loop()