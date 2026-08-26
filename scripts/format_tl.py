#!/usr/bin/env python3
"""元TLの空白・キャラ欄を正規化する。SET判断は行わない。"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from tl_common import MASK_RE, TIME_RE, normalize_input_line, parse_event, render_event


def format_text(text: str) -> str:
    output: list[str] = []
    arrow_chain_active = False
    for line_no, line in enumerate(text.splitlines(), 1):
        line = normalize_input_line(line)
        event = parse_event(line_no, line)
        if event.name:
            has_time = TIME_RE.search(event.prefix) is not None
            if not has_time and arrow_chain_active:
                event = replace(event, prefix="　　→", arrow=True)
            arrow_chain_active = True if not has_time else True
            if has_time:
                arrow_chain_active = True
            output.append(render_event(event, f"[{event.mask}]" if event.mask else None))
        else:
            arrow_chain_active = False
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
