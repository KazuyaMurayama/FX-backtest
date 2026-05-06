"""
run_phase5c.py — Phase 5C: H5 条件付きキャリー×モメンタム戦略検証

仮説H5:
  「12ヶ月モメンタムが正 AND 金利差キャリーが正のときのみロング」という
  条件付き戦略が、AUD/JPYまたはAUD/USDに適用するとSharpe 0.5〜1.0に到達する

対象:
  - AUD/JPY (AUD/USD × USD/JPY で構築)
  - AUD/USD (S3b比較用)

バリアント比較:
  1. BnH        : 常時ロング（ベースライン）
  2. Carry_only : キャリー（金利差）が正のときのみロング
  3. Mom_only   : 12M モメンタムが正のときのみロング
  4. Carry×Mom  : 両方が正のときのみロング（H5本命）
  5. S3b_existing: 既存のS3b carry戦略（比較用、AUD/USD）

実行:
    python -X utf8 src/run_phase5c.py

参考論文: Iwanaga & Sakemoto (2023) 確実性等価リターン+6.6%/年改善
         Menkhoff et al. (2012) FXモメンタムSharpe 0.95
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
import pandas as pd

from data_fetcher import fetch_fx
from backtest_engine import run_backtest, BacktestResult
from evaluation import evaluate, drawdown_series

# ─── 定数 ─────────────────────────────────────────────────────────────────────

RESULTS_DIR = Path(__file__).parent.parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

MOMENTUM_WINDOW = 252   # 12ヶ月 ≈ 252営業日
START = "1990-09-01"    # AUD_RBA金利データ開始(1990-08)の翌月

# 日本語フォント
_avail = {f.name for f in fm.fontManager.ttflist}
_chosen = next((f for f in ["MS Gothic", "Meiryo", "Yu Gothic", "DejaVu Sans"]
                if f in _avail), "DejaVu Sans")
plt.rcParams["font.family"] = _chosen
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150


# ─── データ取得ヘルパー ────────────────────────────────────────────────────────

def load_rates() -> dict[str, pd.Series]:
    """キャッシュ済み金利データを読み込む（月次→日次ffill）"""
    data_dir = Path(__file__).parent.parent / "data" / "raw"
    files = {
        "AUD": "rate_AUD_RBA.csv",
        "JPY": "rate_JPY_CALLRATE.csv",
        "USD": "rate_USD_FEDFUNDS.csv",
    }
    rates = {}
    for key, fname in files.items():
        df = pd.read_csv(data_dir / fname, index_col=0, parse_dates=True)
        df.columns = ["value"]
        s = pd.to_numeric(df["value"], errors="coerce").dropna()
        # 月次データを日次にリサンプル&前方補完
        s_daily = s.resample("D").ffill()
        rates[key] = s_daily
    return rates


def build_audjpy(start: str = START) -> pd.Series:
    """AUD/USD × USD/JPY でAUD/JPYを構築"""
    aud_usd = fetch_fx("AUDUSD")["close"]
    usd_jpy = fetch_fx("USDJPY")["close"]
    aud_usd.index = pd.to_datetime(aud_usd.index)
    usd_jpy.index = pd.to_datetime(usd_jpy.index)

    audjpy = (aud_usd * usd_jpy).dropna()
    audjpy = audjpy.loc[start:].ffill()
    return audjpy


# ─── シグナル生成 ──────────────────────────────────────────────────────────────

def carry_signal(prices: pd.Series, rate_long: pd.Series,
                 rate_short: pd.Series) -> pd.Series:
    """
    金利差が正（rate_long > rate_short）のときロング(+1)、それ以外フラット(0)。
    lookahead bias: 金利は月次ffill済み → 当日時点での確定値使用で問題なし
    """
    rate_long_d  = rate_long.reindex(prices.index).ffill()
    rate_short_d = rate_short.reindex(prices.index).ffill()
    diff = rate_long_d - rate_short_d
    sig = pd.Series(0.0, index=prices.index)
    sig[diff > 0] = 1.0
    return sig


def momentum_signal(prices: pd.Series, window: int = MOMENTUM_WINDOW) -> pd.Series:
    """
    12M(252日)モメンタムが正のときロング(+1)、それ以外フラット(0)。
    shift(1)でlookahead bias排除（今日の終値を翌日から使う）
    """
    ret_12m = prices / prices.shift(window) - 1
    sig = pd.Series(0.0, index=prices.index)
    sig[ret_12m > 0] = 1.0
    # モメンタムシグナルは当日の情報から生成するため、
    # バックテストエンジンが shift(1) するのを考慮してここでは shift しない
    return sig


def combined_signal(carry_sig: pd.Series, mom_sig: pd.Series) -> pd.Series:
    """キャリー × モメンタム: 両方が+1のときのみロング"""
    return (carry_sig == 1.0) & (mom_sig == 1.0)
    # Boolean → floatへ
def combined_signal(carry_sig: pd.Series, mom_sig: pd.Series) -> pd.Series:
    """キャリー × モメンタム: 両方が+1のときのみロング"""
    return ((carry_sig == 1.0) & (mom_sig == 1.0)).astype(float)


# ─── バリアント実行 ────────────────────────────────────────────────────────────

def run_variants_audjpy(rates: dict[str, pd.Series]) -> dict[str, BacktestResult]:
    """AUD/JPYの4バリアントを実行"""
    print("\n[AUD/JPY] データ準備...")
    prices = build_audjpy(start=START)
    pair_label = "AUDJPY"

    sig_carry = carry_signal(prices, rates["AUD"], rates["JPY"])
    sig_mom   = momentum_signal(prices)
    sig_both  = combined_signal(sig_carry, sig_mom)
    sig_bnh   = pd.Series(1.0, index=prices.index)

    variants = {
        "BnH_AUDJPY":        sig_bnh,
        "Carry_only":        sig_carry,
        "Mom12M_only":       sig_mom,
        "Carry×Mom (H5)":    sig_both,
    }

    results = {}
    for name, sig in variants.items():
        r = run_backtest(
            prices, sig,
            pair="AUDUSD",   # スプレッドはAUDUSDで代用
            label=name,
            leverage=1.0,
            start=START,
        )
        r.label = name
        results[name] = r
        m = r.metrics
        print(f"  {name:20s} | Sharpe={m['sharpe']:.3f} | CAGR={m['cagr']:+.2%}"
              f" | MaxDD={m['worst_dd']:.1%} | Calmar={m['calmar']:.3f}"
              f" | Trades={m['n_trades']}")

    return results


def run_variants_audusd(rates: dict[str, pd.Series]) -> dict[str, BacktestResult]:
    """AUD/USDの4バリアント（S3b比較）"""
    print("\n[AUD/USD] データ準備...")
    prices = fetch_fx("AUDUSD")["close"]
    prices.index = pd.to_datetime(prices.index)
    prices = prices.loc[START:].ffill()
    pair_label = "AUDUSD"

    sig_carry = carry_signal(prices, rates["AUD"], rates["USD"])
    sig_mom   = momentum_signal(prices)
    sig_both  = combined_signal(sig_carry, sig_mom)
    sig_bnh   = pd.Series(1.0, index=prices.index)

    variants = {
        "BnH_AUDUSD":        sig_bnh,
        "Carry_only(S3b相当)": sig_carry,
        "Mom12M_only":        sig_mom,
        "Carry×Mom (H5)":     sig_both,
    }

    results = {}
    for name, sig in variants.items():
        r = run_backtest(
            prices, sig,
            pair="AUDUSD",
            label=name,
            leverage=1.0,
            start=START,
        )
        r.label = name
        results[name] = r
        m = r.metrics
        print(f"  {name:25s} | Sharpe={m['sharpe']:.3f} | CAGR={m['cagr']:+.2%}"
              f" | MaxDD={m['worst_dd']:.1%} | Calmar={m['calmar']:.3f}"
              f" | Trades={m['n_trades']}")

    return results


# ─── チャート ──────────────────────────────────────────────────────────────────

COLORS = {
    "BnH_AUDJPY":          "#9E9E9E",
    "BnH_AUDUSD":          "#9E9E9E",
    "Carry_only":          "#FF9800",
    "Carry_only(S3b相当)": "#FF9800",
    "Mom12M_only":         "#2196F3",
    "Carry×Mom (H5)":      "#4CAF50",
}

def plot_comparison(results_jpy: dict, results_usd: dict, save_path: Path) -> None:
    """2行×2列: [AUD/JPY equity, AUD/USD equity], [Sharpe棒, CAGR棒]"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle(
        "Phase 5C H5: Conditional Carry × Momentum Strategy\n"
        "(AUD/JPY & AUD/USD, 1990-2026, Leverage 1x)",
        fontsize=13, fontweight="bold"
    )

    def _equity_panel(ax, results, title):
        for name, r in results.items():
            eq = r.equity / r.equity.iloc[0]
            c = COLORS.get(name, "#333333")
            lw = 2.5 if "H5" in name else 1.2
            alpha = 1.0 if "H5" in name else 0.7
            m = r.metrics
            ax.plot(eq.index, eq.values, color=c, lw=lw, alpha=alpha,
                    label=f"{name}  (Sharpe={m['sharpe']:.3f})")
        ax.axhline(1.0, color="black", lw=0.6, ls=":")
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel("Equity (1.0 = start)")
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(True, alpha=0.3)

    _equity_panel(axes[0, 0], results_jpy, "AUD/JPY Equity Curves")
    _equity_panel(axes[0, 1], results_usd, "AUD/USD Equity Curves")

    def _bar_panel(ax, results_jpy, results_usd, metric, title, pct=False):
        all_names = list(results_jpy.keys()) + ["│"] + list(results_usd.keys())
        all_vals = []
        bar_colors = []
        for name, r in results_jpy.items():
            v = r.metrics[metric] * (100 if pct else 1)
            all_vals.append(v)
            bar_colors.append(COLORS.get(name, "#607D8B"))
        # 区切り
        all_vals.append(0.0)
        bar_colors.append("#FFFFFF")
        for name, r in results_usd.items():
            v = r.metrics[metric] * (100 if pct else 1)
            all_vals.append(v)
            bar_colors.append(COLORS.get(name, "#607D8B"))

        x = np.arange(len(all_names))
        bars = ax.bar(x, all_vals, color=bar_colors, edgecolor="white", lw=0.5)
        # H5バーを強調
        for i, name in enumerate(all_names):
            if "H5" in name:
                bars[i].set_edgecolor("black")
                bars[i].set_linewidth(2)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(all_names, rotation=30, ha="right", fontsize=7)
        ax.axhline(0, color="black", lw=0.8)
        ax.grid(True, alpha=0.3, axis="y")
        suffix = "%" if pct else ""
        for bar, val in zip(bars, all_vals):
            if bar.get_facecolor() == (1, 1, 1, 1):
                continue
            y = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2,
                    y + 0.005 if y >= 0 else y - 0.015,
                    f"{val:.2f}{suffix}",
                    ha="center", va="bottom" if y >= 0 else "top", fontsize=7)

    _bar_panel(axes[1, 0], results_jpy, results_usd, "sharpe", "Sharpe Ratio Comparison")
    _bar_panel(axes[1, 1], results_jpy, results_usd, "cagr", "CAGR Comparison", pct=True)

    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path.name}")


