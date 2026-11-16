# Loop Engineering — priconner_tl_formatter

対象: TL清書・SET変更・同時刻矢印。原本の意味と注記を維持
正本候補: AGENTS.md / SET_RULES.md / CHECKLIST.md / WORKFLOW.md / scripts/test_tl_processing.py。現在の状態はローカル差分とタスク履歴から確認し、例示を未完了の確証としない。

## 1回の開発サイクル
1. 現状: AGENTS.md、正本、前回失敗、git status、禁止/停止指示を確認。
2. 選定: READYがなくても、未完了・未検証の記録から重複しない独立小タスク1件を選ぶ。候補: 同時刻矢印・[54321]等のSETマスク・全角数字・コメント保持から未完了の1件。
3. 仮説: 再現条件、根拠、合格条件と最小変更を定義。
4. 実装: 許可されたコードだけを変更し、未コミット変更と原本を保全。
5. 検証: python3 -m unittest scripts/test_tl_processing.py と関連する既存scripts/test_*.py。実行不能な試験は理由を明示。
6. 評価: PASS / BLOCKED_INPUT / BLOCKED_ENV / TEST_INFRA_ERROR / TASK_FAIL に分類し、実施証拠を保持。
7. 引継ぎ: 変更ファイル・実行テスト・結果・残課題・次の独立タスク1件を記録。

## 継続条件
元TLの意味、コメント、手動UB/SETを勝手に変えない。公開・投稿は禁止。同一失敗の無条件再試行禁止（新情報がある場合も最大1回）。1案件ブロックで他案件のREADYを止めない。緊急停止・ユーザー停止・承認待ち・結果不明の書込は再開しない。管理MDやHeartbeatだけを開発成果に算入しない。各Codex呼出しは1サイクルで終わり、継続起動は承認済みOSスケジューラーが担当。

報告: task_id / 仮説 / 変更ファイル / 実行テストと結果 / 分類 / ブロッカー / 次タスク。
