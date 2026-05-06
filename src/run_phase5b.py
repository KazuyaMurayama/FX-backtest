"""
run_phase5b.py — Phase 5B: 動的ポジションサイジング & 多通貨ポートフォリオ検証

H2: ボラティリティターゲティングによる動的レバレッジ（Sharpe改善検証）
H3: 4通貨ペアポートフォリオ（Equal-weight / Risk-parity）

実行:
    python -X utf8 src/run_phase5b.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# src/ をパスに追加
sys.path.insert(0, str(Path(__file__).parent))

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from data_fetcher import fetch_fx
from backtest_engine import run_backtest, BacktestResult
from evaluation import evaluate, drawdown_series
from strategies.atr_breakout import generate_signals

# ─── 定数 ─────────────────────────────────────────────────────────────────────

PAIR_H2 = "USDJPY"
START_H2 = "1990-01-01"

PAIRS_H3 = ["USDJPY", "EURUSD", "AUDUSD", "USDCAD"]
START_H3 = "1999-01-04"

RESULTS_DIR = Path(__file__).parent.parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"

# 日本語フォント設定
def _setup_font():
    font_candidates = ["MS Gothic", "Meiryo", "Yu Gothic", "DejaVu Sans"]
    import matplotlib.font_manager as fm
    available = {f.name for f in fm.fontManager.ttflist}
    for font in font_candidates:
        if font in available:
            plt.rcParams["font.family"] = font
            break
    plt.rcParams["axes.unicode_minus"] = False

_setup_font()


# ─── H2: ボラティリティターゲティング ─────────────────────────────────────────

def compute_vol_target_leverage(
    prices: pd.Series,
    target_vol: float = 0.10,
    max_lev: float = 5.0,
    atr_span: int = 14,
) -> pd.Series:
    """
    ATRベースのボラティリティターゲットレバレッジを計算。

    Parameters
    ----------
    prices      : 日次終値 Series
    target_vol  : 目標年率ボラティリティ（デフォルト 10%）
    max_lev     : 最大レバレッジキャップ（デフォルト 5.0）
    atr_span    : ATR EWM スパン（デフォルト 14）

    Returns
    -------
    pd.Series
        shift(1)済み時変レバレッジ（lookahead bias なし）
    """
    # ATR近似: 日次絶対変動の指数移動平均
    atr = prices.diff().abs().ewm(span=atr_span, adjust=False).mean()

    # 日次ボラ推定 = atr / price
    daily_vol = atr / prices

    # 年率換算
    annual_vol = daily_vol * np.sqrt(252)

    # レバレッジ = target_vol / annual_vol
    leverage = target_vol / annual_vol

    # キャップ適用
    leverage = leverage.clip(upper=max_lev)

    # lookahead bias 排除: 前日の推定値を使用
    leverage = leverage.shift(1)

    return leverage


def run_h2(
    prices: pd.Series,
    base_signals: pd.Series,
    pair: str = PAIR_H2,
    start: str = START_H2,
) -> tuple[BacktestResult, BacktestResult]:
    """
    H2検証: 固定 vs 動的ボラターゲットレバレッジの比較。

    Returns
    -------
    (fixed_result, dynamic_result)
    """
    # Fixed: S2ベース (leverage=1.0)
    fixed_result = run_backtest(
        prices, base_signals,
        pair=pair, label="S2_Fixed_1x",
        leverage=1.0,
        start=start,
    )

    # Dynamic: シグナル * ボラターゲットレバレッジ
    lev_series = compute_vol_target_leverage(prices)

    # シグナルにレバレッジを乗算（NaN は 1.0 で補完）
    lev_series = lev_series.reindex(prices.index).fillna(1.0)
    dynamic_signals = base_signals * lev_series

    dynamic_result = run_backtest(
        prices, dynamic_signals,
        pair=pair, label="S2_DynVolTarget",
        leverage=1.0,
        start=start,
    )

    return fixed_result, dynamic_result


# ─── H3: 多通貨ペアポートフォリオ ────────────────────────────────────────────

def run_h3(start: str = START_H3) -> dict:
    """
    H3検証: 4ペアポートフォリオ（Equal-weight / Risk-parity）。

    Returns
    -------
    dict: {
        "results": {pair: BacktestResult},
        "returns_df": pd.DataFrame,
        "corr": pd.DataFrame,
        "ew_result": dict (metrics),
        "rp_result": dict (metrics),
        "ew_equity": pd.Series,
        "rp_equity": pd.Series,
    }
    """
    pair_results: dict[str, BacktestResult] = {}
    returns_dict: dict[str, pd.Series] = {}

    for pair in PAIRS_H3:
        print(f"  [{pair}] データ取得 & シグナル生成...")
        prices = fetch_fx(pair)["close"]
        prices.index = pd.to_datetime(prices.index)

        # 全期間でシグナル生成（ウォームアップ期間確保）
        signals = generate_signals(prices)

        # バックテスト実行（period filterはrun_backtest内部で適用）
        result = run_backtest(
            prices, signals,
            pair=pair, label=f"S2_{pair}",
            leverage=1.0,
            start=start,
        )
        pair_results[pair] = result
        returns_dict[pair] = result.returns

    # 日次リターンを DataFrame に集約（共通インデックスで内部結合）
    returns_df = pd.DataFrame(returns_dict).dropna(how="any")
    print(f"  共通期間: {returns_df.index[0].date()} ~ {returns_df.index[-1].date()} ({len(returns_df)}日)")

    # 相関行列
    corr = returns_df.corr()

    # ─── Equal-weight ポートフォリオ ──────────────────────────────────────────
    ew_returns = returns_df.mean(axis=1)
    ew_equity = (1 + ew_returns).cumprod()
    ew_equity.iloc[0] = 1.0
    ew_signals = pd.Series(1.0, index=ew_returns.index)  # 常にポジションあり
    ew_metrics = evaluate(ew_equity, ew_returns, ew_signals)

    # ─── Risk-parity (inverse-vol) ポートフォリオ ─────────────────────────────
    rolling_std = returns_df.rolling(window=63, min_periods=20).std()

    # 0除算回避
    rolling_std = rolling_std.replace(0, np.nan)

    inv_vol = 1.0 / rolling_std
    weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)

    # 最初の期間（ウォームアップ）はEqual-weightで補完
    weights = weights.fillna(1.0 / len(PAIRS_H3))

    # ポートフォリオリターン
    rp_returns = (returns_df * weights).sum(axis=1)
    rp_equity = (1 + rp_returns).cumprod()
    rp_equity.iloc[0] = 1.0
    rp_signals = pd.Series(1.0, index=rp_returns.index)
    rp_metrics = evaluate(rp_equity, rp_returns, rp_signals)

    return {
        "results": pair_results,
        "returns_df": returns_df,
        "corr": corr,
        "ew_metrics": ew_metrics,
        "rp_metrics": rp_metrics,
        "ew_equity": ew_equity,
        "rp_equity": rp_equity,
    }


# ─── チャート作成 ─────────────────────────────────────────────────────────────

def _fmt_pct(x, pos):
    return f"{x:.0%}"


def plot_h2(fixed: BacktestResult, dynamic: BacktestResult) -> None:
    """H2: エクイティカーブ + 指標比較棒グラフ"""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Phase 5B H2: Dynamic Vol-Targeting vs Fixed Leverage", fontsize=13, fontweight="bold")

    # Panel 1: エクイティカーブ
    ax1 = axes[0]
    ax1.plot(fixed.equity.index, fixed.equity.values, label="Fixed 1x", color="#2196F3", linewidth=1.5)
    ax1.plot(dynamic.equity.index, dynamic.equity.values, label="DynVolTarget", color="#FF5722", linewidth=1.5, alpha=0.9)
    ax1.set_title("Equity Curve (USDJPY, 1990-2026)")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Equity (1.0 = start)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Panel 2: 指標比較棒グラフ
    ax2 = axes[1]
    metrics_keys = ["sharpe", "cagr", "worst_dd", "calmar"]
    labels = ["Sharpe", "CAGR", "MaxDD", "Calmar"]
    x = np.arange(len(metrics_keys))
    width = 0.35

    fixed_vals = [fixed.metrics[k] for k in metrics_keys]
    dynamic_vals = [dynamic.metrics[k] for k in metrics_keys]

    bars1 = ax2.bar(x - width/2, fixed_vals, width, label="Fixed 1x", color="#2196F3", alpha=0.8)
    bars2 = ax2.bar(x + width/2, dynamic_vals, width, label="DynVolTarget", color="#FF5722", alpha=0.8)

    ax2.set_title("Metrics Comparison")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis="y")

    # バー上に値を表示
    for bar, val in zip(bars1, fixed_vals):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                 f"{val:.3f}", ha="center", va="bottom" if val >= 0 else "top",
                 fontsize=8, color="#2196F3")
    for bar, val in zip(bars2, dynamic_vals):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                 f"{val:.3f}", ha="center", va="bottom" if val >= 0 else "top",
                 fontsize=8, color="#FF5722")

    plt.tight_layout()
    out_path = CHARTS_DIR / "phase5b_h2_sizing.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  保存: {out_path}")


def plot_h3_portfolio(h3_data: dict) -> None:
    """H3: エクイティカーブ + Sharpe比較棒グラフ"""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle("Phase 5B H3: Multi-Currency Portfolio (1999-2026)", fontsize=13, fontweight="bold")

    pair_results = h3_data["results"]
    ew_equity = h3_data["ew_equity"]
    rp_equity = h3_data["rp_equity"]

    colors_pair = {"USDJPY": "#1565C0", "EURUSD": "#2E7D32", "AUDUSD": "#F57F17", "USDCAD": "#6A1B9A"}

    # Panel 1: エクイティカーブ
    ax1 = axes[0]
    for pair, result in pair_results.items():
        ax1.plot(result.equity.index, result.equity.values,
                 label=pair, color=colors_pair[pair], linewidth=1.0, alpha=0.6)

    ax1.plot(ew_equity.index, ew_equity.values,
             label="EqualWeight", color="#00ACC1", linewidth=2.0, linestyle="--")
    ax1.plot(rp_equity.index, rp_equity.values,
             label="RiskParity", color="#E53935", linewidth=2.5)

    ax1.set_title("Equity Curves (1999~)")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Equity (1.0 = start)")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Sharpe比較棒グラフ（RiskParityを強調）
    ax2 = axes[1]
    variants = list(PAIRS_H3) + ["EqualWeight", "RiskParity"]
    sharpes = [pair_results[p].metrics["sharpe"] for p in PAIRS_H3]
    sharpes.append(h3_data["ew_metrics"]["sharpe"])
    sharpes.append(h3_data["rp_metrics"]["sharpe"])

    bar_colors = [colors_pair[p] for p in PAIRS_H3] + ["#00ACC1", "#E53935"]
    bar_alphas = [0.7] * len(PAIRS_H3) + [0.8, 1.0]

    x = np.arange(len(variants))
    bars = ax2.bar(x, sharpes, color=bar_colors,
                   alpha=None)  # set alpha per bar below
    for bar, alpha in zip(bars, bar_alphas):
        bar.set_alpha(alpha)

    # RiskParityバーを太枠で強調
    bars[-1].set_edgecolor("black")
    bars[-1].set_linewidth(2.0)

    ax2.set_title("Sharpe Ratio Comparison")
    ax2.set_xticks(x)
    ax2.set_xticklabels(variants, rotation=20, ha="right")
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.set_ylabel("Sharpe Ratio")
    ax2.grid(True, alpha=0.3, axis="y")

    # バー上に値を表示
    for bar, val in zip(bars, sharpes):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.005 if val >= 0 else bar.get_height() - 0.005,
                 f"{val:.3f}", ha="center", va="bottom" if val >= 0 else "top", fontsize=9)

    plt.tight_layout()
    out_path = CHARTS_DIR / "phase5b_h3_portfolio.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  保存: {out_path}")


def plot_h3_correlation(h3_data: dict) -> None:
    """H3: 4ペア日次リターン相関行列ヒートマップ"""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    corr = h3_data["corr"]
    pairs = list(corr.columns)

    fig, ax = plt.subplots(figsize=(7, 6))
    ax.set_title("H3: Daily Returns Correlation Matrix\n(USDJPY / EURUSD / AUDUSD / USDCAD, 1999-2026)",
                 fontsize=11, pad=12)

    # imshow でヒートマップ（seabornなし）
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1.0, vmax=1.0, aspect="auto")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    n = len(pairs)
    ax.set_xticks(np.arange(n))
    ax.set_yticks(np.arange(n))
    ax.set_xticklabels(pairs, rotation=30, ha="right", fontsize=11)
    ax.set_yticklabels(pairs, fontsize=11)

    # 各セルに相関値を表示
    for i in range(n):
        for j in range(n):
            val = corr.values[i, j]
            text_color = "white" if abs(val) > 0.5 else "black"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=12, color=text_color, fontweight="bold")

    # グリッド線（セル境界）
    for edge in np.arange(-0.5, n, 1):
        ax.axhline(edge, color="white", linewidth=1.5)
        ax.axvline(edge, color="white", linewidth=1.5)

    plt.tight_layout()
    out_path = CHARTS_DIR / "phase5b_h3_correlation.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  保存: {out_path}")


# ─── CSV保存 ───────────────────────────────────────────────────────────────────

def save_results_csv(
    fixed: BacktestResult,
    dynamic: BacktestResult,
    h3_data: dict,
) -> None:
    """Phase 5B 結果を results/phase5b_results.csv に保存"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    rows = []

    # H2
    for result in [fixed, dynamic]:
        m = result.metrics
        rows.append({
            "phase": "H2",
            "variant": result.label,
            "sharpe": m["sharpe"],
            "cagr": m["cagr"],
            "worst_dd": m["worst_dd"],
            "calmar": m["calmar"],
            "n_trades": m["n_trades"],
        })

    # H3 個別ペア
    for pair, result in h3_data["results"].items():
        m = result.metrics
        rows.append({
            "phase": "H3",
            "variant": pair,
            "sharpe": m["sharpe"],
            "cagr": m["cagr"],
            "worst_dd": m["worst_dd"],
            "calmar": m["calmar"],
            "n_trades": m["n_trades"],
        })

    # H3 EqualWeight
    ew = h3_data["ew_metrics"]
    rows.append({
        "phase": "H3",
        "variant": "EqualWeight",
        "sharpe": ew["sharpe"],
        "cagr": ew["cagr"],
        "worst_dd": ew["worst_dd"],
        "calmar": ew["calmar"],
        "n_trades": ew["n_trades"],
    })

    # H3 RiskParity
    rp = h3_data["rp_metrics"]
    rows.append({
        "phase": "H3",
        "variant": "RiskParity",
        "sharpe": rp["sharpe"],
        "cagr": rp["cagr"],
        "worst_dd": rp["worst_dd"],
        "calmar": rp["calmar"],
        "n_trades": rp["n_trades"],
    })

    df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "phase5b_results.csv"
    df.to_csv(out_path, index=False)
    print(f"  保存: {out_path}")
    return df


