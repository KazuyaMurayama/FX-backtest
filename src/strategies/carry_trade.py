"""
S3: キャリートレード戦略 (Interest Rate Carry)

ロジック:
  1. 各月、金利差 = 外貨金利 - 円金利 を計算
  2. 金利差 > 0 → Long (高金利外貨保有)
  3. 金利差 < 0 → Short (低金利外貨を売り)
  4. シグナルは月次更新（日次データに前方補完）
  5. DDサーキットブレーカー:
       -15%超 → ポジション50%削減
       -25%超 → 全ポジション撤退

対象ペア:
  USDJPY: USD金利(FF) - JPY金利(コール) [1985〜]
  AUDUSD: AUD金利(RBA) - USD金利(FF)    [1990〜]
  NZDUSD: NZD金利(RBNZ) - USD金利(FF)  [1985〜]
  EURUSD: EUR金利(ECB) - USD金利(FF)   [1999〜]
  GBPUSD: GBP金利(BoE) - USD金利(FF)   [1997〜]

デフォルト: USDJPY (最長データ 1985〜)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from data_fetcher import fetch_fx, fetch_rate
from backtest_engine import run_backtest, BacktestResult

# 通貨ペアごとの金利設定: (外貨金利名, 基軸通貨金利名)
PAIR_RATES: dict[str, tuple[str, str]] = {
    "USDJPY": ("USD_FEDFUNDS",  "JPY_CALLRATE"),
    "AUDUSD": ("AUD_RBA",       "USD_FEDFUNDS"),
    "NZDUSD": ("NZD_RBNZ",      "USD_FEDFUNDS"),
    "EURUSD": ("EUR_ECB",       "USD_FEDFUNDS"),
    "GBPUSD": ("GBP_BOE",       "USD_FEDFUNDS"),
}

PAIR = "USDJPY"
START = "1985-07-01"   # JPY金利データ開始日
DD_REDUCE_THRESHOLD = -0.15   # -15%でポジション縮小
DD_EXIT_THRESHOLD   = -0.25   # -25%で全撤退


def _get_rate_diff(pair: str) -> pd.Series:
    """月次金利差 (外貨金利 - 基軸通貨金利) を日次に前方補完して返す。"""
    if pair not in PAIR_RATES:
        raise ValueError(f"Carry未対応ペア: {pair}. 対応: {list(PAIR_RATES.keys())}")

    rate_a_name, rate_b_name = PAIR_RATES[pair]
    rate_a = fetch_rate(rate_a_name)["rate"]
    rate_b = fetch_rate(rate_b_name)["rate"]

    # 共通期間に揃える
    common_start = max(rate_a.index.min(), rate_b.index.min())
    rate_a = rate_a.loc[common_start:]
    rate_b = rate_b.loc[common_start:]

    # 月次でリサンプルして差分計算
    rate_a_m = rate_a.resample("ME").last()
    rate_b_m = rate_b.resample("ME").last()
    diff = rate_a_m - rate_b_m

    return diff  # 月次Series


def generate_signals(
    prices: pd.Series,
    pair: str = PAIR,
    dd_reduce: float = DD_REDUCE_THRESHOLD,
    dd_exit: float = DD_EXIT_THRESHOLD,
) -> pd.Series:
    rate_diff_monthly = _get_rate_diff(pair)

    # 月次シグナル: 金利差の符号
    raw_signal_monthly = np.sign(rate_diff_monthly)

    # 日次インデックスに前方補完
    raw_signal_daily = raw_signal_monthly.reindex(prices.index).ffill().fillna(0)

    # DDサーキットブレーカー（ポジション調整）
    signal = pd.Series(0.0, index=prices.index)
    equity = 1.0
    position = 0.0

    for i in range(len(prices)):
        raw = raw_signal_daily.iloc[i]

        if i > 0:
            prev_p = prices.iloc[i - 1]
            curr_p = prices.iloc[i]
            daily_ret = (curr_p / prev_p - 1.0) * position
            equity *= (1 + daily_ret)

        # ピーク比ドローダウン計算（近似: 1.0からの下落）
        if equity < 1.0:
            dd = equity - 1.0
        else:
            dd = 0.0

        if dd <= dd_exit:
            position = 0.0          # 全撤退
        elif dd <= dd_reduce:
            position = raw * 0.5    # 50%縮小
        else:
            position = raw          # 通常シグナル

        signal.iloc[i] = position

    return signal


def run(
    pair: str = PAIR,
    start: str = START,
    end: str | None = None,
) -> BacktestResult:
    prices = fetch_fx(pair)["close"]
    signals = generate_signals(prices, pair=pair)
    return run_backtest(
        prices, signals,
        pair=pair,
        label=f"S3_Carry_{pair}",
        start=start,
        end=end,
    )


if __name__ == "__main__":
    result = run()
    print(result.summary())