def plot_h5_detail(results_jpy: dict, save_path: Path) -> None:
    """H5本命: AUD/JPY Carry×Momの詳細（エクイティ + ドローダウン）"""
    target_name = "Carry×Mom (H5)"
    bnh_name    = "BnH_AUDJPY"

    r_h5  = results_jpy.get(target_name)
    r_bnh = results_jpy.get(bnh_name)

    if r_h5 is None:
        print(f"  [SKIP] {target_name} not found")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    fig.suptitle("H5 Detail: Conditional Carry×Momentum on AUD/JPY (1990-2026)",
                 fontsize=13, fontweight="bold")

    # Equity
    m = r_h5.metrics
    ax1.plot(r_h5.equity.index, r_h5.equity.values,
             color="#4CAF50", lw=2.5,
             label=f"Carry×Mom  Sharpe={m['sharpe']:.3f}  CAGR={m['cagr']:.1%}  MaxDD={m['worst_dd']:.1%}")
    if r_bnh:
        m_b = r_bnh.metrics
        ax1.plot(r_bnh.equity.index, r_bnh.equity.values,
                 color="#9E9E9E", lw=1.2, ls="--",
                 label=f"BnH  Sharpe={m_b['sharpe']:.3f}  CAGR={m_b['cagr']:.1%}")
    ax1.axhline(1.0, color="black", lw=0.6, ls=":")
    ax1.set_ylabel("Equity (1.0 = start)")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Drawdown
    ax2.plot(r_h5.drawdowns.index, r_h5.drawdowns.values * 100,
             color="#4CAF50", lw=2.0, label="Carry×Mom MaxDD")
    ax2.fill_between(r_h5.drawdowns.index, r_h5.drawdowns.values * 100, 0,
                     color="#4CAF50", alpha=0.1)
    if r_bnh:
        ax2.plot(r_bnh.drawdowns.index, r_bnh.drawdowns.values * 100,
                 color="#9E9E9E", lw=1.0, ls="--", label="BnH DD")
    ax2.axhline(0, color="black", lw=0.6)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.legend(fontsize=9)
    ax2.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(save_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {save_path.name}")


# ─── CSV保存 ───────────────────────────────────────────────────────────────────

def save_csv(results_jpy: dict, results_usd: dict) -> None:
    rows = []
    for universe, res_dict in [("AUDJPY", results_jpy), ("AUDUSD", results_usd)]:
        for name, r in res_dict.items():
            m = r.metrics
            rows.append({
                "universe": universe,
                "variant": name,
                "sharpe":   round(m["sharpe"], 4),
                "cagr":     round(m["cagr"], 4),
                "worst_dd": round(m["worst_dd"], 4),
                "calmar":   round(m["calmar"], 4),
                "n_trades": m["n_trades"],
                "period_years": round(m["period_years"], 1),
            })
    df = pd.DataFrame(rows)
    out = RESULTS_DIR / "phase5c_results.csv"
    df.to_csv(out, index=False)
    print(f"  Saved: {out}")


# ─── メイン ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Phase 5C — H5: Conditional Carry × Momentum")
    print("=" * 60)

    # 金利データ読み込み
    print("\n[RATES] キャッシュ済み金利データ読み込み...")
    rates = load_rates()
    for k, v in rates.items():
        print(f"  {k}: {v.index.min().date()} ~ {v.index.max().date()}, rows={len(v)}")

    # AUD/JPY検証
    print(f"\n--- AUD/JPY バリアント (start={START}) ---")
    results_jpy = run_variants_audjpy(rates)

    # AUD/USD検証（S3b比較）
    print(f"\n--- AUD/USD バリアント (start={START}) ---")
    results_usd = run_variants_audusd(rates)

    # チャート
    print("\n[CHART] チャート生成...")
    plot_comparison(results_jpy, results_usd,
                    CHARTS_DIR / "phase5c_h5_comparison.png")
    plot_h5_detail(results_jpy,
                   CHARTS_DIR / "phase5c_h5_detail.png")

    # CSV
    print("\n[CSV] 結果保存...")
    save_csv(results_jpy, results_usd)

    # サマリー表示
    print("\n" + "=" * 60)
    print("Phase 5C 完了サマリー")
    print("=" * 60)

    h5_jpy = results_jpy["Carry×Mom (H5)"]
    h5_usd = results_usd["Carry×Mom (H5)"]
    m_j = h5_jpy.metrics
    m_u = h5_usd.metrics

    print(f"\n[H5 AUD/JPY Carry×Mom]")
    print(f"  Sharpe: {m_j['sharpe']:.3f}  CAGR: {m_j['cagr']:.1%}  "
          f"MaxDD: {m_j['worst_dd']:.1%}  Calmar: {m_j['calmar']:.3f}")
    print(f"\n[H5 AUD/USD Carry×Mom]")
    print(f"  Sharpe: {m_u['sharpe']:.3f}  CAGR: {m_u['cagr']:.1%}  "
          f"MaxDD: {m_u['worst_dd']:.1%}  Calmar: {m_u['calmar']:.3f}")

    # 仮説判定
    best_sharpe = max(m_j["sharpe"], m_u["sharpe"])
    if best_sharpe >= 0.5:
        verdict = "✅ H5 CONFIRMED (Sharpe >= 0.5)"
    elif best_sharpe >= 0.2:
        verdict = "△ H5 PARTIAL (Sharpe >= 0.2)"
    else:
        verdict = "❌ H5 REJECTED (Sharpe < 0.2)"
    print(f"\n仮説判定: {verdict}")

    print("\n成果物:")
    for f in ["phase5c_h5_comparison.png", "phase5c_h5_detail.png",
              "phase5c_results.csv"]:
        print(f"  results/{'charts/' if f.endswith('.png') else ''}{f}")


if __name__ == "__main__":
    main()
