# engine/oanda_api.py

import oandapyV20
from oandapyV20 import API
from oandapyV20.endpoints import pricing, instruments as ins, orders, trades, accounts

class OandaAPI:
    def __init__(self, access_token, account_id, environment="practice"):
        self.client = API(access_token=access_token, environment=environment)
        self.account_id = account_id

    def get_price(self, instrument="EUR_USD"):
        r = pricing.PricingInfo(accountID=self.account_id, params={"instruments": instrument})
        data = self.client.request(r)
        bid = float(data["prices"][0]["bids"][0]["price"])
        ask = float(data["prices"][0]["asks"][0]["price"])
        return {"instrument": instrument, "bid": bid, "ask": ask}
    
    def get_candles(self, instrument="EUR_USD", granularity="M5", count=200, price="M"):
        """
        granularity: S5,S10,S30,M1,M5,M15,M30,H1,H4,D,W,M
        price: 'M' 中间价; 也可 'B','A','BA','MBA'
        """
        params = {"granularity": granularity, "count": count, "price": price}
        r = ins.InstrumentsCandles(instrument=instrument, params=params)
        data = self.client.request(r)
        # 转成 DataFrame
        import pandas as pd
        rows = []
        for c in data["candles"]:
            rows.append({
                "time": c["time"],
                "complete": c["complete"],
                "o": float(c["mid"]["o"]),
                "h": float(c["mid"]["h"]),
                "l": float(c["mid"]["l"]),
                "c": float(c["mid"]["c"]),
            })
        df = pd.DataFrame(rows)
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        return df
    
    def account_summary(self):
        r = accounts.AccountSummary(accountID=self.account_id)
        return self.client.request(r)["account"]

    def market_order(self, instrument="EUR_USD", units=100, sl_price=None, tp_price=None):
        """
        市价单；多头 units>0，空头 units<0。可选止损/止盈价格（绝对价位）。
        """
        payload = {
            "order": {
                "instrument": instrument,
                "units": str(units),
                "type": "MARKET",
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
            }
        }
        if tp_price:
            payload["order"]["takeProfitOnFill"] = {"price": str(tp_price)}
        if sl_price:
            payload["order"]["stopLossOnFill"] = {"price": str(sl_price)}

        r = orders.OrderCreate(accountID=self.account_id, data=payload)
        return self.client.request(r)

    def list_open_trades(self):
        r = trades.OpenTrades(accountID=self.account_id)
        return self.client.request(r).get("trades", [])

    def close_all_trades(self):
        """平掉所有持仓（按品种逐个平）"""
        open_trades = self.list_open_trades()
        results = []
        for t in open_trades:
            trade_id = t["id"]
            r = trades.TradesClose(accountID=self.account_id, tradeID=trade_id, data={"units": "ALL"})
            results.append(self.client.request(r))
        return results
    
    def mid_price(self, instrument="EUR_USD"):
        r = pricing.PricingInfo(accountID=self.account_id, params={"instruments": instrument})
        data = self.client.request(r)
        bid = float(data["prices"][0]["bids"][0]["price"])
        ask = float(data["prices"][0]["asks"][0]["price"])
        return (bid + ask) / 2.0