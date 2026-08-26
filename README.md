# TL清書

プリンセスコネクト！Re:DiveのクランバトルTLを、元の手動TLの情報を保ったまま、ゲーム内で扱いやすいSET操作付きTLへ整形するための作業用フォルダです。

## 対象

- 入力: 時刻、キャラ名、⭐️手動UB、矢印、コメント、止めぽを含むテキストファイル
- 出力: 編成対応表、開始SET、必要最小限のSET変更、元TLの注記を含む整形済みTL
- 基本方針: 元の発動順と意味を変えず、誤発を避けるためにSET対象を必要最小限にする

## 現在の入力ファイル

- [`202608_1b58000_16`](./202608_1b58000_16): アオイ・ネラ・ツムギ・ペコ・シェフィ編成の元TL

## 作業手順

1. 対象テキストを読み、編成表と各行の発動種別を確認する。
2. [`SET_RULES.md`](./SET_RULES.md)に従って、上から下へSET状態を追跡する。
3. 必要なSET操作だけをキャラ名の横へ追加する。
4. [`CHECKLIST.md`](./CHECKLIST.md)で手動UB、SET発動、矢印、固定位置表記を検査する。
5. 完成版は入力ファイルを上書きせず、別名のテキストファイルとして保存する。

詳細な処理順は[`WORKFLOW.md`](./WORKFLOW.md)を参照してください。

## スクリプト

処理は、決定的な整形とSET状態の追加を分離しています。

```bash
python3 scripts/format_tl.py input.txt formatted.txt
python3 scripts/add_set_operations.py formatted.txt set_tl.txt --report set_tl.report.txt
python3 scripts/validate_tl.py set_tl.txt
python3 scripts/review_tl.py set_tl.txt review_queue.json --source formatted.txt --json
python3 -m unittest scripts/test_tl_processing.py
```

## GitHub Actions

GitHubの`Actions`タブから`Format TL`を選び、`Run workflow`を実行すると、入力ファイルを指定して整形できます。

処理結果は次のファイルを含むArtifact（`tl-format-result`）として保存されます。

- 整形済みTL
- SET操作追加済みTL
- SET操作レポート
- レビュー対象JSON

SET整合性検査に失敗した場合、Workflowは失敗扱いになります。入力ファイルは上書きされません。

- `format_tl.py`: キャラ欄・空白・時刻範囲・括弧・⭐️・🅰️ON/OFF・構造記号を整形する。コメント本文は変更せず、SET判断はしない。
- `add_set_operations.py`: 上から下へSET状態を継続し、必要な変更だけを追加する。
- `--report`: ADD・REMOVE・SET_ALL・CLEAR_ALL・REPLACEの種別と判断理由を別ファイルへ出力する。
- `--ignore-original-set`: 開始SET以外の原本SETを無視し、SET操作を再計算する。
- `validate_tl.py`: SETマスクの固定位置、⭐️手動UB、⭐️なし発動、重複SETを検査する。
- `test_tl_processing.py`: 原本からの再現、代表TLの検証、操作理由レポートを確認する。
- `review_tl.py`: 機械的に解決できない行、原本固定SET、🅰️ON、検証エラーだけを抽出する。

曖昧なコメントは実戦メモとして解釈せず原文のまま保持します。清書ではSET状態と書式だけを確定し、実際の発動順・ダメージ・ボス状態・UB可能タイミングは再現動画または実プレイの検証フェーズで確認します。

コメントは原則として原文を保持します。意味の編集・要約・推測による書き換えは、明示的な指示がある場合だけ行います。

## 編成番号

現在の対象編成は、左から固定で5・4・3・2・1です。

```text
[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]
```

SETマスクの位置は、発動順ではなく常に`5 4 3 2 1`の順で記載します。
