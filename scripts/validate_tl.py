#!/usr/bin/env python3
"""SET付きTLの機械的な整合性を検査する。"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from add_set_operations import auto_note_in_line
from tl_common import MASK_RE, character_names_from_formation, numbers_from_mask, parse_event


def validate(text: str) -> list[str]:
    errors: list[str] = []
    character_names = character_names_from_formation(text)
    character_numbers = dict(character_names)
    for line in text.splitlines():
        for match in re.finditer(r"\(([54321])\)([^|)\]]+)", line):
            character_numbers[match.group(2).strip()] = match.group(1)
    state: set[str] = set()
    previous_mask: str | None = None

    for line_no, line in enumerate(text.splitlines(), 1):
        event = parse_event(line_no, line, character_names)
        mask_match = MASK_RE.search(line)
        mask = mask_match.group(1) if mask_match else None

        # マスクは、その行の発動直後の状態。発動可否は直前の状態で判定する。
        if mask is not None and line.lstrip().startswith("[("):
            state = numbers_from_mask(mask)
            previous_mask = mask
            continue

        if not event.name or event.name not in character_numbers:
            if mask is not None:
                state = numbers_from_mask(mask)
                previous_mask = mask
            continue
        number = character_numbers[event.name]
        auto_event = auto_note_in_line(line)
        if event.manual and number in state:
            errors.append(f"{line_no}: ⭐️手動対象の{event.name}がSET内にあります")
        if (
            not event.manual
            and not event.arrow
            and not auto_event
            and number not in state
            and mask is None
        ):
            errors.append(f"{line_no}: ⭐️なしの{event.name}がSET外です")

        if mask is not None:
            if mask == previous_mask:
                errors.append(f"{line_no}: 直前と同じSET状態を重複記載しています")
            state = numbers_from_mask(mask)
            previous_mask = mask

    for line_no, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("[("):
            continue
        for match in re.finditer(r"\[([^]]*)\]", line):
            if not re.fullmatch(r"[54321-]{5}", match.group(1)):
                errors.append(f"{line_no}: SETマスクが固定5桁ではありません: {match.group(0)}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--annotate",
        action="store_true",
        help="問題を同じファイルの末尾へ注釈として追記する",
    )
    args = parser.parse_args()
    text = args.input.read_text(encoding="utf-8")
    errors = validate(text)
    if errors:
        print("\n".join(errors))
        if args.annotate:
            lines = text.splitlines()
            annotations = ["", "問題がある行", "-----"]
            for error in errors:
                line_number = int(error.split(":", 1)[0])
                source_line = lines[line_number - 1] if 0 < line_number <= len(lines) else ""
                annotations.extend([source_line, "記載内容についての指摘", error, "---"])
            args.input.write_text("\n".join(lines + annotations) + "\n", encoding="utf-8")
        raise SystemExit(1)
    print("OK: 機械的なSET整合性検査に合格しました")


if __name__ == "__main__":
    main()
