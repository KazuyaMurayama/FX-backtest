# FILE_INDEX.md — FX-backtest ファイルインデックス

最終更新: 2026-05-03

---

## 📌 最優先参照ファイル（セッション開始時に必ず確認）

| ファイル | 用途 | 最終更新 |
|--------|------|---------|
| [tasks.md](tasks.md) | タスク進捗・未完了一覧 | 2026-05-03 |
| [SPEC.md](SPEC.md) | システム仕様・設計方針 | 2026-05-03 |
| [CLAUDE.md](CLAUDE.md) | プロジェクトルール | 2026-05-03 |

---

## 📁 ディレクトリ構成（計画）

```
FX-backtest/
├── 📄 CLAUDE.md            ✅ 作成済み
├── 📄 SPEC.md              ✅ 作成済み
├── 📄 tasks.md             ✅ 作成済み
├── 📄 FILE_INDEX.md        ✅ 作成済み（本ファイル）
├── 📄 requirements.txt     ⬜ フェーズ1で作成
├── 📂 src/
│   ├── data_fetcher.py     ⬜ フェーズ1 (タスク1-2)
│   ├── backtest_engine.py  ⬜ フェーズ2 (タスク2-1)
│   ├── evaluation.py       ⬜ フェーズ2 (タスク2-2)
│   └── strategies/
│       ├── __init__.py     ⬜ フェーズ3
│       ├── ma_crossover.py ⬜ フェーズ3 (タスク3-1)
│       ├── atr_breakout.py ⬜ フェーズ3 (タスク3-2)
│       ├── carry_trade.py  ⬜ フェーズ3 (タスク3-3)
│       ├── rsi_reversal.py ⬜ フェーズ3 (タスク3-4)
│       ├── bollinger_band.py ⬜ フェーズ3 (タスク3-5)
│       └── dca.py          ⬜ フェーズ3 (タスク3-6)
├── 📂 data/
│   └── raw/                ⬜ フェーズ1 (CSVキャッシュ)
├── 📂 results/
│   ├── charts/             ⬜ フェーズ4
│   └── summary.csv         ⬜ フェーズ4
└── 📂 notebooks/
    └── analysis.ipynb      ⬜ フェーズ4
```

---

## 🔑 主要ファイルの依存関係

```
data_fetcher.py
  └─ FRED API (fredapi) → data/raw/usdjpy_daily.csv 等
  └─ yfinance → data/raw/eurusd_daily.csv 等

backtest_engine.py
  └─ data_fetcher.py (価格データ取得)
  └─ strategies/*.py (売買シグナル)
  └─ evaluation.py (指標計算)

evaluation.py (スタンドアロン)
  └─ 入力: equity_curve (pd.Series)
  └─ 出力: {sharpe, cagr, worst_dd, ...}
```

---

## 📊 結果ファイル（フェーズ4以降）

| ファイル | 内容 | 更新タイミング |
|--------|------|-------------|
| `results/summary.csv` | 全戦略の指標比較表 | フェーズ4完了時 |
| `results/charts/*.png` | 資産曲線グラフ（戦略別） | フェーズ4完了時 |
| `REPORT.md` | 最終分析レポート | フェーズ4完了時 |

---

## 🔗 外部データソース参照

| ソース | URL | 用途 |
|-------|-----|------|
| FRED API | https://fred.stlouisfed.org/docs/api/api_key.html | USD/JPY 1971〜日足 |
| FRED DEXJPUS | https://fred.stlouisfed.org/series/DEXJPUS | USD/JPY時系列 |
| FRED FEDFUNDS | https://fred.stlouisfed.org/series/FEDFUNDS | 米国政策金利 |
| yfinance docs | https://github.com/ranaroussi/yfinance | 複数通貨ペア |
| BOJ時系列 | https://www.stat-search.boj.or.jp/ | 円相場長期データ |
