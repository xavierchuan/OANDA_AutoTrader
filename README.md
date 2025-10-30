# OANDA AutoTrader 🚀  
_A fully automated FX trading system built with Python and OANDA REST API._

## 🧠 Overview
This project implements a **complete algorithmic trading framework** that connects directly to the **OANDA v20 REST API**.  
It automatically retrieves live price data, detects trade signals using **moving average crossovers**, calculates position sizes with **ATR-based risk management**, and executes real-time trades in a **demo or live environment**.

The system is designed for **quantitative developers** who want to build, test, and deploy rule-based trading strategies in a production-style architecture.

---

## ⚙️ Key Features
- **Live OANDA API integration** — real-time price fetching and trade execution  
- **Modular architecture** — clean separation of API, risk, and strategy logic  
- **Strategy engine** — Moving Average (MA10/MA30) crossover signals  
- **Risk management** — ATR-based stop loss & take profit, dynamic position sizing  
- **Daemon process** — continuously monitors markets every minute (`main_loop.py`)  
- **Logging system** — structured log output with timestamps (`run.log`)  
- **Safe environment control** — switch between *practice* and *live* trading modes  

---

## 🧩 Project Structure
OANDA_AutoTrader/
│
├── engine/
│   ├── oanda_api.py       # Handles OANDA REST API communication
│   ├── risk.py            # Computes ATR, pip size, and risk-based position sizing
│
├── main.py                # Quick test: fetch price, check signal, execute single trade
├── main_loop.py           # Continuous trading daemon (production-style loop)
├── run.log                # Auto-generated log file
├── requirements.txt       # Python dependencies
└── README.md

---

## 🧮 Strategy Logic

The system uses a **Moving Average Crossover** on the 5-minute chart (M5):

- **Bullish crossover** → MA10 crosses above MA30 → `BUY` signal  
- **Bearish crossover** → MA10 crosses below MA30 → `SELL` signal  

Each trade includes:
- Stop Loss = 1.5 × ATR  
- Take Profit = 2.5 × ATR  
- Position size determined by 0.5% account risk  

---

## 🛠️ Setup & Usage

### 1️⃣ Install Dependencies
```bash
pip install -r requirements.txt

2️⃣ Set Your Credentials

Edit the following constants in main.py or use environment variables:
ACCESS_TOKEN = "YOUR_OANDA_TOKEN"
ACCOUNT_ID   = "YOUR_OANDA_ACCOUNT_ID"
ENVIRONMENT  = "practice"  # or "live"

3️⃣ Run Once (Single Signal Test)
python main.py

4️⃣ Run as Continuous Daemon
python main_loop.py
The bot will log every signal, trade, and error to run.log automatically.

📊 Example Output
✅ Connecting to OANDA API...
✅ Current Price: {'instrument': 'EUR_USD', 'bid': 1.15713, 'ask': 1.15719}
📈 Signal: BUY
✅ Executed: BUY @ 1.15715 | SL=1.15575 | TP=1.16075 | units=10500

📚 Technical Highlights
Category     Details
Language     Python 3.10+
API          OANDA v20 REST API
Libraries    oandapyV20, pandas, requests, datetime
Strategy     Moving Average Crossover (M5)
Risk Model   ATR-based dynamic position sizing
Logging      Time-stamped trade logs (UTC)

🧠 Possible Extensions
	•	Add multi-asset trading (e.g., USD/JPY, GBP/USD)
	•	Integrate RSI / MACD / Bollinger filters
	•	Build a backtesting engine for historical evaluation
	•	Connect Telegram / email notifications
	•	Deploy on a VPS for 24/7 autonomous trading

💬 Author

Xiaochuan Li
MSc Financial Engineering | University of Birmingham
📍 Birmingham, UK
🔗 linkedin.com/in/xiaochuan-li-finance￼

⚠️ Disclaimer

This project is for educational and research purposes only.
Use at your own risk. The author takes no responsibility for financial losses caused by live trading.



