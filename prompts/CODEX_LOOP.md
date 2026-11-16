# priconner_tl_formatter: Codexループエンジニアリング起動指示

既存担当として AGENTS.md と docs/LOOP_ENGINEERING.md、正本（AGENTS.md / SET_RULES.md / CHECKLIST.md / WORKFLOW.md / scripts/test_tl_processing.py）を読み、**安全で実行可能な未完了タスク1件の実装・テスト**に着手してください。候補: 同時刻矢印・[54321]等のSETマスク・全角数字・コメント保持から未完了の1件。これは候補であり、未完了の事実は現在のコードと履歴で再確認すること。

READYが空なら既存の未完了を小さく分割して選び、入力/環境不足なら別の独立タスクに移る。現状→仮説→最小変更→検証→評価→次タスク、の1ループを完遂する。python3 -m unittest scripts/test_tl_processing.py と関連する既存scripts/test_*.py。元TLの意味、コメント、手動UB/SETを勝手に変えない。公開・投稿は禁止。

必須出力: task_id、変更ファイル、検証コマンドと結果、PASS/BLOCKED_INPUT/BLOCKED_ENV/TEST_INFRA_ERROR/TASK_FAIL、未検証範囲、次の具体的タスク。差分・テストを確認できないのにPASSとしない。勝手なpush・公開・外部書込・無限ループは禁止。次回実行はOSスケジューラーが設定されている場合のみ。

## progress.md 連携
- 最初に `progress.md`（既存ローカル `PROGRESS.md` が優先される場合はそちら）を確認し、未完了を既存コード/テストと照合する。
- 1件の実装と検証後、変更ファイル/テスト/状態/ブロッカー/次の独立タスクを進捗ファイルに反映。statusは根拠があるときだけ変更する。
- progress-collectionは監視と指示の候補。ホスト/既存Codex担当の認証がない場合は送信禁止。MD更新だけをPASSにしない。
