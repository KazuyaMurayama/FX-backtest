# FX-backtest — Claude Code 運用ルール

SBI証券FX を対象に代表的戦略のバックテストを行い、Sharpe / CAGR / 最悪DD で評価するプロジェクト。

> **本ファイルは VSCode版 / Web版 Claude Code（claude.ai）の両方で本リポジトリの単独完結ガイド**。
> Web版はグローバル `~/.claude/CLAUDE.md` を参照しない前提で、本リポの運用に必要な全ルールをここに集約。

---

## 0. セッション開始時の参照順序
1. `tasks.md` — 未完了タスク・優先度
2. `FILE_INDEX.md` — ファイル構成・依存関係
3. `SPEC.md` — 仕様・設計方針
4. このCLAUDE.md — ルール入口

---

## 1. プロジェクト固有ルール

### コーディングルール
- 言語: Python 3.11+
- データ取得: `fredapi`（USD/JPY 1971〜）＋ `yfinance`（複数通貨）
- バックテスト: `vectorbt` または `backtesting.py`
- 結果: `results/` ディレクトリにCSV保存

### 評価指標
- Sharpe / CAGR / 最悪DD（MaxDD） を必ず併記
- 単一指標での優劣判定禁止

### タイムアウト対策
- データ取得・バックテストは戦略ごとに分割実行
- 各ステップで CSV 中間保存 → 再実行時はキャッシュ参照

### コミットメッセージ規約
- `feat: ` / `fix: ` / `docs: ` プレフィックス必須
- 日本語/英語どちらでも可（"why" を重視）

---

## 2. 開発者情報・命名ルール

| 種別 | 表記 | 用途 |
|---|---|---|
| **システム識別子（変更不可）** | `KazuyaMurayama` | GitHub ユーザー名 / URL / `@KazuyaMurayama` |
| **システム識別子（変更不可）** | `kazuya.murayama.21@gmail.com` | git `user.email` / 連絡先 |
| **表記名（人間として記載する場合）** | **男座員也（Kazuya Oza / おざ かずや）** | ドキュメント本文の著者名 / コミット message 中の自己言及 |

- 「Murayama」「村山」「Otokoza」「おとこざ」を**表記名**として誤用しない（システム識別子としての `KazuyaMurayama` は許容）
- 機密情報（APIキー、.env 等）はコミットしない

---

## 3. モデル使い分け（期間限定: 全タスク Opus）
- **全タスク Opus**。サブエージェントも `model: "opus"` を明示
- 通常運用への戻し方: 「メイン: Opus / サブ: Sonnet (model: "sonnet")」

---

## 4. ツール実行・Shell・Git・ファイル保存

### ツール実行ポリシー
- 確認不要・即実行（事前確認文を出力しない）
- ファイル操作は Edit/Write/Read/Grep/Glob を直接使用
- 例外（事前確認必須）: main への `git push --force`、`gh repo delete`

### Shell
- VSCode版: Windows 11 + PowerShell 5.1（`&&` 不可 → `;` + `if ($?)`）/ Bash併用可
- Web版: Linux サンドボックス

### ブランチ管理（絶対厳守）
- **デフォルト: mainへ直接コミット**
- ブランチ作成禁止（`git checkout -b` / `git switch -c` / `git branch` も禁止）
- 万一ブランチを作成した場合、必ず `main` へマージ → ブランチ削除 → push を完了
- 「完了 = mainにマージ済み＆push済み」
- Web版が自動生成したブランチ（`claude/xxx`）も同様

### ファイル保存ルール
- 成果物・スクリプトは本リポジトリ内のみに保存
- `C:\Users\user\Desktop` への出力禁止（ユーザー明示指定時を除く）

---

## 5. 成果物報告ルール（最重要・毎回必須）

ファイルを1つでも作成・更新・pushしたら、**すべての**成果物を以下の形式で報告：

| 成果物 | 説明 | リンク |
|---|---|---|
| file.md | 1行説明 | [開く](https://github.com/KazuyaMurayama/FX-backtest/blob/main/path/to/file.md) |

### 厳守事項
1. Markdownリンク `[表示名](URL)` 形式必須（plain text URL 禁止）
2. `/blob/<実ブランチ>/<実パス>` 形式（リポジトリトップURL禁止）
3. **報告前にURL存在確認必須**：`Invoke-WebRequest -Uri https://api.github.com/repos/KazuyaMurayama/FX-backtest/contents/PATH?ref=BRANCH -UseBasicParsing` でステータス200確認
4. ブランチ名は推測禁止：`git rev-parse --abbrev-ref HEAD` で実値取得
5. push完了後のみURL生成

---

## 6. ドキュメント日付ルール
レポート系 .md ファイルを新規作成する際は、H1直下に必ず記載:
```
作成日: YYYY-MM-DD
最終更新日: YYYY-MM-DD
```
- 更新時は **最終更新日のみ** を当日付に書き換える（作成日は固定）
- 除外: README / CLAUDE.md / FILE_INDEX.md / tasks.md / SPEC.md / CHANGELOG / LICENSE

---

## 7. Skill 起動ルール（必須・スキップ禁止）
該当シーンでは `.claude/skills/<name>/SKILL.md` を読んでから作業を開始する。
（Web版は本リポの `.claude/skills/`、VSCode版は `~/.claude/skills/` も参照可）

| トリガー | スキル |
|---|---|
| 時系列・トレンド分析 | `.claude/skills/time-series-analysis/SKILL.md` |
| 戦略比較の統計検定 | `.claude/skills/ab-test-analysis/SKILL.md` |
| 新戦略の先行研究調査 | `.claude/skills/research-deep/SKILL.md` |
| バックテスト計画の立案 | `.claude/skills/sp-writing-plans/SKILL.md` + `sp-executing-plans/SKILL.md` |
| 比較レポートの図表生成 | `.claude/skills/mermaid-agents365/SKILL.md` |
| 結果のQC・レビュー・共有前 | `.claude/skills/analysis-qa-checklist/SKILL.md` |
| 成果物の納品・コミット前 | `.claude/skills/sp-verification-before-completion/SKILL.md` |
| データ品質確認 | `.claude/skills/data-quality-audit/SKILL.md` |
| バグ・エラー調査 | `.claude/skills/sp-systematic-debugging/SKILL.md` |
| 出力形式の整形 | `skills/output-format.md`（旧リポ内ファイル） |

---

## 8. 関連リポジトリ
- [KazuyaMurayama/NASDAQ_backtest](https://github.com/KazuyaMurayama/NASDAQ_backtest) — NASDAQ 3倍レバレッジ戦略のバックテスト研究本体（評価指標体系・9指標標準 等の参照源）
