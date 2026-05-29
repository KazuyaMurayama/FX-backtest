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

## 開発者情報

このリポジトリの開発者・所有者は **男座員也（Kazuya Oza / おざ かずや）** です。

- ドキュメント・コード・コミット等で開発者名を記載する際は必ず **男座員也** または **Kazuya Oza** を使用する
- 「Murayama」「村山」「Otokoza」「おとこざ」など誤表記は使用しない

### 開発者の作業環境
- **OS:** Windows 11（Macではない）。シェルは PowerShell 5.1 / Bash（WSL/Git Bash）。`brew` / `Cmd+` / Mac専用コマンドは使用不可。パッケージ管理は `winget` / `scoop`。
- **スマートフォン:** iPhone（iOS）。Android固有の手順・adb・Play Store等は不要。
- コマンド例はPowerShell構文（`;` 連結、`$env:VAR`）で提示。macOS専用ツールを回答に含めない。

## 作業品質ルール

### Git・ブランチ管理
- 作業前: `git branch --show-current` でブランチ確認 → main以外なら `git checkout main && git pull` してから開始。

### ファイル特定（編集前）
- ユーザー発話のキーワード全てをファイル名と照合してから編集。キーワード不完全一致・候補不確かなら必ず確認。

### 成果物報告
- ファイル作成・更新・push後は必ず3列表で報告: `| 成果物 | 説明 | リンク |`
- リンクは `/blob/<実ブランチ>/<パス>` 形式。報告前に `gh api repos/OWNER/REPO/contents/PATH?ref=BRANCH` で存在確認。push前はURL生成しない。

### ドキュメント品質
- UIパス・コマンド・設定名は公式ドキュメントで確認後に記載。確認不可なら「[要確認]」と明記。
- OS/環境制約（例: Windows専用）をタスク開始時に確認。完成後に `brew`/`Cmd`/`macOS` 等をgrepして除去。

## ファイル保存ルール
- 成果物・スクリプトは本リポジトリ内のみに保存。`C:\\Users\\user\\Desktop` への出力禁止（ユーザー明示指定時を除く）。

<!-- SKILLS_RULES_START -->
## Skill 起動ルール（v2.1 / 2026-05-29）
以下のスキルは **必須・スキップ禁止**。該当シーンでは SKILL.md を読んでから作業を開始すること。

- **時系列・トレンド分析を行う時は必ず** `.claude/skills/time-series-analysis/SKILL.md` を読み、手順に従って分析を実行する
- **A/B テスト・戦略比較の統計検定を行う時は必ず** `.claude/skills/ab-test-analysis/SKILL.md` を読み、手順に従って検定を実行する
- **新戦略・新指標の先行研究調査が必要な時は必ず** `.claude/skills/research-deep/SKILL.md` を読んでから並列 Web リサーチを実行する
- **大規模 sweep/grid 計画を立てる時は必ず** `.claude/skills/sp-writing-plans/SKILL.md` を読んでフェーズ分割計画を作成し、`.claude/skills/sp-executing-plans/SKILL.md` の手順で実行する
- **比較レポートに図表が必要な時は必ず** `.claude/skills/mermaid-agents365/SKILL.md` を読んでからダイアグラムを作成する
- **成果物の納品・コミット前、または品質チェック（QC）・レビューフェーズに入る時は必ず** `.claude/skills/sp-verification-before-completion/SKILL.md` のチェックリストを実行する
- **分析・レポートの品質チェック（QC）・レビュー・共有前は必ず** `.claude/skills/analysis-qa-checklist/SKILL.md` を読んでチェックリストを実施する
- **データ品質・整合性の確認が必要な時は必ず** `.claude/skills/data-quality-audit/SKILL.md` を読んで監査を実行する
<!-- SKILLS_RULES_END -->

## 🚀 自動実行ポリシー

### 確認不要で即実行する操作
- 全ファイル操作（作成・編集・削除）
- 全シェルコマンド（PowerShell, Bash, git, gh, npm, node, python）
- Git操作: add / commit / push / pull / fetch / merge / branch -D / reset --hard
- GitHub操作: gh pr create / gh api 全般 / ブランチ削除
- パッケージ操作: npm install / pip install / Web検索・フェッチ

### 事前確認が必要な操作（例外のみ）
- `git push --force` を main / master ブランチに対して実行する場合
- `gh repo delete` 実行時

### 動作原則
- 計画提示（簡潔）→ 即実行 → 結果報告 のフロー厳守
- 事前確認文（「Should I run...?」等）を出力しない

## ドキュメント日付ルール

レポート系 .md ファイル新規生成時は H1 タイトル直下に必ず記載:
```
作成日: YYYY-MM-DD
最終更新日: YYYY-MM-DD
```
- 更新時は最終更新日のみ当日付に書き換え（作成日は変更しない）
- 除外: README.md / CLAUDE.md / FILE_INDEX.md / tasks.md / CHANGELOG.md

