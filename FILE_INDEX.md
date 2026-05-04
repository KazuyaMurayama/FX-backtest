# FILE_INDEX.md — FX-backtest ファイルインデックス

最終更新: 2026-05-04

---

## 📌 最優先参照ファイル（セッション開始時に必ず確認）

| ファイル | 用途 | 最終更新 |
|--------|------|---------|
| [tasks.md](tasks.md) | タスク進捗・未完了一覧 | 2026-05-04 |
| [SPEC.md](SPEC.md) | システム仕様・設計方針 | 2026-05-04 |
| [CLAUDE.md](CLAUDE.md) | プロジェクトルール | 2026-05-03 |

---

## 📁 ディレクトリ構成（現在）

```
FX-backtest/
├── 📄 CLAUDE.md            ✅ 作成済み
├── 📄 SPEC.md              ✅ 作成済み
├── 📄 tasks.md             ✅ 作成済み
├── 📄 FILE_INDEX.md        ✅ 作成済み（本ファイル）
├── 📄 requirements.txt     ✅ フェーズ1完了
├── 📄 .gitignore           ✅ フェーズ1完了
├── 📂 src/
│   ├── __init__.py         ✅ フェーズ1完了
│   ├── data_fetcher.py     ✅ フェーズ1完了（FRED直接URL+キャッシュ+リトライ）
│   ├── backtest_engine.py  ⬜ フェーズ2 (タスク2-1)
│   ├── evaluation.py       ⬜ フェーズ2 (タスク2-2)
│   └── strategies/
│       ├── __init__.py     ✅ フェーズ1完了
│       ├── ma_crossover.py ⬜ フェーズ3 (タスク3-1)
│       ├── atr_breakout.py ⬜ フェーズ3 (タスク3-2)
│       ├── carry_trade.py  ⬜ フェーズ3 (タスク3-3)
│       ├── rsi_reversal.py ⬜ フェーズ3 (タスク3-4)
│       ├── bollinger_band.py ⬜ フェーズ3 (タスク3-5)
│       └── dca.py          ⬜ フェーズ3 (タスク3-6)
├── 📂 data/
│   └── raw/                ✅ キャッシュ保存済み（gitignore対象）
│       ├── fx_USDJPY.csv   (14,430行 / 1971〜2026)
│       ├── fx_GBPUSD.csv   (14,430行 / 1971〜2026)
│       ├── fx_EURUSD.csv   ( 7,125行 / 1999〜2026)
│       ├── fx_AUDUSD.csv   (14,430行 / 1971〜2026)
│       ├── fx_NZDUSD.csv   (14,430行 / 1971〜2026)
│       ├── fx_USDCHF.csv   (14,430行 / 1971〜2026)
│       ├── fx_USDCAD.csv   (14,430行 / 1971〜2026)
│       ├── rate_USD_FEDFUNDS.csv (862行 / 1954〜)
│       ├── rate_JPY_CALLRATE.csv (489行 / 1985〜)
│       ├── rate_AUD_RBA.csv      (428行 / 1990〜)
│       ├── rate_EUR_ECB.csv      (9,982行 / 1999〜)
│       ├── rate_GBP_BOE.csv      (7,409行 / 1997〜)
│       └── rate_NZD_RBNZ.csv     (480行 / 1985〜)
├── 📂 results/
│   ├── charts/             ⬜ フェーズ4
│   └── summary.csv         ⬜ フェーズ4
└── 📂 notebooks/
    └── analysis.ipynb      ⬜ フェーズ4
```

---

## 🔑 主要ファイルの依存関係

```
data_fetcher.py                        ← フェーズ1完了
  ├─ FRED直接URL (requests) → data/raw/fx_*.csv
  └─ FRED直接URL (requests) → data/raw/rate_*.csv

backtest_engine.py                     ← フェーズ2
  ├─ data_fetcher.py (価格データ読込)
  ├─ strategies/*.py (売買シグナル生成)
  └─ evaluation.py (指標計算)

evaluation.py                          ← フェーズ2
  ├─ 入力: equity_curve (pd.Series)
  └─ 出力: {sharpe, cagr, worst_dd, ...}
```

---

## 📊 データ取得結果サマリー（フェーズ1完了時点）

| ペア/金利 | 行数 | 開始日 | 終了日 | 年数 |
|----------|------|-------|-------|------|
| USDJPY | 14,430 | 1971-01-04 | 2026-04-24 | 55.3年 |
| GBPUSD | 14,430 | 1971-01-04 | 2026-04-24 | 55.3年 |
| EURUSD | 7,125 | 1999-01-04 | 2026-04-24 | 27.3年 |
| AUDUSD | 14,430 | 1971-01-04 | 2026-04-24 | 55.3年 |
| NZDUSD | 14,430 | 1971-01-04 | 2026-04-24 | 55.3年 |
| USDCHF | 14,430 | 1971-01-04 | 2026-04-24 | 55.3年 |
| USDCAD | 14,430 | 1971-01-04 | 2026-04-24 | 55.3年 |
| USD金利(FF) | 862 | 1954-07-01 | 2026-04-01 | 71.8年 |
| JPY金利 | 489 | 1985-07-01 | 2026-03-01 | 40.7年 |
| AUD金利 | 428 | 1990-08-01 | 2026-03-01 | 35.6年 |
| EUR金利 | 9,982 | 1999-01-01 | 2026-04-30 | 27.3年 |
| GBP金利 | 7,409 | 1997-01-02 | 2026-04-29 | 29.3年 |
| NZD金利 | 480 | 1985-01-01 | 2024-12-01 | 39.9年 |

---

## 🔗 外部データソース参照

| ソース | 用途 | APIキー |
|-------|-----|--------|
| FRED fredgraph.csv直接URL | FX価格・金利（主要） | 不要 ✅ |
| Frankfurter API | バックアップ（1999〜） | 不要 ✅ |
| yfinance | 補完用（2000〜） | 不要 ✅ |
