# FX-backtest Project — CLAUDE.md

## プロジェクト概要
SBI証券FXを対象に代表的戦略のバックテストを行い、Sharpe/CAGR/最悪DDで評価する。

## 必読ファイル（セッション開始時）
1. `tasks.md` — 未完了タスク・優先度
2. `FILE_INDEX.md` — ファイル構成・依存関係
3. `SPEC.md` — 仕様・設計方針

## モデル使い分け
- 計画・分析・設計 → Opus
- 実装・調査サブタスク → Sonnet（`model: "sonnet"`）

## Gitルール
- ブランチ作成禁止（`git checkout -b` / `git switch -c` / `git branch` 禁止）
- 各フェーズ完了後に `git add → commit → push`
- コミットメッセージ: `feat: ` / `fix: ` / `docs: ` プレフィックス必須

## コーディングルール
- 言語: Python 3.11+
- データ取得: `fredapi`（USD/JPY 1971〜）＋ `yfinance`（複数通貨）
- バックテスト: `vectorbt` または `backtesting.py`
- 結果: `results/` ディレクトリにCSV保存

## タイムアウト対策
- データ取得・バックテストは戦略ごとに分割実行
- 各ステップでCSV中間保存→再実行時はキャッシュ参照

## 禁止事項
- 名前誤記: ❌ 村山/Murayama/おとこざ → ✅ 男座員也/おざかずや/Kazuya Oza
- 確認なしの破壊的操作禁止

## スキルファイル
- `skills/output-format.md` — 出力形式ルール（工数超過時切り出し）
