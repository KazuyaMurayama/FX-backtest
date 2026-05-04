"""
run_all_strategies.py — 全6戦略を実行して結果を比較・保存する。

出力:
  - results/summary.csv  : 全戦略の評価指標比較表
  - コンソール           : サマリー表示

実行方法:
  python -X utf8 src/run_all_strategies.py
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import time
import pandas as pd

from backtest_engine import BacktestResult, compare_results

RESULTS_DIR = Path(__file__).parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def run_strategy(name: str, fn, **kwargs) -> BacktestResult | None:
    print(f"\n--- {name} ---")
    t0 = time.time()
    try:
        result = fn(**kwargs)
        elapsed = time.time() - t0
        m = result.metrics
        print(f"  Sharpe   : {m['sharpe']:.3f}")
        print(f"  CAGR     : {m['cagr']:.1%}")
        print(f"  Worst DD : {m['worst_dd']:.1%}")
        print(f"  Trades   : {m['n_trades']}")
        print(f"  ({elapsed:.1f}s)")
        return result
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("FX-backtest: 全6戦略 実行")
    print("=" * 60)

    # 各戦略をインポート
    from strategies.ma_crossover import run as run_ma
    from strategies.atr_breakout import run as run_atr
    from strategies.carry_trade import run as run_carry
    from strategies.rsi_reversal import run as run_rsi
    from strategies.bollinger_band import run as run_bb
    from strategies.dca import run as run_dca

    results: list[BacktestResult] = []

    configs = [
        ("S1: MAクロス(50/200)",      run_ma,    {"pair": "USDJPY", "start": "1971-01-01"}),
        ("S2: ATRブレイクアウト",     run_atr,   {"pair": "USDJPY", "start": "1971-01-01"}),
        ("S3: キャリー(USDJPY)",      run_carry, {"pair": "USDJPY", "start": "1985-07-01"}),
        ("S3b: キャリー(AUDUSD)",     run_carry, {"pair": "AUDUSD", "start": "1990-08-01"}),
        ("S3c: キャリー(NZDUSD)",     run_carry, {"pair": "NZDUSD", "start": "1985-01-01"}),
        ("S4: RSI逆張り",             run_rsi,   {"pair": "USDJPY", "start": "1971-01-01"}),
        ("S5: BB平均回帰",            run_bb,    {"pair": "USDJPY", "start": "1971-01-01"}),
        ("S6: 積立DCA(USDJPY)",       run_dca,   {"pair": "USDJPY", "start": "1990-01-01"}),
        # ベースライン: BnH
        ("BnH_USDJPY(基準)",          run_ma,    {"pair": "USDJPY", "start": "1990-01-01",
                                                   "fast": 1, "slow": 2}),  # 常時Long近似
    ]

    for name, fn, kwargs in configs:
        r = run_strategy(name, fn, **kwargs)
        if r is not None:
            r.label = name   # ラベルを分かりやすく上書き
            results.append(r)

    # ─── 比較テーブル ─────────────────────────────────────────────────────────

    print("\n" + "=" * 60)
    print("全戦略 評価指標比較")
    print("=" * 60)

    comparison = compare_results(results)

    # 数値列を見やすくフォーマット
    display_cols = ["sharpe", "cagr", "worst_dd", "calmar", "win_rate",
                    "n_trades", "period_years", "total_return"]
    display = comparison[display_cols].copy()
    for col in ["cagr", "worst_dd", "win_rate", "total_return"]:
        display[col] = display[col].apply(
            lambda x: f"{float(x):.1%}" if pd.notna(x) and x != "" else "N/A"
        )
    for col in ["sharpe", "calmar"]:
        display[col] = display[col].apply(
            lambda x: f"{float(x):.3f}" if pd.notna(x) and x != "" else "N/A"
        )
    print(display.to_string())

    # CSV保存
    csv_path = RESULTS_DIR / "summary.csv"
    comparison.to_csv(csv_path)
    print(f"\n[SAVED] {csv_path}")

    # ランキング（Sharpeで降順）
    print("\n--- Sharpe Ratio ランキング ---")
    ranked = comparison[["sharpe", "cagr", "worst_dd", "n_trades"]].copy()
    ranked["sharpe"] = pd.to_numeric(ranked["sharpe"], errors="coerce")
    ranked = ranked.sort_values("sharpe", ascending=False)
    for i, (strategy, row) in enumerate(ranked.iterrows(), 1):
        sharpe = float(row["sharpe"]) if pd.notna(row["sharpe"]) else float("nan")
        cagr_val = float(row["cagr"]) if pd.notna(row["cagr"]) else float("nan")
        dd_val = float(row["worst_dd"]) if pd.notna(row["worst_dd"]) else float("nan")
        print(f"  {i}. {strategy:<30} Sharpe={sharpe:.3f}  CAGR={cagr_val:.1%}  MaxDD={dd_val:.1%}")

    print("\n[DONE] 全戦略バックテスト完了")
