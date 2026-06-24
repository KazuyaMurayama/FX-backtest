# FX-backtest — Claude Code 運用ルール

SBI証券FX を対象に代表的戦略のバックテストを行い、Sharpe / CAGR / 最悪DD で評価するプロジェクト。

> **本ファイルは VSCode版 / Web版 Claude Code（claude.ai）の両方で本リポジトリの単独完結ガイドです。**
> Web版はグローバル `~/.claude/CLAUDE.md` を参照しません。本リポの運用に必要な全ルールをこの1ファイルに集約しています（他リポ・グローバルとの重複は完結性のため許容）。

---

## 1. セッション開始手順（毎回・最初に実行）

セッション開始時、次の順で必ず読み込んでから作業を始める：

1. **本ファイル（CLAUDE.md）** — 前提制約・実行ルール
2. **`tasks.md`** — 未完了タスク・優先度
3. **`FILE_INDEX.md`** — ファイル構成・依存関係
4. **`SPEC.md`** — 仕様・設計方針

> 編集前に、ユーザー発話のキーワードを `FILE_INDEX.md` と照合してから対象ファイルを特定する（推測で着手しない）。

---

## 2. 開発者情報・命名ルール

| 種別 | 表記 | 用途 |
|---|---|---|
| **システム識別子（変更不可）** | `KazuyaMurayama` | GitHub ユーザー名 / URL / `@KazuyaMurayama` |
| **システム識別子（変更不可）** | `kazuya.murayama.21@gmail.com` | git `user.email` / 連絡先 |
| **表記名（人間として記載する場合）** | **男座員也（Kazuya Oza / おざ かずや）** | ドキュメント本文の著者名 / コミット message 中の自己言及 |

- ドキュメント本文等で開発者名を**人間として**記載する際は **男座員也 / Kazuya Oza** を使用。
- 「Murayama」「村山」「Otokoza」「おとこざ」を**表記名**として誤用しない（システム識別子 `KazuyaMurayama` の出現は許容）。
- 機密情報（APIキー、.env 等）はコミットしない。

---

## 3. ツール実行ルール

- **確認不要・即実行**。「Allow〜?」「Should I…?」等の事前確認文を出力しない。即実行 → 事後報告。
- 長時間処理は積極的にバックグラウンド実行する。
- ファイル操作（編集・検索・読み込み）は専用ツール（Edit/Write/Read/Grep/Glob）を直接使用する。
- Shell は PowerShell 5.1 基準（`&&` 不可 → `;` + `if ($?)`）/ Bash 併用可。
- **例外（事前確認必須）**: main への `git push --force`、`gh repo delete`。

---

## 4. ブランチ管理

- **既定: main へ直接コミット**。ブランチ作成はユーザーが明示指示した場合のみ。
- ブランチを作成した場合、回答完了前に必ず `main` へマージ → ブランチ削除 → push まで完了させる。
  - 手順: `git checkout main; git pull; git merge <branch> --no-ff; git push origin main; git branch -d <branch>`
- 「完了 = main にマージ済み＆push済み」。ブランチにファイルを残したまま回答を終えない。

<!-- BRANCH_CLEANUP_START -->
### ブランチ整理スキル（自主起動）
- 次を **検知** したら、ユーザー指示が無くても **必ず** `.claude/skills/branch-cleanup/SKILL.md` を読んで起動する：`git branch -a` / `git ls-remote --heads origin` で **main 以外のブランチが残存** している／ユーザーが「ブランチ削除・整理・main に集約」を依頼した／自分が作ったブランチを完了前に放置しようとしている。
- **Web版 Claude Code（claude.ai/code）でもブランチ削除は実行可能**。「環境の制約でできない／ユーザー自身で対応を」とは回答しない。3段階で試す：① `git push origin --delete <branch>` → ② 拒否なら REST API 直接 DELETE（`gh api -X DELETE` / token curl）→ ③ それも不可な環境のみ Actions ワークフローでフォールバック（使用後は削除してリポを汚さない）。
- 手順全文・コマンド・フォールバック YAML は `.claude/skills/branch-cleanup/SKILL.md` に集約（本ファイルを肥大化させない）。
<!-- BRANCH_CLEANUP_END -->

---

## 5. ファイル保存ルール

- 生成物・スクリプト・中間ファイルはすべて**本リポジトリ内**に保存する。
- `C:\Users\user\Desktop` への出力は禁止（ユーザーが明示した場合のみ例外）。
- ログ・コミットメッセージ等の一時ファイルを無断で作らない。

---

## 6. 成果物報告ルール（毎回必須）

ファイルを1つでも作成・更新・push したら、**すべての**成果物を次の3列表で報告する。例外なし。

