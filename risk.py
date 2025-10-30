# engine/risk.py
import numpy as np
import pandas as pd

def compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    传入 df 含列: h(高), l(低), c(收)，index为时间。
    返回最后一个已完成K线的 ATR 值（同价格单位）。
    """
    # 只用已完成K线
    d = df[df["complete"]].copy()

    high = d["h"]
    low  = d["l"]
    close = d["c"]

    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.rolling(period).mean()
    return float(atr.dropna().iloc[-1])

def pip_size(instrument: str) -> float:
    """
    简化：常见品种的 pip 大小
    - *_JPY → 0.01
    - 其他主要货币对 → 0.0001
    """
    if instrument.endswith("_JPY"):
        return 0.01
    return 0.0001

def position_size_by_risk_eurusd(
    nav_gbp: float,
    risk_pct: float,
    entry_price: float,
    sl_price: float,
    gbp_usd: float,
) -> int:
    """
    仅针对 EUR_USD：按“账户净值 * 风险比例”计算应下的单位数（units）。
    - 风险以 GBP 度量，但 EURUSD 的每单位每个 pip 的价值是 0.0001 美元
    - 所以先算 USD 风险，再用 GBPUSD 汇率换算到 GBP
    """
    pip = 0.0001  # EURUSD 固定
    stop_distance = abs(entry_price - sl_price)        # 价格差
    pips = stop_distance / pip                          # 止损距离(单位: pip)
    risk_per_unit_usd = pips * pip                      # 1单位在止损被打时的美元风险（≈ stop_distance）
    if risk_per_unit_usd <= 0:
        return 0
    # USD → GBP
    risk_per_unit_gbp = risk_per_unit_usd / gbp_usd
    max_risk_gbp = nav_gbp * risk_pct
    units = int(max_risk_gbp // risk_per_unit_gbp)
    return max(units, 1)