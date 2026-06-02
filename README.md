# FX-backtest — SBI証券FX 戦略バックテストプロジェクト

> SBI証券で実行可能な FX 取引手法について、長期ヒストリカルデータ（USD/JPY 1971年〜の55年分等）でバックテストを実施し、**Sharpe / CAGR / 最悪DD** で定量評価するプロジェクト。

作成日: 2026-06-02
最終更新日: 2026-06-02

---

## 📋 概要

- **対象**: SBI証券 FX（店頭FX / くりっく365 / 積立FX / SBI FXトレード等）
- **戦略カテゴリ**: 移動平均クロス・RSI・ボリンジャー・キャリートレード・積立FX (DCA) など
- **データ期間**: USD/JPY 1971〜現在（**55年**）/ 他通貨ペアは1999〜
- **データソース**: FRED（セントルイス連銀）/ Frankfurter / yfinance — **全て無料・APIキー不要**

### 評価指標
| 指標 | 目標水準 |
|---|---|
| Sharpe Ratio（年率超過収益 / 年率σ、無リスク金利=0） | > 0.5 |
| CAGR（年率複利成長率） | > 5% |
| 最悪ドローダウン (Worst DD) | < -40% |

---

## 🚀 クイックスタート

### セットアップ

```powershell
# Python 3.13.7 で動作確認済み
pip install -r requirements.txt
```

### バックテスト実行

```powershell
# 全戦略をまとめて実行
python src/run_all_strategies.py

# フェーズ別実行
python src/run_phase5a.py    # ベース戦略
python src/run_phase5b.py    # キャリートレード
python src/run_phase5c.py    # 積立FX
python src/run_phase6a.py    # NZD/JPY・GBP/JPY S2+MA200+Slope 検証
```

結果は `results/*.csv` および `results/charts/` に出力されます。

---

## 📁 ディレクトリ構成

```
FX-backtest/
├── CLAUDE.md              # Claude Code 運用ルール
├── README.md              # このファイル
├── SPEC.md                # 詳細仕様書（11KB）
├── HYPOTHESES.md          # 戦略仮説と検証ログ（22KB）
├── REPORT.md              # 最新の戦略評価レポート（13KB）
├── FILE_INDEX.md          # ファイル構成・依存関係
├── tasks.md               # 進捗管理（フェーズ4完了）
├── requirements.txt       # Python依存
├── src/
│   ├── data_fetcher.py        # データ取得（FRED/Frankfurter/yfinance、キャッシュ・リトライ実装）
│   ├── backtest_engine.py     # バックテストエンジン（signal.shift(1) で lookahead bias 排除）
│   ├── evaluation.py          # 評価指標計算（Sharpe/CAGR/MaxDD/Calmar/勝率等）
│   ├── strategies/            # 各戦略実装
│   ├── run_phase5a.py 〜 run_phase6a.py  # フェーズ別実行
│   ├── generate_charts.py     # 可視化
│   └── test_engine.py         # 単体テスト
├── data/                  # キャッシュ済みヒストリカルデータ
├── notebooks/             # 探索用 Jupyter ノート
└── results/               # バックテスト結果（CSV / チャート）
    ├── fx_landscape.md
    ├── phase5a_results.csv 〜 phase6a_results.csv
    ├── summary.csv
    └── charts/
```

---

## 📊 これまでの主な発見（詳細は [REPORT.md](REPORT.md) 参照）

- USD/JPY 55年分（14,430行）取得確認、キャッシュで50倍高速化
- 7通貨ペア + 6金利シリーズ全取得成功
- バックテストは `signal.shift(1)` を全戦略で適用し**lookahead bias を排除**
- バックテストは**スプレッドコストを反映**するが、税コストは含まない（実運用時は要調整）
  - 店頭FX：総合課税（最大55%）
  - くりっく365：申告分離 20.315% + 3年損失繰越 → 長期投資・損益通算面で最有利

---

## 🛠 技術スタック

- **言語**: Python 3.11+ / 3.13.7 で動作確認
- **データ取得**: `requests` (FRED直接) / `yfinance` / `pandas-datareader` (Frankfurter等)
- **データ処理**: `pandas` / `numpy`
- **テクニカル指標**: `ta`（RSI/ATR/BB/ADX）
- **バックテスト**: `vectorbt`
- **可視化**: `matplotlib` / `seaborn`

---

## 🔗 関連リポジトリ

- [KazuyaMurayama/NASDAQ_backtest](https://github.com/KazuyaMurayama/NASDAQ_backtest) — NASDAQ 3倍レバ戦略バックテスト本体（評価指標 9指標標準の参照源）
- [KazuyaMurayama/NASDAQ-strategy-gas](https://github.com/KazuyaMurayama/NASDAQ-strategy-gas) — NASDAQ 本番運用システム

---

## ⚖️ 免責事項

本プロジェクトの結果は**過去データに基づくバックテスト**であり、将来の投資パフォーマンスを保証するものではありません。実投資判断は自己責任で行ってください。

---

## 開発者

**男座員也（Kazuya Oza / おざ かずや）**

GitHub: [@KazuyaMurayama](https://github.com/KazuyaMurayama)

---

## ライセンス

未定（個人プロジェクト）。利用・引用時は事前にご相談ください。
