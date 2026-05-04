"""
S4: RSI逆張り戦略 (RSI Mean Reversion)

ロジック:
  1. RSI(14) < 30 → Long エントリー
  2. RSI(14) > 70 → Short エントリー
  3. エグジット: RSI が中立ゾーン(45〜55)に戻ったとき OR ATR(14)×1.5ストップ
  4. トレンドフィルタ: SMA(200)より上でのみLong有効（下ではShortのみ）

デフォルト: USD/JPY 1971〜
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
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_EXIT_LOW = 45
RSI_EXIT_HIGH = 55
ATR_PERIOD = 14
ATR_STOP_MULT = 1.5
TREND_MA = 200


def _calc_rsi(prices: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _calc_atr(prices: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    return prices.diff().abs().ewm(span=period, adjust=False).mean()


def generate_signals(
    prices: pd.Series,
    rsi_period: int = RSI_PERIOD,
    oversold: int = RSI_OVERSOLD,
    overbought: int = RSI_OVERBOUGHT,
    exit_low: int = RSI_EXIT_LOW,
    exit_high: int = RSI_EXIT_HIGH,
    atr_period: int = ATR_PERIOD,
    atr_stop_mult: float = ATR_STOP_MULT,
    trend_ma: int = TREND_MA,
) -> pd.Series:
    rsi = _calc_rsi(prices, rsi_period)
    atr = _calc_atr(prices, atr_period)
    sma_trend = prices.rolling(trend_ma).mean()

    signal = pd.Series(0.0, index=prices.index)
    position = 0.0
    stop_level = np.nan
    warmup = max(rsi_period * 2, trend_ma)

    for i in range(warmup, len(prices)):
        p = prices.iloc[i]
        r = rsi.iloc[i]
        a = atr.iloc[i]
        trend_up = p > sma_trend.iloc[i]

        # ストップ損切りチェック
        if position == 1.0 and not np.isnan(stop_level) and p < stop_level:
            position = 0.0
            stop_level = np.nan
        elif position == -1.0 and not np.isnan(stop_level) and p > stop_level:
            position = 0.0
            stop_level = np.nan

        # エグジット: RSI中立域に戻ったとき
        if position == 1.0 and exit_low <= r <= exit_high:
            position = 0.0
            stop_level = np.nan
        elif position == -1.0 and exit_low <= r <= exit_high:
            position = 0.0
            stop_level = np.nan

        # エントリー
        if position == 0.0:
            if r < oversold and trend_up:
                # 上昇トレンド中の売られ過ぎ → Long
                position = 1.0
                stop_level = p - atr_stop_mult * a
            elif r > overbought and not trend_up:
                # 下降トレンド中の買われ過ぎ → Short
                position = -1.0
                stop_level = p + atr_stop_mult * a

        signal.iloc[i] = position

    signal.iloc[:warmup] = 0.0
    return signal


def run(
    pair: str = PAIR,
    start: str = START,
    end: str | None = None,
    rsi_period: int = RSI_PERIOD,
    oversold: int = RSI_OVERSOLD,
    overbought: int = RSI_OVERBOUGHT,
) -> BacktestResult:
    prices = fetch_fx(pair)["close"]
    signals = generate_signals(prices, rsi_period=rsi_period,
                               oversold=oversold, overbought=overbought)
    return run_backtest(
        prices, signals,
        pair=pair,
        label=f"S4_RSI{rsi_period}",
        start=start,
        end=end,
    )


if __name__ == "__main__":
    result = run()
    print(result.summary())
