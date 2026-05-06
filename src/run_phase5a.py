"""
run_phase5a.py — Phase 5A 検証スクリプト

H1: レバレッジ感度分析（カルマー比最大レバレッジの特定）
H4: MA200レジームフィルター（Sharpe改善・トレード削減）

実行:
    python -X utf8 src/run_phase5a.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

import matplotlib
matplotlib.use("Agg")  # GUI不要バックエンド

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

from data_fetcher import fetch_fx
from backtest_engine import run_backtest, BacktestResult
from strategies.atr_breakout import generate_signals

# ─── 設定 ─────────────────────────────────────────────────────────────────────

PAIR = "USDJPY"
START = "1990-01-01"

LEVERAGE_RANGE = [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0]

RESULTS_DIR = Path(__file__).parent.parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── 日本語フォント設定 ────────────────────────────────────────────────────────

_jp_candidates = ["MS Gothic", "Meiryo", "Yu Gothic", "DejaVu Sans"]

def _get_jp_font() -> str:
    available = {f.name for f in fm.fontManager.ttflist}
    for candidate in _jp_candidates:
        if candidate in available:
            return candidate
    return "DejaVu Sans"

_jp_font = _get_jp_font()
plt.rcParams["font.family"] = _jp_font
plt.rcParams["axes.unicode_minus"] = False

print(f"[INFO] 使用フォント: {_jp_font}")


# ─── H1: レバレッジ感度分析 ──────────────────────────────────────────────────

def run_h1(
    prices: pd.Series,
    base_signals: pd.Series,
    pair: str = PAIR,
    start: str = START,
) -> pd.DataFrame:
    """
    各レバレッジでバックテストを実行し、評価指標をDataFrameで返す。

    Returns
    -------
    pd.DataFrame  columns=[leverage, cagr, worst_dd, calmar, sharpe]
    """
    print("\n[H1] レバレッジ感度分析 開始...")
    rows = []
    for lev in LEVERAGE_RANGE:
        result = run_backtest(
            prices,
            base_signals,
            pair=pair,
            label=f"S2_lev{lev}",
            leverage=lev,
            start=start,
        )
        m = result.metrics
        rows.append({
            "leverage": lev,
            "cagr":     m["cagr"],
            "worst_dd": m["worst_dd"],
            "calmar":   m["calmar"],
            "sharpe":   m["sharpe"],
        })
        print(
            f"  lev={lev:5.1f}x | CAGR={m['cagr']:+.2%} "
            f"| MaxDD={m['worst_dd']:.2%} | Calmar={m['calmar']:.3f} "
            f"| Sharpe={m['sharpe']:.3f}"
        )
    df = pd.DataFrame(rows)
    print("[H1] 完了")
    return df


# ─── H4: MA200レジームフィルター ─────────────────────────────────────────────

def apply_ma200_filter(
    prices: pd.Series,
    signals: pd.Series,
    mode: str = "simple",
) -> pd.Series:
    """
    MA200レジームフィルターをシグナルに適用する（ループなし・ベクタライズ）。

    Parameters
    ----------
    prices  : pd.Series  日次終値
    signals : pd.Series  S2の出力シグナル（-1/0/+1）
    mode    : str
        "simple" : price > MA200 → Long許可、price < MA200 → Short許可
        "slope"  : + MA200の20日傾き条件（上昇傾きならLong、下降傾きならShort）

    Returns
    -------
    pd.Series  フィルター適用済みシグナル（-1/0/+1）
    """
    # MA200: その日の終値で計算（lookahead bias なし）
    ma200 = prices.rolling(200, min_periods=200).mean()

    # MA200の20日傾き: (今日のMA200 - 20日前のMA200) / 20日前のMA200
    ma200_slope = ma200.pct_change(20)  # 20日変化率

    filtered = signals.copy()

    if mode == "simple":
        # Long許可: price > MA200 のみ
        long_ok = prices > ma200
        # Short許可: price < MA200 のみ
        short_ok = prices < ma200

        # Longシグナルで許可外 → Flat
        filtered = filtered.where(~((filtered == 1) & ~long_ok), other=0)
        # Shortシグナルで許可外 → Flat
        filtered = filtered.where(~((filtered == -1) & ~short_ok), other=0)

    elif mode == "slope":
        # Long許可: price > MA200 かつ MA200が0.1%以上の上昇傾き
        long_ok = (prices > ma200) & (ma200_slope >= 0.001)
        # Short許可: price < MA200 かつ MA200が0.1%以上の下降傾き（負の傾き）
        short_ok = (prices < ma200) & (ma200_slope <= -0.001)

        # Longシグナルで許可外 → Flat
        filtered = filtered.where(~((filtered == 1) & ~long_ok), other=0)
        # Shortシグナルで許可外 → Flat
        filtered = filtered.where(~((filtered == -1) & ~short_ok), other=0)

    else:
        raise ValueError(f"未対応mode: {mode}. 'simple' または 'slope' を指定してください。")

    return filtered


def run_h4(
    prices: pd.Series,
    base_signals: pd.Series,
    pair: str = PAIR,
    start: str = START,
) -> tuple[dict[str, BacktestResult], pd.DataFrame]:
    """
    MA200フィルターの2バリアントを実行し、結果を返す。

    Returns
    -------
    results_dict : dict[str, BacktestResult]
    metrics_df   : pd.DataFrame  variant別評価指標
    """
    print("\n[H4] MA200レジームフィルター検証 開始...")

    variants = {}

    # ベースライン: S2 Base
    result_base = run_backtest(
        prices, base_signals,
        pair=pair, label="S2_Base",
        leverage=1.0, start=start,
    )
    variants["S2_Base"] = result_base

    # S2 + MA200 simple
    sig_simple = apply_ma200_filter(prices, base_signals, mode="simple")
    result_simple = run_backtest(
        prices, sig_simple,
        pair=pair, label="S2+MA200",
        leverage=1.0, start=start,
    )
    variants["S2+MA200"] = result_simple

    # S2 + MA200 + Slope
    sig_slope = apply_ma200_filter(prices, base_signals, mode="slope")
    result_slope = run_backtest(
        prices, sig_slope,
        pair=pair, label="S2+MA200+Slope",
        leverage=1.0, start=start,
    )
    variants["S2+MA200+Slope"] = result_slope

    # 結果表示
    rows = []
    for name, res in variants.items():
        m = res.metrics
        print(
            f"  {name:20s} | Sharpe={m['sharpe']:.3f} | CAGR={m['cagr']:+.2%} "
            f"| MaxDD={m['worst_dd']:.2%} | Calmar={m['calmar']:.3f} | Trades={m['n_trades']}"
        )
        rows.append({
            "variant":  name,
            "sharpe":   m["sharpe"],
            "cagr":     m["cagr"],
            "worst_dd": m["worst_dd"],
            "calmar":   m["calmar"],
            "n_trades": m["n_trades"],
        })

    metrics_df = pd.DataFrame(rows)
    print("[H4] 完了")
    return variants, metrics_df


# ─── チャート作成 ─────────────────────────────────────────────────────────────

def plot_h1(df: pd.DataFrame) -> None:
    """H1レバレッジ感度分析の3パネルチャートを保存。"""
    best_idx = df["calmar"].idxmax()
    best_lev = df.loc[best_idx, "leverage"]

    fig, axes = plt.subplots(3, 1, figsize=(10, 12))
    fig.suptitle("Phase 5A H1: レバレッジ感度分析", fontsize=14, fontweight="bold")

    leverages = df["leverage"].values
    x = np.arange(len(leverages))
    labels = [f"{l}x" for l in leverages]

    # Panel 1: CAGR
    ax1 = axes[0]
    colors1 = ["tomato" if lev == best_lev else "steelblue" for lev in leverages]
    bars1 = ax1.bar(x, df["cagr"] * 100, color=colors1, edgecolor="white", linewidth=0.5)
    ax1.set_title("CAGR (%) vs Leverage")
    ax1.set_ylabel("CAGR (%)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.axhline(0, color="black", linewidth=0.8, linestyle="--")
    for bar, val in zip(bars1, df["cagr"]):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            f"{val:.1%}",
            ha="center", va="bottom", fontsize=8,
        )

    # Panel 2: MaxDD
    ax2 = axes[1]
    colors2 = ["tomato" if lev == best_lev else "coral" for lev in leverages]
    bars2 = ax2.bar(x, df["worst_dd"] * 100, color=colors2, edgecolor="white", linewidth=0.5)
    ax2.set_title("MaxDD (%) vs Leverage")
    ax2.set_ylabel("MaxDD (%)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    for bar, val in zip(bars2, df["worst_dd"]):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() - 0.5,
            f"{val:.1%}",
            ha="center", va="top", fontsize=8, color="white",
        )

    # Panel 3: Calmar（最大点に赤マーカー）
    ax3 = axes[2]
    colors3 = ["steelblue"] * len(leverages)
    bars3 = ax3.bar(x, df["calmar"], color=colors3, edgecolor="white", linewidth=0.5)
    # 最大点を赤マーカーで強調
    ax3.bar(
        x[best_idx], df.loc[best_idx, "calmar"],
        color="red", edgecolor="darkred", linewidth=1.5, label=f"最大 lev={best_lev}x",
    )
    ax3.set_title("Calmar Ratio vs Leverage")
    ax3.set_ylabel("Calmar Ratio")
    ax3.set_xticks(x)
    ax3.set_xticklabels(labels)
    ax3.legend()
    for bar, val in zip(bars3, df["calmar"]):
        ax3.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.001,
            f"{val:.3f}",
            ha="center", va="bottom", fontsize=8,
        )

    fig.tight_layout()
    out_path = CHARTS_DIR / "phase5a_h1_leverage.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"[Chart] H1チャート保存: {out_path}")


def plot_h4(variants: dict[str, BacktestResult], metrics_df: pd.DataFrame) -> None:
    """H4レジームフィルターの2パネルチャートを保存。"""
    fig, axes = plt.subplots(2, 1, figsize=(12, 12))
    fig.suptitle("Phase 5A H4: MA200レジームフィルター", fontsize=14, fontweight="bold")

    # Panel 1: エクイティカーブ比較
    ax1 = axes[0]
    colors_ec = {"S2_Base": "steelblue", "S2+MA200": "darkorange", "S2+MA200+Slope": "green"}
    for name, res in variants.items():
        # start以降のエクイティを1.0に正規化
        eq = res.equity
        eq_norm = eq / eq.iloc[0]
        ax1.plot(eq_norm.index, eq_norm.values, label=name, color=colors_ec.get(name), linewidth=1.2)

    ax1.set_title("エクイティカーブ比較 (1990年〜)")
    ax1.set_ylabel("エクイティ (正規化)")
    ax1.set_xlabel("")
    ax1.legend()
    ax1.axhline(1.0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax1.grid(True, alpha=0.3)

    # Panel 2: Sharpe/CAGR/MaxDD/Calmar/Trades の棒グラフ比較
    ax2 = axes[1]
    variants_list = metrics_df["variant"].tolist()
    n_variants = len(variants_list)
    metrics_to_plot = ["sharpe", "cagr", "worst_dd", "calmar"]
    metric_labels = ["Sharpe", "CAGR (%)", "MaxDD (%)", "Calmar"]

    x = np.arange(n_variants)
    width = 0.2
    colors_bar = ["steelblue", "darkorange", "green", "purple"]

    for i, (col, label) in enumerate(zip(metrics_to_plot, metric_labels)):
        values = metrics_df[col].values
        # CAGR・MaxDDはパーセント表示
        if col in ("cagr", "worst_dd"):
            display_vals = values * 100
        else:
            display_vals = values
        offset = (i - len(metrics_to_plot) / 2 + 0.5) * width
        bars = ax2.bar(x + offset, display_vals, width, label=label, color=colors_bar[i], alpha=0.85)
        for bar, val in zip(bars, display_vals):
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.005 if bar.get_height() >= 0 else bar.get_height() - 0.1,
                f"{val:.2f}",
                ha="center", va="bottom" if bar.get_height() >= 0 else "top",
                fontsize=7,
            )

    # トレード回数を第2軸
    ax2b = ax2.twinx()
    ax2b.plot(x, metrics_df["n_trades"].values, "D--", color="black", label="Trades", markersize=8, linewidth=1.5)
    ax2b.set_ylabel("Trades (#)", color="black")
    ax2b.tick_params(axis="y", labelcolor="black")
    for xi, val in zip(x, metrics_df["n_trades"].values):
        ax2b.text(xi, val + 2, str(val), ha="center", va="bottom", fontsize=8, color="black")

    ax2.set_title("指標比較: S2_Base vs S2+MA200 vs S2+MA200+Slope")
    ax2.set_ylabel("指標値")
    ax2.set_xticks(x)
    ax2.set_xticklabels(variants_list, fontsize=9)
    ax2.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)

    # 凡例をまとめる
    handles1, labels1 = ax2.get_legend_handles_labels()
    handles2, labels2 = ax2b.get_legend_handles_labels()
    ax2.legend(handles1 + handles2, labels1 + labels2, loc="upper right", fontsize=8)

    fig.tight_layout()
    out_path = CHARTS_DIR / "phase5a_h4_regime.png"
    fig.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"[Chart] H4チャート保存: {out_path}")


# ─── CSV出力 ──────────────────────────────────────────────────────────────────

def save_results_csv(h1_df: pd.DataFrame, h4_df: pd.DataFrame) -> None:
    """H1・H4結果をresults/phase5a_results.csvに保存。"""
    # H1: leverage, cagr, worst_dd, calmar, sharpe
    h1_out = h1_df[["leverage", "cagr", "worst_dd", "calmar", "sharpe"]].copy()
    h1_out.insert(0, "section", "H1_leverage")

    # H4: variant, sharpe, cagr, worst_dd, calmar, n_trades
    h4_out = h4_df[["variant", "sharpe", "cagr", "worst_dd", "calmar", "n_trades"]].copy()
    h4_out.insert(0, "section", "H4_regime")
    h4_out.rename(columns={"variant": "leverage"}, inplace=True)

    # 結合（列を合わせる）
    combined = pd.concat([h1_out, h4_out], ignore_index=True)

    out_path = RESULTS_DIR / "phase5a_results.csv"
    combined.to_csv(out_path, index=False)
    print(f"[CSV] 結果保存: {out_path}")


# ─── メイン ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Phase 5A 検証スクリプト")
    print("=" * 60)

    # データ取得
    print(f"\n[DATA] {PAIR} データ取得中...")
    prices = fetch_fx(PAIR)["close"]
    prices.index = pd.to_datetime(prices.index)
    print(f"[DATA] 取得完了: {prices.index.min().date()} 〜 {prices.index.max().date()} ({len(prices)}行)")

    # ベースシグナル生成（S2 ATRブレイクアウト）
    print("\n[SIGNAL] S2ベースシグナル生成中...")
    base_signals = generate_signals(prices)
    n_active = (base_signals != 0).sum()
    print(f"[SIGNAL] 生成完了: アクティブ日数={n_active}日")

    # H1: レバレッジ感度分析
    h1_df = run_h1(prices, base_signals, pair=PAIR, start=START)

    # H4: MA200レジームフィルター
    h4_variants, h4_df = run_h4(prices, base_signals, pair=PAIR, start=START)

    # チャート保存
    print("\n[CHART] チャート生成中...")
    plot_h1(h1_df)
    plot_h4(h4_variants, h4_df)

    # CSV保存
    save_results_csv(h1_df, h4_df)

    # サマリー表示
    print("\n" + "=" * 60)
    print("Phase 5A 検証完了 — 結果サマリー")
    print("=" * 60)

    print("\n[H1] レバレッジ感度分析:")
    best_idx = h1_df["calmar"].idxmax()
    best = h1_df.loc[best_idx]
    print(f"  カルマー最大レバレッジ: {best['leverage']}x  (Calmar={best['calmar']:.3f})")
    print(h1_df.to_string(index=False))

    print("\n[H4] MA200レジームフィルター:")
    print(h4_df.to_string(index=False))

    print("\n[出力ファイル]")
    print(f"  チャート: {CHARTS_DIR}/phase5a_h1_leverage.png")
    print(f"  チャート: {CHARTS_DIR}/phase5a_h4_regime.png")
    print(f"  CSV    : {RESULTS_DIR}/phase5a_results.csv")
    print("\n[完了] Phase 5A 全検証終了")


if __name__ == "__main__":
    main()
