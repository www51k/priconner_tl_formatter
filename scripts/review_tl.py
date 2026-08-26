#!/usr/bin/env python3
"""TLを機械走査し、AI・人間確認が必要な行だけを抽出する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tl_common import CHAR_NUMBERS, parse_event
from validate_tl import validate


def collect_review_items(
    text: str,
    original_text: str | None = None,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    lines = text.splitlines()
    original_lines = original_text.splitlines() if original_text is not None else []
    for line_no, line in enumerate(lines, 1):
        event = parse_event(line_no, line)
        if event.arrow and event.name is None:
            stripped = line.strip()
            if "ボス" not in stripped and "止めぽ" not in stripped:
                items.append({
                    "line": line_no,
                    "kind": "UNRESOLVED_EVENT",
                    "text": line,
                    "reason": "発動行のキャラ名を機械解析できません",
                })
        original_line = original_lines[line_no - 1] if line_no <= len(original_lines) else ""
        original_event = parse_event(line_no, original_line)
        if (
            event.mask is not None
            and event.name in CHAR_NUMBERS
            and original_event.mask is not None
        ):
            items.append({
                "line": line_no,
                "kind": "ORIGINAL_SET",
                "text": line,
                "reason": "原本SETを固定し、自動更新しません",
            })
        if "🅰️ON" in line:
            items.append({
                "line": line_no,
                "kind": "AUTO_ON",
                "text": line,
                "reason": "オートONの根拠を原本・実戦検証で確認します",
            })

    for error in validate(text):
        line_number = int(error.split(":", 1)[0])
        items.append({
            "line": line_number,
            "kind": "VALIDATION_ERROR",
            "text": lines[line_number - 1] if 0 < line_number <= len(lines) else "",
            "reason": error,
        })
    return items


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, help="原本または整形直後の入力ファイル")
    parser.add_argument("--json", action="store_true", help="JSON形式で出力する")
    args = parser.parse_args()
    text = args.input.read_text(encoding="utf-8")
    original_text = args.source.read_text(encoding="utf-8") if args.source else None
    items = collect_review_items(text, original_text)
    if args.json:
        args.output.write_text(
            json.dumps(items, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        lines = [
            f"行{item['line']}: {item['kind']} / {item['reason']} / {item['text']}"
            for item in items
        ]
        args.output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


if __name__ == "__main__":
    main()
