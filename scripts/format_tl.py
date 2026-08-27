#!/usr/bin/env python3
"""元TLの空白・キャラ欄を正規化する。SET判断は行わない。"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from tl_common import (
    MASK_RE,
    TIME_RE,
    TIME_TOKEN_RE,
    character_names_from_formation,
    normalize_input_line,
    parse_event,
    render_event,
)


def format_text(text: str) -> str:
    output: list[str] = []
    character_names = character_names_from_formation(text)
    arrow_chain_active = False
    previous_event_seconds: int | None = None
    previous_time_bucket: int | None = None
    for line_no, line in enumerate(text.splitlines(), 1):
        line = normalize_input_line(line)
        event = parse_event(line_no, line, character_names)
        if event.name:
            has_time = TIME_RE.search(event.prefix) is not None
            time_match = TIME_TOKEN_RE.search(event.prefix)
            current_seconds = (
                int(time_match.group(1)) * 60 + int(time_match.group(2))
                if time_match
                else None
            )
            current_time_bucket = (
                current_seconds // 10 if current_seconds is not None else previous_time_bucket
            )
            if (
                current_seconds is not None
                and previous_time_bucket is not None
                and current_time_bucket != previous_time_bucket
                and output
                and output[-1].strip()
            ):
                output.append("")
            same_time = (
                has_time
                and current_seconds is not None
                and current_seconds == previous_event_seconds
            )
            # 同一秒でも⭐️手動UBは矢印連鎖ではない。YouTube備考欄などで
            # 「直前行と同時刻の手動UB」が頻出するため、明示された⭐️を優先する。
            if arrow_chain_active and not event.star and (not has_time or same_time):
                event = replace(event, prefix="　　　→", arrow=True)
            arrow_chain_active = True
            if current_seconds is not None:
                previous_event_seconds = current_seconds
                previous_time_bucket = current_time_bucket
            # SETの内容は変更せず、手動操作だけ次行先頭へ移す。
            # 手動UBとSETを同じ行に置くと見落としやすいため、配置だけを
            # 変更し、マスク自体の再計算は行わない。
            inline_mask = None if event.star else (f"[{event.mask}]" if event.mask else None)
            output.append(render_event(
                event,
                inline_mask,
            ))
            if event.star and event.mask:
                output.append(f"[{event.mask}]")
        else:
            arrow_chain_active = False
            previous_event_seconds = None
            output.append(line.rstrip("\r"))
    return "\n".join(output) + ("\n" if text.endswith(("\n", "\r")) else "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(format_text(args.input.read_text()), encoding="utf-8")


if __name__ == "__main__":
    main()
