"""
S5: ボリンジャーバンド平均回帰戦略 (Bollinger Band Mean Reversion)

ロジック:
  1. BB(20, 2σ): 中心線 = SMA(20), 上限 = +2σ, 下限 = -2σ
  2. Close < 下限(-2σ) → Long エントリー
  3. Close > 上限(+2σ) → Short エントリー
  4. エグジット: 中心線(SMA20)到達 OR ±1σ到達
  5. レンジフィルタ: BB幅(=4σ/SMA20)が過去中央値を下回る → レンジ相場判定
     (ADXの代替。BB幅が狭い = ボラが低い = レンジ相場)

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
BB_PERIOD = 20
BB_ENTRY_STD = 2.0
BB_EXIT_STD = 0.0   # 0.0 = 中心線でエグジット
BANDWIDTH_LOOKBACK = 252  # BB幅の中央値計算期間（1年）
ATR_PERIOD = 14
ATR_STOP_MULT = 2.5  # エントリー価格 ± ATR×この値 をストップに設定


def _calc_bb(prices: pd.Series, period: int, n_std: float):
    """(upper, middle, lower, bandwidth)を返す。"""
    middle = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    upper = middle + n_std * std
    lower = middle - n_std * std
    bandwidth = (2 * n_std * std) / middle   # 正規化BB幅
    return upper, middle, lower, bandwidth


def _calc_atr(prices: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    return prices.diff().abs().ewm(span=period, adjust=False).mean()


def generate_signals(
    prices: pd.Series,
    bb_period: int = BB_PERIOD,
    entry_std: float = BB_ENTRY_STD,
    exit_std: float = BB_EXIT_STD,
    bw_lookback: int = BANDWIDTH_LOOKBACK,
    atr_period: int = ATR_PERIOD,
    atr_stop_mult: float = ATR_STOP_MULT,
) -> pd.Series:
    # エントリー用BB
    up_entry, mid, low_entry, bw = _calc_bb(prices, bb_period, entry_std)
    # エグジット用BB
    up_exit, _, low_exit, _ = _calc_bb(prices, bb_period, exit_std)
    atr = _calc_atr(prices, atr_period)

    # レンジフィルタ: BB幅が過去中央値以下ならレンジ相場
    bw_median = bw.rolling(bw_lookback).median()
    in_range = bw <= bw_median

    signal = pd.Series(0.0, index=prices.index)
    position = 0.0
    stop_level = np.nan
    warmup = max(bb_period + 1, bw_lookback, atr_period)

    for i in range(warmup, len(prices)):
        p = prices.iloc[i]

        # ATRストップ損切り（最優先）
        if position == 1.0 and not np.isnan(stop_level) and p < stop_level:
            position = 0.0
            stop_level = np.nan
        elif position == -1.0 and not np.isnan(stop_level) and p > stop_level:
            position = 0.0
            stop_level = np.nan

        # 利食いエグジット: 中心線到達
        if position == 1.0 and p >= up_exit.iloc[i]:
            position = 0.0
            stop_level = np.nan
        elif position == -1.0 and p <= low_exit.iloc[i]:
            position = 0.0
            stop_level = np.nan

        # エントリー（レンジ相場フィルタ通過時のみ）
        if position == 0.0 and in_range.iloc[i]:
            a = atr.iloc[i]
            if p < low_entry.iloc[i]:
                position = 1.0
                stop_level = p - atr_stop_mult * a
            elif p > up_entry.iloc[i]:
                position = -1.0
                stop_level = p + atr_stop_mult * a

        signal.iloc[i] = position

    signal.iloc[:warmup] = 0.0
    return signal


def run(
    pair: str = PAIR,
    start: str = START,
    end: str | None = None,
    bb_period: int = BB_PERIOD,
    entry_std: float = BB_ENTRY_STD,
    exit_std: float = BB_EXIT_STD,
) -> BacktestResult:
    prices = fetch_fx(pair)["close"]
    signals = generate_signals(prices, bb_period=bb_period,
                               entry_std=entry_std, exit_std=exit_std)
    return run_backtest(
        prices, signals,
        pair=pair,
        label=f"S5_BB{bb_period}({entry_std}sd)",
        start=start,
        end=end,
    )


if __name__ == "__main__":
    result = run()
    print(result.summary())
