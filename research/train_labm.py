import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

df = pd.read_csv("data/eurusd_m1.csv")

X = df[['ret_1', 'ret_3', 'ema_fast', 'ema_slow', 'atr']]
y = df['label']  # 1=BUY, 0=SELL

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
model = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.05, max_depth=6)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print("Accuracy:", accuracy_score(y_test, y_pred))

joblib.dump(model, "../models/lgb_model.pkl")
print("✅ Saved model to ../models/lgb_model.pkl")