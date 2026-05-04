"""
S6: 積立FX戦略 (Dollar-Cost Averaging / DCA)

ロジック:
  毎月末に一定額（デフォルト10万円）分のUSDを購入し続ける。
  売却なし。SBI証券の積立FXに相当するベンチマーク戦略。

エクイティ計算:
  equity(t) = (保有USD総量 × 現在レート) / 累積投資JPY総額
  → 投資効率比。1.0スタート, >1.0 = 利益, <1.0 = 損失。

評価指標の解釈:
  - CAGR: 円換算での年率投資効率成長率
  - Worst DD: 最悪時点での評価損率
  - Sharpeは参考値（キャッシュフロー加重ではなく等価換算のため）

デフォルト: USD/JPY 1990〜, 毎月末100,000JPY投資
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from data_fetcher import fetch_fx
from backtest_engine import BacktestResult
from evaluation import evaluate, drawdown_series

PAIR = "USDJPY"
START = "1990-01-01"
MONTHLY_AMOUNT = 100_000   # JPY


def run(
    pair: str = PAIR,
    start: str = START,
    end: str | None = None,
    monthly_amount: float = MONTHLY_AMOUNT,
) -> BacktestResult:
    prices = fetch_fx(pair)["close"]
    prices.index = pd.to_datetime(prices.index)

    if start:
        prices = prices.loc[start:]
    if end:
        prices = prices.loc[:end]
    prices = prices.ffill().dropna()

    # 月末価格
    monthly_prices = prices.resample("ME").last()

    total_usd = 0.0
    cumulative_jpy = 0.0
    nav_records: list[tuple] = []

    for date, price in monthly_prices.items():
        usd_bought = monthly_amount / price
        total_usd += usd_bought
        cumulative_jpy += monthly_amount

        current_value = total_usd * price
        nav = current_value / cumulative_jpy   # 投資効率比
        nav_records.append((date, nav))

    nav_monthly = pd.Series(
        [v for _, v in nav_records],
        index=pd.DatetimeIndex([d for d, _ in nav_records]),
    )

    # 日次に前方補完
    equity_daily = nav_monthly.reindex(prices.index).ffill().bfill()
    equity_daily = equity_daily / equity_daily.iloc[0]   # 1.0始まりに正規化

    # リターン・シグナル（DCA特有）
    returns = equity_daily.pct_change().fillna(0)
    # DCAはフルロングに相当（1.0シグナル）
    signals = pd.Series(1.0, index=prices.index)

    dd = drawdown_series(equity_daily)
    metrics = evaluate(equity_daily, returns, signals)

    return BacktestResult(
        label=f"S6_DCA_{pair}",
        pair=pair,
        equity=equity_daily,
        returns=returns,
        signals=signals,
        drawdowns=dd,
        metrics=metrics,
    )


if __name__ == "__main__":
    result = run()
    print(result.summary())
