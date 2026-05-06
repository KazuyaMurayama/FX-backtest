"""
run_phase6a.py — Phase 6A 検証スクリプト

目的: USD/JPY より高ボラの SBI 取引可能クロス円ペアで
      S2 ATRブレイクアウト + H4 MA200+Slope フィルターを適用し、
      USD/JPYとの Sharpe/CAGR/MaxDD 比較を行う。

対象ペア:
  - USD/JPY (基準・再掲)
  - NZD/JPY (σ11.5%, キャリー+トレンド)
  - GBP/JPY (σ12.0%, 高ボラ・トレンド継続)

価格データ: FRED合成
  - NZD/JPY = NZD/USD (DEXUSNZ) × USD/JPY (DEXJPUS)
  - GBP/JPY = GBP/USD (DEXUSUK) × USD/JPY (DEXJPUS)
  → 1971年〜の長期データが利用可能

実行:
    python -X utf8 src/run_phase6a.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

from data_fetcher import fetch_fx
from backtest_engine import run_backtest, BacktestResult
from strategies.atr_breakout import generate_signals

# ─── 設定 ─────────────────────────────────────────────────────────────────────

START = "1990-01-01"   # Phase5Aと共通開始日

PAIRS = ["USDJPY", "NZDJPY", "GBPJPY"]

RESULTS_DIR = Path(__file__).parent.parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── 日本語フォント設定 ────────────────────────────────────────────────────────

_jp_candidates = ["MS Gothic", "Meiryo", "Yu Gothic", "DejaVu Sans"]

def _get_jp_font() -> str:
    available = {f.name for f in fm.fontManager.ttflist}
    for c in _jp_candidates:
        if c in available:
            return c
    return "DejaVu Sans"

_jp_font = _get_jp_font()
plt.rcParams["font.family"] = _jp_font
plt.rcParams["axes.unicode_minus"] = False


# ─── クロス円価格データ合成 ───────────────────────────────────────────────────

def build_cross_jpy(base_usd_pair: str) -> pd.Series:
    """
    FREDデータから JPYクロスレートを合成する。
    base_usd_pair: 例 'NZDUSD', 'GBPUSD', 'AUDUSD'
    戻り値: base/JPY の日次終値 Series（1990年〜）
    """
    usd_jpy = fetch_fx("USDJPY")["close"]
    base_usd = fetch_fx(base_usd_pair)["close"]

    # base/JPY = base/USD × USD/JPY
    cross = (base_usd * usd_jpy).dropna()
    cross.index = pd.to_datetime(cross.index)
    usd_jpy.index = pd.to_datetime(usd_jpy.index)

    # 共通インデックスに揃える
    idx = cross.index.intersection(usd_jpy.index)
    return cross.loc[idx].rename("close")


def load_prices(pair: str) -> pd.Series:
    """ペア名からprice Seriesを返す（クロス円は合成）。"""
    if pair == "USDJPY":
        prices = fetch_fx("USDJPY")["close"]
        prices.index = pd.to_datetime(prices.index)
        return prices
    elif pair == "NZDJPY":
        return build_cross_jpy("NZDUSD")
    elif pair == "GBPJPY":
        return build_cross_jpy("GBPUSD")
    elif pair == "AUDJPY":
        return build_cross_jpy("AUDUSD")
    elif pair == "EURJPY":
        return build_cross_jpy("EURUSD")
    else:
        raise ValueError(f"未対応ペア: {pair}")


# ─── MA200 + Slope フィルター（Phase5Aと同一ロジック）────────────────────────

def apply_ma200_filter(prices: pd.Series, signals: pd.Series, mode: str = "slope") -> pd.Series:
    ma200 = prices.rolling(200, min_periods=200).mean()
    ma200_slope = ma200.pct_change(20)
    filtered = signals.copy()

    if mode == "simple":
        long_ok  = prices > ma200
        short_ok = prices < ma200
        filtered = filtered.where(~((filtered == 1)  & ~long_ok),  other=0)
        filtered = filtered.where(~((filtered == -1) & ~short_ok), other=0)

    elif mode == "slope":
        long_ok  = (prices > ma200) & (ma200_slope >= 0.001)
        short_ok = (prices < ma200) & (ma200_slope <= -0.001)
        filtered = filtered.where(~((filtered == 1)  & ~long_ok),  other=0)
        filtered = filtered.where(~((filtered == -1) & ~short_ok), other=0)

    return filtered


# ─── 1ペアの全バリアント実行 ─────────────────────────────────────────────────

def run_pair(pair: str, start: str = START) -> dict[str, dict]:
    """
    1ペアについて3バリアント（Base, MA200, MA200+Slope）を実行。
    Returns: {variant_name: metrics_dict}
    """
    print(f"\n[{pair}] データ準備...")
    prices = load_prices(pair)
    print(f"  価格取得: {prices.index.min().date()} 〜 {prices.index.max().date()} ({len(prices)}行)")

    base_signals = generate_signals(prices)
    sig_ma200       = apply_ma200_filter(prices, base_signals, mode="simple")
    sig_ma200_slope = apply_ma200_filter(prices, base_signals, mode="slope")

    results = {}
    variants = [
        ("S2_Base",        base_signals),
        ("S2+MA200",       sig_ma200),
        ("S2+MA200+Slope", sig_ma200_slope),
    ]

    for name, sig in variants:
        res = run_backtest(prices, sig, pair=pair, label=name, leverage=1.0, start=start)
        m = res.metrics
        results[name] = {
            "pair":     pair,
            "variant":  name,
            "sharpe":   m["sharpe"],
            "cagr":     m["cagr"],
            "worst_dd": m["worst_dd"],
            "calmar":   m["calmar"],
            "n_trades": m["n_trades"],
            "equity":   res.equity,
        }
        print(
            f"  {name:20s} | Sharpe={m['sharpe']:+.3f} | CAGR={m['cagr']:+.2%} "
            f"| MaxDD={m['worst_dd']:.2%} | Trades={m['n_trades']}"
        )
    return results


# ─── チャート: ペア×バリアント エクイティカーブ ────────────────────────────────

def plot_equity_curves(all_results: dict[str, dict[str, dict]]) -> None:
    """
    3ペア × 3バリアントのエクイティカーブを3×1パネルで描画。
    """
    fig, axes = plt.subplots(3, 1, figsize=(13, 15), sharex=False)
    fig.suptitle("Phase 6A: S2 + MA200+Slope フィルター — クロス円ペア比較", fontsize=14, fontweight="bold")

    pair_labels = {"USDJPY": "USD/JPY (基準)", "NZDJPY": "NZD/JPY (σ11.5%)", "GBPJPY": "GBP/JPY (σ12.0%)"}
    colors = {"S2_Base": "steelblue", "S2+MA200": "darkorange", "S2+MA200+Slope": "green"}
    ls     = {"S2_Base": "-",         "S2+MA200": "--",          "S2+MA200+Slope": "-"}
    lw     = {"S2_Base": 1.0,         "S2+MA200": 1.2,           "S2+MA200+Slope": 1.8}

    for ax, pair in zip(axes, PAIRS):
        variants = all_results[pair]
        for vname, vdata in variants.items():
            eq = vdata["equity"]
            eq_norm = eq / eq.iloc[0]
            m = vdata
            label = (
                f"{vname} | Sharpe={m['sharpe']:+.3f} | "
                f"CAGR={m['cagr']:+.2%} | MaxDD={m['worst_dd']:.1%}"
            )
            ax.plot(eq_norm.index, eq_norm.values,
                    color=colors[vname], linestyle=ls[vname], linewidth=lw[vname],
                    label=label, alpha=0.9)

        ax.set_title(pair_labels.get(pair, pair), fontsize=11, fontweight="bold")
        ax.set_ylabel("エクイティ (正規化)")
        ax.axhline(1.0, color="black", linewidth=0.7, linestyle=":", alpha=0.5)
        ax.legend(fontsize=7.5, loc="upper left")
        ax.grid(True, alpha=0.25)

    axes[-1].set_xlabel("年")
    fig.tight_layout()
    out = CHARTS_DIR / "phase6a_equity_curves.png"
    fig.savefig(out, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"\n[Chart] エクイティカーブ保存: {out}")


# ─── チャート: ペア×バリアント Sharpe/CAGR/MaxDD 棒グラフ比較 ─────────────────

def plot_metrics_comparison(rows: list[dict]) -> None:
    """
    3ペア × 3バリアントの Sharpe/CAGR/MaxDD を並べた棒グラフ。
    """
    df = pd.DataFrame(rows)

    metrics = [
        ("sharpe",   "Sharpe Ratio",  False),
        ("cagr",     "CAGR (%)",      True),
        ("worst_dd", "MaxDD (%)",     True),
    ]
    pair_order = ["USDJPY", "NZDJPY", "GBPJPY"]
    var_order  = ["S2_Base", "S2+MA200", "S2+MA200+Slope"]
    var_colors = ["steelblue", "darkorange", "green"]
    pair_labels = {"USDJPY": "USD/JPY", "NZDJPY": "NZD/JPY", "GBPJPY": "GBP/JPY"}

    fig, axes = plt.subplots(1, 3, figsize=(16, 6))
    fig.suptitle("Phase 6A: ペア別 指標比較 (S2 Base vs MA200 vs MA200+Slope)", fontsize=13, fontweight="bold")

    x = np.arange(len(pair_order))
    width = 0.22

    for ax, (col, ylabel, pct) in zip(axes, metrics):
        for i, (var, color) in enumerate(zip(var_order, var_colors)):
            vals = []
            for pair in pair_order:
                row = df[(df["pair"] == pair) & (df["variant"] == var)]
                v = float(row[col].values[0]) if len(row) > 0 else np.nan
                vals.append(v * 100 if pct else v)

            offset = (i - 1) * width
            bars = ax.bar(x + offset, vals, width, label=var, color=color, alpha=0.85, edgecolor="white")

            for bar, val in zip(bars, vals):
                if not np.isnan(val):
                    va = "bottom" if val >= 0 else "top"
                    yoff = 0.01 if val >= 0 else -0.01
                    ax.text(bar.get_x() + bar.get_width() / 2,
                            bar.get_height() + yoff,
                            f"{val:.2f}", ha="center", va=va, fontsize=7.5)

        ax.set_title(ylabel, fontsize=11)
        ax.set_ylabel(ylabel)
        ax.set_xticks(x)
        ax.set_xticklabels([pair_labels[p] for p in pair_order])
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.legend(fontsize=8)
        ax.grid(True, axis="y", alpha=0.25)

    fig.tight_layout()
    out = CHARTS_DIR / "phase6a_metrics_comparison.png"
    fig.savefig(out, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"[Chart] 指標比較チャート保存: {out}")


# ─── チャート: MA200+Slope適用後 Best 3 バリアントの累積リターン ───────────────

def plot_best_overlay(all_results: dict[str, dict[str, dict]]) -> None:
    """
    各ペアの MA200+Slope 適用後エクイティを1枚に重ね描き（最良比較）。
    """
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.set_title("Phase 6A: S2+MA200+Slope — 3ペア最良バリアント比較", fontsize=13, fontweight="bold")

    pair_labels = {"USDJPY": "USD/JPY", "NZDJPY": "NZD/JPY", "GBPJPY": "GBP/JPY"}
    colors = {"USDJPY": "steelblue", "NZDJPY": "darkorange", "GBPJPY": "green"}

    for pair in PAIRS:
        vdata = all_results[pair]["S2+MA200+Slope"]
        eq = vdata["equity"]
        eq_norm = eq / eq.iloc[0]
        m = vdata
        label = (
            f"{pair_labels[pair]} | Sharpe={m['sharpe']:+.3f} | "
            f"CAGR={m['cagr']:+.2%} | MaxDD={m['worst_dd']:.1%} | Trades={m['n_trades']}"
        )
        ax.plot(eq_norm.index, eq_norm.values, color=colors[pair], linewidth=1.8, label=label)

    ax.axhline(1.0, color="black", linewidth=0.7, linestyle=":", alpha=0.5)
    ax.set_ylabel("エクイティ (正規化)")
    ax.set_xlabel("年")
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.25)

    fig.tight_layout()
    out = CHARTS_DIR / "phase6a_best_overlay.png"
    fig.savefig(out, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"[Chart] ベストバリアント重ね描き保存: {out}")


# ─── CSV保存 ──────────────────────────────────────────────────────────────────

def save_results_csv(rows: list[dict]) -> None:
    df = pd.DataFrame([{k: v for k, v in r.items() if k != "equity"} for r in rows])
    out = RESULTS_DIR / "phase6a_results.csv"
    df.to_csv(out, index=False)
    print(f"[CSV] 結果保存: {out}")


# ─── メイン ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Phase 6A — クロス円ペア S2+H4 検証")
    print("=" * 60)
    print(f"対象ペア: {PAIRS}")
    print(f"開始日  : {START}")

    all_results: dict[str, dict[str, dict]] = {}
    all_rows: list[dict] = []

    for pair in PAIRS:
        results = run_pair(pair, start=START)
        all_results[pair] = results
        all_rows.extend(results.values())

    # チャート生成
    print("\n[CHART] チャート生成中...")
    plot_equity_curves(all_results)
    plot_metrics_comparison(all_rows)
    plot_best_overlay(all_results)

    # CSV保存
    save_results_csv(all_rows)

    # サマリー表示
    print("\n" + "=" * 60)
    print("Phase 6A 完了 — サマリー")
    print("=" * 60)

    df_sum = pd.DataFrame([{k: v for k, v in r.items() if k != "equity"} for r in all_rows])
    df_slope = df_sum[df_sum["variant"] == "S2+MA200+Slope"].copy()
    df_slope = df_slope[["pair", "sharpe", "cagr", "worst_dd", "calmar", "n_trades"]]

    print("\n[S2+MA200+Slope フィルター適用後 最終比較]")
    for _, row in df_slope.iterrows():
        print(
            f"  {row['pair']:8s} | Sharpe={row['sharpe']:+.3f} | CAGR={row['cagr']:+.2%} "
            f"| MaxDD={row['worst_dd']:.2%} | Calmar={row['calmar']:.3f} | Trades={int(row['n_trades'])}"
        )

    print("\n成果物:")
    print(f"  results/charts/phase6a_equity_curves.png")
    print(f"  results/charts/phase6a_metrics_comparison.png")
    print(f"  results/charts/phase6a_best_overlay.png")
    print(f"  results/phase6a_results.csv")
    print("\n[完了] Phase 6A 全検証終了")


if __name__ == "__main__":
    main()
