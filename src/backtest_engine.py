"""
backtest_engine.py — FXバックテストエンジン

設計原則（SPEC.md §5, §7 準拠）:
  1. Lookahead bias 厳禁: signal.shift(1) で翌日適用
  2. スプレッドコスト: 建玉変化時のみ適用（片道）
  3. レバレッジ: デフォルト1倍（変更可）
  4. 入力: close価格Series + signal Series → BacktestResult

使用法:
    engine = BacktestEngine(pair='USDJPY')
    result = engine.run(prices, signals, label='MA_Crossover')
    print(result.metrics)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from evaluation import evaluate, drawdown_series

# ─── スプレッドコスト（SBI証券 実績値） ──────────────────────────────────────

SPREAD_ABS: dict[str, float] = {
    "USDJPY": 0.002,     # 0.2銭（対円ペア: JPY建て絶対値）
    "EURUSD": 0.00004,   # 0.4pips
    "GBPUSD": 0.00009,   # 0.9pips
    "AUDUSD": 0.00006,   # 0.6pips
    "NZDUSD": 0.00008,   # 0.8pips
    "USDCHF": 0.00006,   # 0.6pips
    "USDCAD": 0.00010,   # 1.0pips
    # クロス円ペア（SBI証券FXα スプレッド実績値）
    "EURJPY": 0.005,     # 0.5銭
    "GBPJPY": 0.009,     # 0.9銭
    "AUDJPY": 0.005,     # 0.5銭
    "NZDJPY": 0.012,     # 1.2銭
    "CHFJPY": 0.018,     # 1.8銭
    "CADJPY": 0.017,     # 1.7銭
    "MXNJPY": 0.003,     # 0.3銭（SBI証券最狭水準）
    "ZARJPY": 0.009,     # 0.9銭
}
SPREAD_DEFAULT = 0.00008   # 未登録ペアのデフォルト


# ─── 結果コンテナ ─────────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    """バックテスト結果。"""
    label: str
    pair: str
    equity: pd.Series           # エクイティカーブ（1.0始まり）
    returns: pd.Series          # 日次純リターン（スプレッド差引後）
    signals: pd.Series          # 適用シグナル（shift済み）
    drawdowns: pd.Series        # ドローダウン時系列
    metrics: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.metrics:
            self.metrics = evaluate(self.equity, self.returns, self.signals)

    def summary(self) -> str:
        m = self.metrics
        return (
            f"[{self.label} | {self.pair}]\n"
            f"  Sharpe    : {m['sharpe']:.3f}\n"
            f"  CAGR      : {m['cagr']:.1%}\n"
            f"  Worst DD  : {m['worst_dd']:.1%}\n"
            f"  Calmar    : {m['calmar']:.3f}\n"
            f"  Win Rate  : {m['win_rate']:.1%}\n"
            f"  Trades    : {m['n_trades']}\n"
            f"  Period    : {m['period_years']}年\n"
            f"  Total Ret : {m['total_return']:.1%}"
        )


# ─── エンジン本体 ─────────────────────────────────────────────────────────────

class BacktestEngine:
    """
    FX日足バックテストエンジン。

    Parameters
    ----------
    pair : str
        通貨ペア名（例: 'USDJPY'）
    leverage : float
        レバレッジ倍率（デフォルト=1.0）
    initial_capital : float
        初期資金（評価用、実際の計算には非使用）
    """

    def __init__(
        self,
        pair: str,
        leverage: float = 1.0,
        initial_capital: float = 1_000_000,
    ):
        self.pair = pair.upper()
        self.leverage = leverage
        self.initial_capital = initial_capital
        self._spread_abs = SPREAD_ABS.get(self.pair, SPREAD_DEFAULT)

    def run(
        self,
        prices: pd.Series,
        signals: pd.Series,
        label: str = "strategy",
        start: str | None = None,
        end: str | None = None,
    ) -> BacktestResult:
        """
        バックテストを実行してBacktestResultを返す。

        Parameters
        ----------
        prices : pd.Series
            日次終値（DatetimeIndex）
        signals : pd.Series
            売買シグナル {-1: Short, 0: Flat, +1: Long}
            ※ 当日の信号を翌日に適用（lookahead bias排除）
        label : str
            戦略名
        start, end : str
            期間フィルタ（任意）。例: '1990-01-01'

        Returns
        -------
        BacktestResult
        """
        prices, signals = self._align_and_filter(prices, signals, start, end)
        applied_sig = self._apply_lag(signals)
        returns = self._calc_returns(prices, applied_sig)
        equity = self._calc_equity(returns)
        dd = drawdown_series(equity)

        return BacktestResult(
            label=label,
            pair=self.pair,
            equity=equity,
            returns=returns,
            signals=applied_sig,
            drawdowns=dd,
        )

    # ─── 内部メソッド ─────────────────────────────────────────────────────────

    def _align_and_filter(
        self,
        prices: pd.Series,
        signals: pd.Series,
        start: str | None,
        end: str | None,
    ) -> tuple[pd.Series, pd.Series]:
        """インデックスを揃え、期間フィルタを適用する。"""
        prices = prices.copy()
        prices.index = pd.to_datetime(prices.index)

        signals = signals.reindex(prices.index).ffill().fillna(0)

        if start:
            prices = prices.loc[start:]
            signals = signals.loc[start:]
        if end:
            prices = prices.loc[:end]
            signals = signals.loc[:end]

        # 欠損価格を前方補完（土日・祝日は既にfill済みだが念のため）
        prices = prices.ffill().dropna()
        signals = signals.reindex(prices.index).ffill().fillna(0)
        return prices, signals

    def _apply_lag(self, signals: pd.Series) -> pd.Series:
        """
        シグナルに1日ラグを適用してlookahead biasを排除。

        当日終値でシグナル確定 → 翌日終値〜翌日終値のリターンに適用。
        """
        return signals.shift(1).fillna(0)

    def _calc_returns(
        self,
        prices: pd.Series,
        applied_sig: pd.Series,
    ) -> pd.Series:
        """
        日次純リターン = ポジションリターン - スプレッドコスト。

        スプレッドコストはポジションが変化した日のみ適用（片道）。
        """
        price_ret = prices.pct_change().fillna(0)

        # ポジションリターン（レバレッジ適用）
        pos_ret = applied_sig * price_ret * self.leverage

        # スプレッドコスト: 建玉変化量に比例（abs(delta_signal) が係数）
        delta_sig = applied_sig.diff().abs().fillna(0)
        spread_fraction = self._spread_abs / prices  # スプレッドを価格比率に変換
        spread_cost = delta_sig * spread_fraction * self.leverage

        return pos_ret - spread_cost

    def _calc_equity(self, returns: pd.Series) -> pd.Series:
        """リターン系列からエクイティカーブ（1.0始まり）を計算。"""
        equity = (1 + returns).cumprod()
        equity.iloc[0] = 1.0   # 初日を1.0に固定
        return equity


# ─── ユーティリティ ───────────────────────────────────────────────────────────

def run_backtest(
    prices: pd.Series,
    signals: pd.Series,
    pair: str,
    label: str = "strategy",
    leverage: float = 1.0,
    start: str | None = None,
    end: str | None = None,
) -> BacktestResult:
    """BacktestEngine を直接呼ばずに使えるショートカット関数。"""
    engine = BacktestEngine(pair=pair, leverage=leverage)
    return engine.run(prices, signals, label=label, start=start, end=end)


def compare_results(results: list[BacktestResult]) -> pd.DataFrame:
    """
    複数のBacktestResultを比較テーブルにまとめる。

    Returns
    -------
    pd.DataFrame
        rows=strategy, cols=評価指標
    """
    rows = {}
    for r in results:
        rows[r.label] = r.metrics
    df = pd.DataFrame(rows).T
    df.index.name = "strategy"
    return df
