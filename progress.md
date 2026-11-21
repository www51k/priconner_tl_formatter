# progress.md — priconner_tl_formatter

<!-- progress-collection:v1
{"project_id":"priconner_tl_formatter","monitor":true,"instruction_target":"existing-codex","dispatch_policy":"verified-only","host":null,"thread_id":null,"status":"PAUSED_BY_USER","last_verified_at":null}
-->


## 管理状態（2026-11-22 利用者指定）
- **監視対象のまま保留（PAUSED_BY_USER）**。進捗・状態の確認は可能だが、タスクの起動・再開は禁止。
- 現時点で急ぎの実装作業なし。ユーザーの再開指示まで実装・テストの自動起動や既存Codexへの作業指示を行わない。
- 現地PCのCodex/OSタスクループが停止していることは未検証。ローカル設定の `enabled: false` /停止マーカー/スレッド所有者を確認するまでは停止完了とみなさない。
- 再開は利用者の明示指示と既存担当・停止条件の再照合後のみ。

## 収集・指示
- `progress-collection` の監視対象。既存Codex担当への指示候補（PC/thread未照合で未送信）。
- status=`NEEDS_TRIAGE` は未完了の調査待ち。実行中・完了・READYと混同しない。停止/承認状態は現地優先。

## 次に照合する実装・検証候補
- [ ] TL整形・SETマスク・同時刻矢印・全角数字の既存テストから実行可能な未完了1件を選ぶ。原文意味の変更や無確認公開はしない。
- これは実際の未完了タスクであるという保証ではない。既存の正本、ソースコード、テスト、未コミット変更と照合する。

## 実行履歴（現地で更新）
| 時刻 | task_id | 状態 | 変更ファイル | テストと結果 | ブロッカー | 次の独立タスク |
| --- | --- | --- | --- | --- | --- | --- |
| 未確認 | 未確定 | NEEDS_TRIAGE | なし | 未実施 | PC/thread/作業状況未照合 | 正本から実行可能な小タスク1件を選ぶ |

## 開発ループ
現状→仮説→最小変更→テスト→評価/分類→次の小タスク。結果に基づき管理ブロックと実行履歴を更新する。監視/MD編集だけではPASSとしない。本番・実機・外部送信・停止済み作業の無断再開禁止。
