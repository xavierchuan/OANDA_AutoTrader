# main.py
# 最小可用策略：M5 均线交叉 + ATR 风控 + 按账户净值比例自动计算仓位
# 仅在 practice（Demo）环境自动下单；请勿直接用于 live。

from engine.oanda_api import OandaAPI
from engine.risk import compute_atr, position_size_by_risk_eurusd, pip_size

# ====== 你的账户配置（先用 Demo）======
ACCESS_TOKEN = "7a5d421b37c4e2183ea0836f6c589425-801636f5d581395dd81f75689214a067"
ACCOUNT_ID   = "101-004-37523957-001"   # Demo 账户通常以 101- 开头
ENVIRONMENT  = "practice"               # 先只在 Demo 跑
INSTRUMENT   = "EUR_USD"

# ====== 策略与风控参数 ======
MA_FAST       = 10       # 快速均线
MA_SLOW       = 30       # 慢速均线
CANDLES_COUNT = 300      # 拉取K线数（要大于慢速MA）
ATR_PERIOD    = 14       # ATR 周期
SL_ATR_MULT   = 1.5      # 止损 = 1.5 * ATR
TP_ATR_MULT   = 2.5      # 止盈 = 2.5 * ATR
RISK_PCT      = 0.005    # 单笔风险 = 账户净值的 0.5%
UNITS_MIN_CAP = 100      # 最小下单单位（避免过小）

# ====== 连接 API ======
api = OandaAPI(ACCESS_TOKEN, ACCOUNT_ID, environment=ENVIRONMENT)
print("✅ Connecting to OANDA API...")

# 1) 实时报价
px = api.get_price(INSTRUMENT)
print("✅ Current Price:", px)
bid, ask = px["bid"], px["ask"]
mid = (bid + ask) / 2.0
pip = pip_size(INSTRUMENT)  # EUR_USD = 0.0001

# 2) 历史K线（M5）
df = api.get_candles(INSTRUMENT, granularity="M5", count=CANDLES_COUNT)
df["ma_fast"] = df["c"].rolling(MA_FAST).mean()
df["ma_slow"] = df["c"].rolling(MA_SLOW).mean()

# 只用“已完成”的最后两根K线判断交叉
last = df[df["complete"]].iloc[-1]
prev = df[df["complete"]].iloc[-2]

signal = None
if prev["ma_fast"] <= prev["ma_slow"] and last["ma_fast"] > last["ma_slow"]:
    signal = "BUY"
elif prev["ma_fast"] >= prev["ma_slow"] and last["ma_fast"] < last["ma_slow"]:
    signal = "SELL"

print(f"📈 Signal: {signal}")

# 3) ATR 风控：动态 SL/TP
atr = compute_atr(df, ATR_PERIOD)
if signal:
    if signal == "BUY":
        sl_price = round(mid - SL_ATR_MULT * atr, 5)
        tp_price = round(mid + TP_ATR_MULT * atr, 5)
    else:
        sl_price = round(mid + SL_ATR_MULT * atr, 5)
        tp_price = round(mid - TP_ATR_MULT * atr, 5)

    # 4) 账户净值（GBP）+ GBPUSD 中间价（用于 USD→GBP 换算）
    summary  = api.account_summary()
    nav_gbp  = float(summary["NAV"])            # 账户净值(GBP)
    gbp_usd  = api.mid_price("GBP_USD")         # 1 GBP = ? USD

    # 5) 按风险计算仓位（单位数），针对 EUR_USD 精确实现
    units = position_size_by_risk_eurusd(
        nav_gbp=nav_gbp,
        risk_pct=RISK_PCT,
        entry_price=mid,
        sl_price=sl_price,
        gbp_usd=gbp_usd,
    )
    units = max(units, UNITS_MIN_CAP)
    units = units if signal == "BUY" else -units

    # 6) 仅在 practice 环境自动下单
    if ENVIRONMENT == "practice":
        resp = api.market_order(INSTRUMENT, units=units, sl_price=sl_price, tp_price=tp_price)
        fill = resp["orderFillTransaction"]["price"]
        print(f"✅ {signal} placed @ {fill} | units={units} | SL={sl_price} | TP={tp_price} | ATR={atr:.5f}")
    else:
        print("⚠️ 当前为 live 环境，示例脚本不自动下单。")
else:
    print("ℹ️ 无交易信号，不下单。")

# 7) 查看当前持仓
open_trades = api.list_open_trades()
print(f"🔎 Open trades: {len(open_trades)}")