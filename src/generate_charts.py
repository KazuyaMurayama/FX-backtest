"""
generate_charts.py -- 全戦略の資産曲線・ドローダウン・指標比較グラフを生成。

出力:
  results/charts/01_equity_curves.png   -- 全戦略エクイティカーブ
  results/charts/02_drawdowns.png       -- ドローダウン推移
  results/charts/03_metrics_bar.png     -- Sharpe/CAGR/MaxDD 比較棒グラフ
  results/charts/04_top3_detail.png     -- 上位3戦略の詳細

実行: python -X utf8 src/generate_charts.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# ── フォント設定（Windows / cross-platform）
import matplotlib.font_manager as fm
_jp_candidates = ["MS Gothic", "Meiryo", "Yu Gothic", "IPAexGothic",
                  "Noto Sans CJK JP", "DejaVu Sans"]
_avail = {f.name for f in fm.fontManager.ttflist}
_chosen = next((f for f in _jp_candidates if f in _avail), "DejaVu Sans")
plt.rcParams["font.family"] = _chosen
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150

CHARTS_DIR = Path(__file__).parent.parent / "results" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ── カラーパレット（戦略別）
COLORS = {
    "S1: MAcross(50/200)":    "#2196F3",
    "S2: ATR Breakout":       "#4CAF50",
    "S3: Carry(USDJPY)":      "#F44336",
    "S3b: Carry(AUDUSD)":     "#FF9800",
    "S3c: Carry(NZDUSD)":     "#FFC107",
    "S4: RSI Reversal":       "#9C27B0",
    "S5: BB MeanRev":         "#795548",
    "S6: DCA(USDJPY)":        "#607D8B",
    "BnH USDJPY(baseline)":   "#9E9E9E",
}


def get_all_results():
    """全戦略を実行してBacktestResultのリストを返す。"""
    from strategies.ma_crossover import run as run_ma
    from strategies.atr_breakout import run as run_atr
    from strategies.carry_trade import run as run_carry
    from strategies.rsi_reversal import run as run_rsi
    from strategies.bollinger_band import run as run_bb
    from strategies.dca import run as run_dca
    from backtest_engine import run_backtest
    from data_fetcher import fetch_fx

    configs = [
        ("S1: MAcross(50/200)",  run_ma,    {"pair":"USDJPY","start":"1990-01-01"}),
        ("S2: ATR Breakout",     run_atr,   {"pair":"USDJPY","start":"1990-01-01"}),
        ("S3: Carry(USDJPY)",    run_carry, {"pair":"USDJPY","start":"1990-01-01"}),
        ("S3b: Carry(AUDUSD)",   run_carry, {"pair":"AUDUSD","start":"1990-08-01"}),
        ("S3c: Carry(NZDUSD)",   run_carry, {"pair":"NZDUSD","start":"1990-01-01"}),
        ("S4: RSI Reversal",     run_rsi,   {"pair":"USDJPY","start":"1990-01-01"}),
        ("S5: BB MeanRev",       run_bb,    {"pair":"USDJPY","start":"1990-01-01"}),
        ("S6: DCA(USDJPY)",      run_dca,   {"pair":"USDJPY","start":"1990-01-01"}),
    ]

    # BnH: 常時ロング
    prices_bnh = fetch_fx("USDJPY")["close"]
    sig_bnh = pd.Series(1.0, index=prices_bnh.index)
    bnh = run_backtest(prices_bnh, sig_bnh, pair="USDJPY",
                       label="BnH USDJPY(baseline)", start="1990-01-01")

    results = []
    for label, fn, kw in configs:
        try:
            r = fn(**kw)
            r.label = label
            results.append(r)
            print(f"  OK: {label}")
        except Exception as e:
            print(f"  NG: {label} -- {e}")

    bnh.label = "BnH USDJPY(baseline)"
    results.append(bnh)
    return results


# ── Chart 1: エクイティカーブ比較 ────────────────────────────────────────────

def plot_equity_curves(results, save_path):
    fig, ax = plt.subplots(figsize=(14, 7))

    for r in results:
        eq = r.equity
        color = COLORS.get(r.label, "#333333")
        lw = 2.5 if r.label in ("S2: ATR Breakout", "S3b: Carry(AUDUSD)") else 1.0
        alpha = 1.0 if r.label in ("S2: ATR Breakout", "S3b: Carry(AUDUSD)",
                                    "BnH USDJPY(baseline)") else 0.55
        ls = "--" if r.label == "BnH USDJPY(baseline)" else "-"
        ax.plot(eq.index, eq.values, color=color, lw=lw, alpha=alpha, ls=ls,
                label=f"{r.label}  (Sharpe={r.metrics['sharpe']:.3f})")

    ax.axhline(1.0, color="black", lw=0.8, ls=":")
    ax.set_title("FX Backtest: Equity Curves (1990-2026, Leverage 1x, USD/JPY basis)",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Equity (1.0 = initial)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.legend(fontsize=8, loc="upper left", framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}"))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path.name}")


# ── Chart 2: ドローダウン比較 ────────────────────────────────────────────────

def plot_drawdowns(results, save_path):
    fig, ax = plt.subplots(figsize=(14, 6))

    for r in results:
        dd = r.drawdowns
        color = COLORS.get(r.label, "#333333")
        lw = 2.0 if r.label in ("S2: ATR Breakout", "S3b: Carry(AUDUSD)") else 0.8
        alpha = 1.0 if r.label in ("S2: ATR Breakout", "S3b: Carry(AUDUSD)",
                                    "BnH USDJPY(baseline)") else 0.45
        ls = "--" if r.label == "BnH USDJPY(baseline)" else "-"
        ax.plot(dd.index, dd.values * 100, color=color, lw=lw, alpha=alpha, ls=ls,
                label=f"{r.label}  (MaxDD={r.metrics['worst_dd']:.1%})")

    ax.axhline(0, color="black", lw=0.8, ls=":")
    ax.fill_between(results[0].drawdowns.index,
                    results[0].drawdowns.values * 0, -100,
                    alpha=0.03, color="red")
    ax.set_title("FX Backtest: Drawdown Comparison (1990-2026)",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("Drawdown (%)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.legend(fontsize=8, loc="lower left", framealpha=0.9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path.name}")


# ── Chart 3: 評価指標比較棒グラフ ────────────────────────────────────────────

def plot_metrics_bar(results, save_path):
    labels = [r.label.replace("(", "\n(") for r in results]
    sharpes = [r.metrics["sharpe"] for r in results]
    cagrs   = [r.metrics["cagr"] * 100 for r in results]
    dds     = [r.metrics["worst_dd"] * 100 for r in results]

    x = np.arange(len(labels))
    w = 0.26

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle("FX Backtest: Strategy Comparison (1990-2026)",
                 fontsize=14, fontweight="bold")

    def bar_colors(vals, higher_better=True):
        cmap = plt.cm.RdYlGn if higher_better else plt.cm.RdYlGn_r
        norm_v = np.array(vals, dtype=float)
        vmin, vmax = norm_v.min(), norm_v.max()
        if vmax == vmin:
            return ["#aaaaaa"] * len(vals)
        normalized = (norm_v - vmin) / (vmax - vmin)
        return [cmap(v) for v in normalized]

    # Sharpe
    ax = axes[0]
    colors = bar_colors(sharpes)
    bars = ax.bar(x, sharpes, color=colors, edgecolor="white", lw=0.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Sharpe Ratio", fontsize=12, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
    ax.yaxis.grid(True, alpha=0.3)
    for bar, v in zip(bars, sharpes):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{v:.3f}", ha="center", va="bottom", fontsize=7)

    # CAGR
    ax = axes[1]
    colors = bar_colors(cagrs)
    bars = ax.bar(x, cagrs, color=colors, edgecolor="white", lw=0.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("CAGR (%/year)", fontsize=12, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
    ax.yaxis.grid(True, alpha=0.3)
    for bar, v in zip(bars, cagrs):
        offset = 0.05 if v >= 0 else -0.15
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + offset,
                f"{v:.1f}%", ha="center", va="bottom", fontsize=7)

    # MaxDD
    ax = axes[2]
    colors = bar_colors(dds, higher_better=False)
    bars = ax.bar(x, dds, color=colors, edgecolor="white", lw=0.5)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Worst Drawdown (%)", fontsize=12, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7, rotation=30, ha="right")
    ax.yaxis.grid(True, alpha=0.3)
    for bar, v in zip(bars, dds):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() - 1.5,
                f"{v:.1f}%", ha="center", va="top", fontsize=7)

    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path.name}")


# ── Chart 4: 上位3戦略の詳細 ────────────────────────────────────────────────

def plot_top3_detail(results, save_path):
    top3_labels = ["S2: ATR Breakout", "S3b: Carry(AUDUSD)", "BnH USDJPY(baseline)"]
    top3 = [r for r in results if r.label in top3_labels]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    fig.suptitle("Top Strategies Detail: S2 ATR Breakout vs S3b Carry(AUD/USD) vs BnH",
                 fontsize=13, fontweight="bold")

    # Equity curves
    for r in top3:
        c = COLORS.get(r.label, "#333333")
        lw = 2.5 if r.label != "BnH USDJPY(baseline)" else 1.5
        ls = "--" if r.label == "BnH USDJPY(baseline)" else "-"
        m = r.metrics
        lbl = (f"{r.label}\n"
               f"Sharpe={m['sharpe']:.3f}  CAGR={m['cagr']:.1%}  "
               f"MaxDD={m['worst_dd']:.1%}  Trades={m['n_trades']}")
        ax1.plot(r.equity.index, r.equity.values, color=c, lw=lw, ls=ls, label=lbl)
    ax1.axhline(1.0, color="black", lw=0.6, ls=":")
    ax1.set_ylabel("Equity (1.0 = initial)", fontsize=11)
    ax1.legend(fontsize=9, loc="upper left", framealpha=0.95)
    ax1.grid(True, alpha=0.3)

    # Drawdowns
    for r in top3:
        c = COLORS.get(r.label, "#333333")
        lw = 2.0 if r.label != "BnH USDJPY(baseline)" else 1.2
        ls = "--" if r.label == "BnH USDJPY(baseline)" else "-"
        ax2.plot(r.drawdowns.index, r.drawdowns.values * 100,
                 color=c, lw=lw, ls=ls, label=r.label)
        ax2.fill_between(r.drawdowns.index, r.drawdowns.values * 100, 0,
                         color=c, alpha=0.08)
    ax2.axhline(0, color="black", lw=0.6)
    ax2.set_ylabel("Drawdown (%)", fontsize=11)
    ax2.set_xlabel("Date", fontsize=11)
    ax2.legend(fontsize=9, loc="lower left", framealpha=0.95)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path.name}")


# ── メイン ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating charts...")
    print("Running strategies...")
    results = get_all_results()

    print("\nPlotting...")
    plot_equity_curves(results, CHARTS_DIR / "01_equity_curves.png")
    plot_drawdowns(results,     CHARTS_DIR / "02_drawdowns.png")
    plot_metrics_bar(results,   CHARTS_DIR / "03_metrics_bar.png")
    plot_top3_detail(results,   CHARTS_DIR / "04_top3_detail.png")

    print("\n[DONE] All charts saved to results/charts/")