# ─── メイン ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Phase 5B: 動的ポジションサイジング & 多通貨ポートフォリオ")
    print("=" * 60)

    # ─── H2: ボラティリティターゲティング ──────────────────────────────────────
    print("\n[H2] ボラティリティターゲティング検証")
    prices_usdjpy = fetch_fx(PAIR_H2)["close"]
    prices_usdjpy.index = pd.to_datetime(prices_usdjpy.index)
    base_signals = generate_signals(prices_usdjpy)

    fixed, dynamic = run_h2(prices_usdjpy, base_signals)

    print(f"\n  Fixed  (S2 1x):")
    print(f"    Sharpe={fixed.metrics['sharpe']:.3f}, CAGR={fixed.metrics['cagr']:.1%}, "
          f"MaxDD={fixed.metrics['worst_dd']:.1%}, Calmar={fixed.metrics['calmar']:.3f}, "
          f"Trades={fixed.metrics['n_trades']}")
    print(f"  Dynamic (Vol-Target):")
    print(f"    Sharpe={dynamic.metrics['sharpe']:.3f}, CAGR={dynamic.metrics['cagr']:.1%}, "
          f"MaxDD={dynamic.metrics['worst_dd']:.1%}, Calmar={dynamic.metrics['calmar']:.3f}, "
          f"Trades={dynamic.metrics['n_trades']}")

    print("\n  チャート生成中...")
    plot_h2(fixed, dynamic)

    # ─── H3: 多通貨ポートフォリオ ───────────────────────────────────────────────
    print("\n[H3] 多通貨ポートフォリオ検証")
    h3_data = run_h3()

    print("\n  個別ペア結果:")
    for pair, result in h3_data["results"].items():
        m = result.metrics
        print(f"    {pair}: Sharpe={m['sharpe']:.3f}, CAGR={m['cagr']:.1%}, "
              f"MaxDD={m['worst_dd']:.1%}")

    ew = h3_data["ew_metrics"]
    rp = h3_data["rp_metrics"]
    print(f"  EqualWeight : Sharpe={ew['sharpe']:.3f}, CAGR={ew['cagr']:.1%}, "
          f"MaxDD={ew['worst_dd']:.1%}, Calmar={ew['calmar']:.3f}")
    print(f"  RiskParity  : Sharpe={rp['sharpe']:.3f}, CAGR={rp['cagr']:.1%}, "
          f"MaxDD={rp['worst_dd']:.1%}, Calmar={rp['calmar']:.3f}")

    print("\n  相関行列:")
    print(h3_data["corr"].round(3).to_string())

    print("\n  チャート生成中...")
    plot_h3_portfolio(h3_data)
    plot_h3_correlation(h3_data)

    # ─── CSV保存 ──────────────────────────────────────────────────────────────
    print("\n[CSV] 結果保存中...")
    df_csv = save_results_csv(fixed, dynamic, h3_data)

    print("\n" + "=" * 60)
    print("Phase 5B 完了サマリー")
    print("=" * 60)
    print("\n[H2] Sharpe比較:")
    print(f"  Fixed 1x    : {fixed.metrics['sharpe']:.3f}")
    print(f"  DynVolTarget: {dynamic.metrics['sharpe']:.3f}  "
          f"{'↑改善' if dynamic.metrics['sharpe'] > fixed.metrics['sharpe'] else '↓悪化'}")

    print("\n[H3] Sharpe比較:")
    for pair, result in h3_data["results"].items():
        print(f"  {pair:8s}: {result.metrics['sharpe']:.3f}")
    print(f"  {'EqualWeight':8s}: {ew['sharpe']:.3f}")
    print(f"  {'RiskParity':8s}: {rp['sharpe']:.3f}  ← 注目")

    print("\n成果物:")
    print(f"  {RESULTS_DIR / 'phase5b_results.csv'}")
    print(f"  {CHARTS_DIR / 'phase5b_h2_sizing.png'}")
    print(f"  {CHARTS_DIR / 'phase5b_h3_portfolio.png'}")
    print(f"  {CHARTS_DIR / 'phase5b_h3_correlation.png'}")

    return df_csv


if __name__ == "__main__":
    main()
