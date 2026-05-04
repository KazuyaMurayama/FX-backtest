"""
test_engine.py — backtest_engine + evaluation の単体テスト

テストケース:
  T1: ゼロシグナル → リターン=0, エクイティ=1.0固定
  T2: 定常ロング  → エクイティ ≈ 価格累積リターン（スプレッド差引）
  T3: 定常ショート → 価格下落時に利益
  T4: 実データ (USD/JPY 1971〜) でエンド・ツー・エンド動作確認
  T5: evaluation 個別指標の境界値チェック
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd

from backtest_engine import BacktestEngine, run_backtest
from evaluation import sharpe_ratio, cagr, worst_drawdown, evaluate


def assert_close(actual, expected, tol=1e-6, label=""):
    assert abs(actual - expected) < tol, f"[{label}] {actual} != {expected} (tol={tol})"

def assert_true(condition, label=""):
    assert condition, f"[{label}] FAILED"

PASS = "[PASS]"
FAIL = "[FAIL]"


# ─── T1: ゼロシグナル ─────────────────────────────────────────────────────────

def test_zero_signal():
    label = "T1: ゼロシグナル"
    dates = pd.date_range("2000-01-01", periods=100, freq="B")
    prices = pd.Series(100 + np.random.randn(100).cumsum(), index=dates, name="close")
    signals = pd.Series(0.0, index=dates)

    result = run_backtest(prices, signals, pair="USDJPY", label="zero")

    assert_close(result.returns.sum(), 0.0, tol=1e-10, label=label)
    assert_close(result.equity.iloc[-1], 1.0, tol=1e-10, label=label)
    assert_close(result.metrics["n_trades"], 0, tol=0.5, label=label)
    print(f"{PASS} {label}")


# ─── T2: 定常ロング（スプレッドコスト1回のみ） ──────────────────────────────

def test_constant_long():
    label = "T2: 定常ロング"
    dates = pd.date_range("2000-01-01", periods=50, freq="B")
    prices = pd.Series(range(100, 150), dtype=float, index=dates, name="close")
    signals = pd.Series(1.0, index=dates)

    result = run_backtest(prices, signals, pair="USDJPY", label="long")

    # ポジション変化は1回だけ（最初のシグナル確定時）
    assert_true(result.metrics["n_trades"] == 1, label + " n_trades")

    # CAGRは正（価格が単調増加）
    assert_true(result.metrics["cagr"] > 0, label + " cagr>0")

    # エクイティ最終値 > 1
    assert_true(result.equity.iloc[-1] > 1.0, label + " equity>1")
    print(f"{PASS} {label}")


# ─── T3: 定常ショート（価格上昇 → 損失） ────────────────────────────────────

def test_constant_short():
    label = "T3: 定常ショート（価格上昇時は損失）"
    dates = pd.date_range("2000-01-01", periods=50, freq="B")
    prices = pd.Series(range(100, 150), dtype=float, index=dates, name="close")
    signals = pd.Series(-1.0, index=dates)

    result = run_backtest(prices, signals, pair="USDJPY", label="short")

    # 価格が単調上昇なのでショートは損失
    assert_true(result.equity.iloc[-1] < 1.0, label)
    assert_true(result.metrics["worst_dd"] < 0, label + " worst_dd<0")
    print(f"{PASS} {label}")


# ─── T4: ロング/ショート反転シグナル ────────────────────────────────────────

def test_alternating_signal():
    label = "T4: 反転シグナル（ポジション変化コスト）"
    dates = pd.date_range("2000-01-01", periods=10, freq="B")
    prices = pd.Series([100.0]*10, index=dates, name="close")  # 価格変動なし
    # 毎日反転
    sigs = [1, -1, 1, -1, 1, -1, 1, -1, 1, -1]
    signals = pd.Series(sigs, dtype=float, index=dates)

    result = run_backtest(prices, signals, pair="USDJPY", label="alt")

    # 価格変動なし + 毎日スプレッドコスト → リターンは常に負
    assert_true(result.equity.iloc[-1] < 1.0, label + " equity<1 (spread cost)")
    assert_true(result.metrics["n_trades"] > 1, label + " n_trades>1")
    print(f"{PASS} {label}")


# ─── T5: evaluation 境界値 ───────────────────────────────────────────────────

def test_evaluation_edge_cases():
    label = "T5: evaluation 境界値"

    # 全ゼロリターン → Sharpe=nan
    ret_zero = pd.Series([0.0]*252)
    sr = sharpe_ratio(ret_zero)
    assert_true(np.isnan(sr), label + " sharpe(zero)=nan")

    # 単調増加エクイティ → worst_dd=0
    eq_up = pd.Series(np.linspace(1.0, 2.0, 252))
    wd = worst_drawdown(eq_up)
    assert_close(wd, 0.0, tol=1e-10, label=label + " worst_dd(monotone)")

    # CAGR: 1年後に2倍 → 100%
    eq_double = pd.Series([1.0]*252 + [2.0])
    c = cagr(pd.Series([1.0, 2.0]))
    # 1年以下なのでCAGR > 100%になるが正であることを確認
    assert_true(c > 0, label + " cagr>0")

    # evaluate が全キーを返す
    eq = pd.Series(np.linspace(1.0, 1.5, 252))
    ret = eq.pct_change().fillna(0)
    sig = pd.Series([1.0]*252)
    m = evaluate(eq, ret, sig)
    required = {"sharpe","cagr","worst_dd","calmar","win_rate","profit_factor","n_trades","max_dd_duration","total_return","period_years"}
    missing = required - set(m.keys())
    assert_true(len(missing) == 0, label + f" missing keys={missing}")

    print(f"{PASS} {label}")


# ─── T6: 実データ エンド・ツー・エンド ──────────────────────────────────────

def test_real_data_e2e():
    label = "T6: 実データ (USD/JPY) エンド・ツー・エンド"
    try:
        from data_fetcher import fetch_fx
        prices = fetch_fx("USDJPY")["close"]

        # 常時ロングシグナル（バイ・アンド・ホールド相当）
        signals = pd.Series(1.0, index=prices.index)

        result = run_backtest(prices, signals, pair="USDJPY",
                              label="BnH_USDJPY", start="1990-01-01")

        assert_true(len(result.equity) > 1000, label + " enough data")
        assert_true(not result.equity.isnull().any(), label + " no NaN in equity")
        assert_true(not result.returns.isnull().any(), label + " no NaN in returns")

        # 指標が全て有限値
        for k, v in result.metrics.items():
            if isinstance(v, float):
                assert_true(np.isfinite(v) or np.isnan(v), label + f" {k} is finite/nan")

        print(f"{PASS} {label}")
        print(result.summary())
        return result
    except Exception as e:
        print(f"[FAIL] {label}: {e}")
        raise


# ─── 実行 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("BacktestEngine + Evaluation 単体テスト")
    print("=" * 60)

    passed = 0
    failed = 0
    for fn in [test_zero_signal, test_constant_long, test_constant_short,
               test_alternating_signal, test_evaluation_edge_cases, test_real_data_e2e]:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"[FAIL]: {e}")
            failed += 1
        except Exception as e:
            print(f"[ERROR]: {e}")
            failed += 1

    print()
    print(f"結果: {passed}件PASS / {failed}件FAIL")
    if failed == 0:
        print("[ALL PASS] 全テスト通過")
