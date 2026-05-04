"""
S1: 移動平均クロス戦略 (MA Crossover)

ロジック:
  - SMA(fast) > SMA(slow) → Long (+1)
  - SMA(fast) < SMA(slow) → Short (-1)
  - データ不足期間 → Flat (0)

デフォルト: fast=50日, slow=200日, USD/JPY 1971〜
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from data_fetcher import fetch_fx
from backtest_engine import run_backtest, BacktestResult

PAIR = "USDJPY"
START = "1971-01-01"
FAST = 50
SLOW = 200


def generate_signals(prices: pd.Series, fast: int = FAST, slow: int = SLOW) -> pd.Series:
    sma_fast = prices.rolling(fast).mean()
    sma_slow = prices.rolling(slow).mean()

    signal = pd.Series(0.0, index=prices.index)
    signal[sma_fast > sma_slow] = 1.0
    signal[sma_fast < sma_slow] = -1.0
    # SMA計算に必要な期間はFlatのまま
    signal.iloc[:slow] = 0.0
    return signal


def run(
    pair: str = PAIR,
    start: str = START,
    end: str | None = None,
    fast: int = FAST,
    slow: int = SLOW,
) -> BacktestResult:
    prices = fetch_fx(pair)["close"]
    signals = generate_signals(prices, fast=fast, slow=slow)
    return run_backtest(
        prices, signals,
        pair=pair,
        label=f"S1_MA{fast}/{slow}",
        start=start,
        end=end,
    )


if __name__ == "__main__":
    result = run()
    print(result.summary())
