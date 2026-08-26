#!/usr/bin/env python3
"""元TLの空白・キャラ欄を正規化する。SET判断は行わない。"""

from __future__ import annotations

import argparse
from pathlib import Path

from tl_common import MASK_RE, normalize_input_line, parse_event, render_event


def format_text(text: str) -> str:
    output: list[str] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        line = normalize_input_line(line)
        event = parse_event(line_no, line)
        if event.name:
            output.append(render_event(event, f"[{event.mask}]" if event.mask else None))
        else:
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
