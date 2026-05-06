import yfinance as yf
import pandas as pd
from datetime import datetime

pairs = [
    # メジャー
    ("USDJPY=X", "USD/JPY"),
    ("EURUSD=X", "EUR/USD"),
    ("GBPUSD=X", "GBP/USD"),
    ("AUDUSD=X", "AUD/USD"),
    ("NZDUSD=X", "NZD/USD"),
    ("USDCAD=X", "USD/CAD"),
    ("USDCHF=X", "USD/CHF"),
    # クロス円
    ("EURJPY=X", "EUR/JPY"),
    ("GBPJPY=X", "GBP/JPY"),
    ("AUDJPY=X", "AUD/JPY"),
    ("NZDJPY=X", "NZD/JPY"),
    ("CHFJPY=X", "CHF/JPY"),
    ("CADJPY=X", "CAD/JPY"),
    ("ZARJPY=X", "ZAR/JPY"),
    ("TRYJPY=X", "TRY/JPY"),
    ("MXNJPY=X", "MXN/JPY"),
    ("SGDJPY=X", "SGD/JPY"),
    ("HKDJPY=X", "HKD/JPY"),
    ("NOKJPY=X", "NOK/JPY"),
    ("SEKJPY=X", "SEK/JPY"),
    # その他クロス
    ("EURGBP=X", "EUR/GBP"),
    ("EURAUD=X", "EUR/AUD"),
    ("EURCAD=X", "EUR/CAD"),
    ("EURCHF=X", "EUR/CHF"),
    ("AUDNZD=X", "AUD/NZD"),
    ("GBPAUD=X", "GBP/AUD"),
    ("GBPCAD=X", "GBP/CAD"),
    ("GBPCHF=X", "GBP/CHF"),
    ("AUDCAD=X", "AUD/CAD"),
    ("NZDCAD=X", "NZD/CAD"),
]

results = []
for ticker, name in pairs:
    try:
        df = yf.Ticker(ticker).history(period="max")
        if len(df) > 0:
            start = df.index[0].strftime("%Y-%m-%d")
            end = df.index[-1].strftime("%Y-%m-%d")
            n = len(df)
            results.append({"ペア": name, "Ticker": ticker, "開始日": start, "終了日": end, "営業日数": n, "状態": "OK"})
        else:
            results.append({"ペア": name, "Ticker": ticker, "開始日": "-", "終了日": "-", "営業日数": 0, "状態": "空"})
    except Exception as e:
        results.append({"ペア": name, "Ticker": ticker, "開始日": "-", "終了日": "-", "営業日数": 0, "状態": f"ERROR: {e}"})

df_result = pd.DataFrame(results)
print(df_result.to_markdown(index=False))
df_result.to_csv("results/fx_yf_availability.csv", index=False, encoding="utf-8-sig")
print(f"\n保存完了: results/fx_yf_availability.csv")
