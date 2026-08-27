#!/usr/bin/env python3
"""Create a local-only comparison payload from the collected Discord TL data.

The payload deliberately contains only TL text and channel names. Authors,
message links, IDs, and the raw collection are never copied to the repository.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from format_tl import format_text


def choose_records(records: list[dict], limit: int) -> list[dict]:
    usable = [
        record for record in records
        if record.get("has_tl_candidate")
        and record.get("tl_text", "").strip()
        and not set(record.get("review_flags", [])) & {"possibly_truncated"}
    ]
    # Keep the comparison broad: prefer longer TLs, then ensure each source
    # channel contributes before filling remaining slots.
    usable.sort(key=lambda item: (-len(item.get("tl_lines", [])), item.get("channel_name", ""), item.get("tl_text", "")))
    selected: list[dict] = []
    channels: set[str] = set()
    for record in usable:
        channel = record.get("channel_name", "unknown")
        if channel in channels:
            continue
        selected.append(record)
        channels.add(channel)
        if len(selected) >= limit:
            return selected
    for record in usable:
        if record in selected:
            continue
        selected.append(record)
        if len(selected) >= limit:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    records = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    examples = []
    for index, record in enumerate(choose_records(records, args.limit), 1):
        original = record["tl_text"].strip("\n") + "\n"
        examples.append({
            "name": f"Discord学習データ_{index:02d}",
            "source": record.get("channel_name", "Discord"),
            "original": original,
            "formatted": format_text(original),
            "originalTitle": f"学習データ（{record.get('channel_name', 'Discord')}）",
            "formattedTitle": "整形後（現行ルール）",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(examples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(examples)} examples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
