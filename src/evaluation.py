"""
evaluation.py — バックテスト評価指標計算モジュール

評価指標（SPEC.md §1 準拠）:
  - Sharpe Ratio（年率, 無リスク金利=0）
  - CAGR（年率複利成長率）
  - Worst Drawdown（最大峰値比下落率）
  + Calmar Ratio, Max DD Duration, Win Rate, Profit Factor, Trade Count

全関数は純関数（副作用なし）。入力は pd.Series、出力は float or dict。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


# ─── 個別指標 ─────────────────────────────────────────────────────────────────

def sharpe_ratio(returns: pd.Series, risk_free: float = 0.0) -> float:
    """
    年率 Sharpe Ratio。

    Parameters
    ----------
    returns : pd.Series
        日次リターン（小数）
    risk_free : float
        日次無リスク金利（デフォルト=0）

    Returns
    -------
    float
        Sharpe Ratio（年率化済み）。標準偏差=0の場合 nan を返す。
    """
    excess = returns - risk_free
    std = excess.std()
    if std == 0 or np.isnan(std):
        return np.nan
    return float((excess.mean() / std) * np.sqrt(TRADING_DAYS_PER_YEAR))


def cagr(equity: pd.Series) -> float:
    """
    CAGR（年率複利成長率）。

    Parameters
    ----------
    equity : pd.Series
        エクイティカーブ（1.0始まり）

    Returns
    -------
    float
        CAGR（小数。0.10 = 10%/年）
    """
    if len(equity) < 2:
        return np.nan
    n_years = len(equity) / TRADING_DAYS_PER_YEAR
    total_return = equity.iloc[-1] / equity.iloc[0]
    if total_return <= 0:
        return -1.0
    return float(total_return ** (1.0 / n_years) - 1.0)


def worst_drawdown(equity: pd.Series) -> float:
    """
    最悪ドローダウン（Worst Drawdown）。

    Returns
    -------
    float
        最大下落率（負の値。-0.30 = -30%）
    """
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    return float(dd.min())


def drawdown_series(equity: pd.Series) -> pd.Series:
    """ドローダウン時系列を返す（可視化用）。"""
    running_max = equity.cummax()
    return (equity - running_max) / running_max


def max_drawdown_duration(equity: pd.Series) -> int:
    """最長ドローダウン継続日数（日）。"""
    dd = drawdown_series(equity)
    in_dd = dd < 0
    max_dur = 0
    cur_dur = 0
    for v in in_dd:
        if v:
            cur_dur += 1
            max_dur = max(max_dur, cur_dur)
        else:
            cur_dur = 0
    return max_dur


def calmar_ratio(equity: pd.Series) -> float:
    """Calmar Ratio = CAGR / abs(Worst DD)。"""
    wd = worst_drawdown(equity)
    if wd == 0:
        return np.nan
    return float(cagr(equity) / abs(wd))


def win_rate(returns: pd.Series, signals: pd.Series) -> float:
    """
    勝率（ポジション保有日のうちプラスリターン日の割合）。

    Parameters
    ----------
    returns : pd.Series  日次リターン（純損益）
    signals : pd.Series  ポジションシグナル（-1/0/+1）
    """
    active = signals != 0
    if active.sum() == 0:
        return np.nan
    active_ret = returns[active]
    return float((active_ret > 0).mean())


def profit_factor(returns: pd.Series) -> float:
    """Profit Factor = 総利益 / 総損失の絶対値。"""
    gains = returns[returns > 0].sum()
    losses = returns[returns < 0].sum()
    if losses == 0:
        return np.inf
    return float(gains / abs(losses))


def trade_count(signals: pd.Series) -> int:
    """ポジション変化回数（片道）。"""
    return int((signals.diff().abs() > 0).sum())


# ─── 総合評価 ─────────────────────────────────────────────────────────────────

def evaluate(
    equity: pd.Series,
    returns: pd.Series,
    signals: pd.Series,
) -> dict:
    """
    全評価指標をまとめて計算して返す。

    Parameters
    ----------
    equity  : pd.Series  エクイティカーブ（1.0始まり、日次）
    returns : pd.Series  日次純リターン（スプレッドコスト差引後）
    signals : pd.Series  適用済みシグナル（shift後）

    Returns
    -------
    dict
        {sharpe, cagr, worst_dd, calmar, win_rate,
         profit_factor, n_trades, max_dd_duration,
         total_return, period_years}
    """
    period_years = len(equity) / TRADING_DAYS_PER_YEAR
    total_ret = float(equity.iloc[-1] / equity.iloc[0] - 1.0)

    return {
        "sharpe":          round(sharpe_ratio(returns), 4),
        "cagr":            round(cagr(equity), 4),
        "worst_dd":        round(worst_drawdown(equity), 4),
        "calmar":          round(calmar_ratio(equity), 4),
        "win_rate":        round(win_rate(returns, signals), 4),
        "profit_factor":   round(profit_factor(returns), 4),
        "n_trades":        trade_count(signals),
        "max_dd_duration": max_drawdown_duration(equity),
        "total_return":    round(total_ret, 4),
        "period_years":    round(period_years, 1),
    }


def metrics_table(results: dict[str, dict]) -> pd.DataFrame:
    """
    複数戦略の評価指標を比較テーブルで返す。

    Parameters
    ----------
    results : dict  {strategy_name: evaluate()の出力dict}
    """
    df = pd.DataFrame(results).T
    df.index.name = "strategy"
    fmt = {
        "sharpe":        "{:.3f}",
        "cagr":          "{:.1%}",
        "worst_dd":      "{:.1%}",
        "calmar":        "{:.3f}",
        "win_rate":      "{:.1%}",
        "profit_factor": "{:.3f}",
        "total_return":  "{:.1%}",
    }
    for col, f in fmt.items():
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f.format(x) if pd.notna(x) else "NaN")
    return df
