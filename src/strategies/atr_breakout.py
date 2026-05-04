"""
S2: ATRブレイクアウト戦略 (Donchian Channel + ATR Trailing Stop)

ロジック:
  1. Donchianチャネル(N日高値/安値)のブレイクアウトでエントリー
     - Close > N日最高値 → Long (+1)
     - Close < N日最低値 → Short (-1)
  2. ATRフィルタ: 現ATR < 過去FILTER日平均ATR × COMPRESS_RATIO なら無効
     (ボラティリティ圧縮フィルタ = 静穏後のブレイクアウトのみ有効)
  3. 一度エントリーしたらATR×STOP倍のトレイリングストップで管理

注意:
  FREDデータはclose-onlyのため High/Low 不使用。
  ATR近似 = |close - close.shift(1)| の14日EWM。
  Donchian = N日closeの最大/最小値。

デフォルト: PERIOD=20, ATR=14, FILTER=50, USD/JPY 1971〜
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
PERIOD = 20        # Donchianチャネル期間
ATR_PERIOD = 14    # ATR期間
FILTER_PERIOD = 50 # ATRフィルタ平均期間
COMPRESS_RATIO = 0.8  # ATR圧縮判定閾値（現ATR < 過去平均×この値 → フィルタON）
STOP_MULT = 2.0    # トレイリングストップ = ATR × STOP_MULT


def _calc_atr(prices: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    """close-only ATR近似: 絶対日次変動の指数移動平均"""
    daily_change = prices.diff().abs()
    return daily_change.ewm(span=period, adjust=False).mean()


def generate_signals(
    prices: pd.Series,
    period: int = PERIOD,
    atr_period: int = ATR_PERIOD,
    filter_period: int = FILTER_PERIOD,
    compress_ratio: float = COMPRESS_RATIO,
    stop_mult: float = STOP_MULT,
) -> pd.Series:
    atr = _calc_atr(prices, atr_period)
    atr_avg = atr.rolling(filter_period).mean()

    # Donchianチャネル（前日までのN日高値/安値 → lookahead bias回避でshift(1)）
    highest = prices.shift(1).rolling(period).max()
    lowest = prices.shift(1).rolling(period).min()

    # ATRボラティリティ圧縮フィルタ（静穏相場のみ有効）
    compressed = atr < (atr_avg * compress_ratio)

    signal = pd.Series(0.0, index=prices.index)
    position = 0.0
    stop_level = np.nan

    for i in range(1, len(prices)):
        p = prices.iloc[i]
        prev_pos = position

        # トレイリングストップ判定
        if position == 1.0 and not np.isnan(stop_level) and p < stop_level:
            position = 0.0
            stop_level = np.nan
        elif position == -1.0 and not np.isnan(stop_level) and p > stop_level:
            position = 0.0
            stop_level = np.nan

        # エントリー（フィルタ通過時のみ）
        if compressed.iloc[i] and position == 0.0:
            if not np.isnan(highest.iloc[i]) and p > highest.iloc[i]:
                position = 1.0
                stop_level = p - stop_mult * atr.iloc[i]
            elif not np.isnan(lowest.iloc[i]) and p < lowest.iloc[i]:
                position = -1.0
                stop_level = p + stop_mult * atr.iloc[i]

        # トレイリングストップを更新（利益方向へのみ移動）
        if position == 1.0:
            new_stop = p - stop_mult * atr.iloc[i]
            if np.isnan(stop_level):
                stop_level = new_stop
            else:
                stop_level = max(stop_level, new_stop)
        elif position == -1.0:
            new_stop = p + stop_mult * atr.iloc[i]
            if np.isnan(stop_level):
                stop_level = new_stop
            else:
                stop_level = min(stop_level, new_stop)

        signal.iloc[i] = position

    # データ不足期間はFlat
    warmup = max(period, filter_period, atr_period)
    signal.iloc[:warmup] = 0.0
    return signal


def run(
    pair: str = PAIR,
    start: str = START,
    end: str | None = None,
    period: int = PERIOD,
    atr_period: int = ATR_PERIOD,
    filter_period: int = FILTER_PERIOD,
    compress_ratio: float = COMPRESS_RATIO,
    stop_mult: float = STOP_MULT,
) -> BacktestResult:
    prices = fetch_fx(pair)["close"]
    signals = generate_signals(
        prices,
        period=period,
        atr_period=atr_period,
        filter_period=filter_period,
        compress_ratio=compress_ratio,
        stop_mult=stop_mult,
    )
    return run_backtest(
        prices, signals,
        pair=pair,
        label=f"S2_ATR_Breakout{period}",
        start=start,
        end=end,
    )


if __name__ == "__main__":
    result = run()
    print(result.summary())