| 成果物 | 説明 | リンク |
|---|---|---|
| file.md | 1行説明 | [開く](https://github.com/KazuyaMurayama/FX-backtest/blob/main/path/to/file.md) |

**厳守事項**
1. 必ず Markdownリンク `[表示名](URL)` 形式。plain text URL 禁止。
2. `/blob/<実ブランチ>/<実パス>` 形式。リポトップ URL 禁止。
3. **報告前に URL 存在確認**: `gh api repos/KazuyaMurayama/FX-backtest/contents/PATH?ref=BRANCH` で存在確認。
4. ブランチ名は推測せず `git rev-parse --abbrev-ref HEAD` で実値取得。
5. **push 完了後にのみ URL 生成**。未push ファイルは絶対パス＋「（ローカル）」と明記。
6. 404 を出したら即訂正版を提示し、原因を1行報告。

---

## 7. ドキュメント命名・日付ルール（v2.0 / 2026-06-03 改訂）

### ファイル名
- 基本形 `<TOPIC>_YYYYMMDD.md`（**サフィックス・ハイフンなし**）。例: `STRATEGY_REPORT_20260603.md`
- 同日中の追加更新は `-v2`、`-v3`（例: `STRATEGY_REPORT_20260603-v2.md`）。
- 日付が変わったら v サフィックスをリセット（例: 翌日1回目 `STRATEGY_REPORT_20260604.md`）。

### 表記の区別
- **ファイル名**: ハイフン**なし** `YYYYMMDD`（例: `20260603`）。
- **本文中の日付**: ハイフン**あり** `YYYY-MM-DD`（例: `2026-06-03`）。

### H1直下の日付メタデータ
レポート系 .md 新規作成時は H1直下に必ず記載し、更新時は **最終更新日のみ** 当日付に書き換える（作成日は固定）：
```
作成日: YYYY-MM-DD
最終更新日: YYYY-MM-DD
```

### 対象外（日付サフィックスを入れない）
README / CLAUDE.md / FILE_INDEX / tasks.md / CHANGELOG / LICENSE / SPEC.md / `CURRENT_*.md` / パイプライン自動生成ファイル。

### 旧形式（廃止・新規禁止）
- ❌ `<TOPIC>_2026-06-03.md`（ハイフン区切り）
- ✅ `<TOPIC>_20260603.md`（現行ルール）

---

## 8. モデル使い分け

- **メイン: Claude Fable 5（`claude-fable-5`）** — 計画・中〜高難易度の実装/分析・全体指揮。
- **実行フェーズ（定型実装・ファイル編集・テスト実行）**: サブエージェントを `model: "sonnet"` で起動して委譲。
- ※難易度ベースの自動メイン切替は不可。Fable の自動切替は安全性ブロック時の Opus 4.8 フォールバックのみ。工程別の使い分けはサブエージェント委譲で行う。

---

## 9. Skill 起動ルール

該当シーンでは、本リポ `.claude/skills/<name>/SKILL.md` を読んでから作業を開始する（**本リポに実在する skill のみ掲載**）。

| トリガー | スキル |
|---|---|
| 時系列・トレンド分析 | `.claude/skills/time-series-analysis/SKILL.md` |
| 戦略比較の統計検定 | `.claude/skills/ab-test-analysis/SKILL.md` |
| 先行研究・市場調査 | `.claude/skills/research-deep/SKILL.md` |
| バックテスト計画の立案 | `.claude/skills/sp-writing-plans/SKILL.md` |
| 計画に沿った実行 | `.claude/skills/sp-executing-plans/SKILL.md` |
| 新戦略・設計のアイデア出し | `.claude/skills/sp-brainstorming/SKILL.md` |
| 比較レポートの図表生成 | `.claude/skills/mermaid-agents365/SKILL.md` |
| 成果物の納品・コミット前チェック | `.claude/skills/sp-verification-before-completion/SKILL.md` |

---

## 10. プロジェクト固有ルール

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

## 11. 関連リポジトリ

- [KazuyaMurayama/NASDAQ_backtest](https://github.com/KazuyaMurayama/NASDAQ_backtest) — NASDAQ 3倍レバレッジ戦略のバックテスト研究本体（評価指標体系・9指標標準等の参照源）

---

## 12. 回答スタイル

- 日本語で回答する。
- 回答末尾に「**Next Action:**」でユーザーの次アクションを具体的に推奨する。迷う場面は「**推奨:**」で明示する。

## 13. コンテキスト管理（自動圧縮対策 / Compact Instructions）

Claude Code はコンテキスト利用率が高まると自動でテキスト要約圧縮（auto-compact, 約83.5%目安）を行う。圧縮で重要情報を失わないため以下を守る。

### 圧縮時に必ず保持する情報（`/compact` 実行・自動圧縮時に要約へ残す）
- 本リポ/タスクの目的・前提制約・現行の意思決定
- 進行中タスクと未解決課題（`tasks.md` の最新状態）
- 正典ファイル・最新成果物への参照（例: SPEC / `CURRENT_*.md` / 最新レポート）
- ファイルスコープ・モジュール境界・命名規則
- 直近のエラー・制約・回避策

### 圧縮の影響を受けない永続層（外部メモリ）に状態を書き出す
- `tasks.md`（次にやること・進捗。セッション終了時に必ず更新）
- `file_index.md` / `FILE_INDEX.md`（索引）、`session.json`（あれば進捗）
- 確定した結論・成果はレポート `.md` に保存（会話履歴に依存させない）

### 運用ルール
- 重い調査・実装はサブエージェントに委譲し、親には要約のみ戻す（コンテキスト分離）
- 利用率が高まったら警告を待たず能動的に `/compact <保持指示>` を実行。別タスクへ移る際は `/clear`（CLAUDE.md・tasks.md は残る）
- ※潜在空間ベクトル圧縮（Codex方式）は公開APIの制約上、本ハーネスでは実装不可。テキスト要約＋外部メモリで代替する