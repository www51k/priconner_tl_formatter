#!/usr/bin/env python3
"""元TLの空白・キャラ欄を正規化する。SET判断は行わない。"""

from __future__ import annotations

import argparse
import re
from dataclasses import replace
from pathlib import Path

from tl_common import (
    DISPLAY_NAMES,
    MASK_RE,
    TIME_RE,
    TIME_TOKEN_RE,
    character_names_from_formation,
    display_names_from_tl_declarations,
    normalize_input_line,
    parse_event,
    render_event,
)


def split_inline_character_arrow(line: str) -> list[str]:
    """キャラ→キャラを、時刻行と矢印行へ分ける。"""
    candidates = sorted(set(DISPLAY_NAMES), key=len, reverse=True)
    for left in candidates:
        match = re.search(re.escape(left) + r"[ \t　]*(?:→|⇒|->|➡︎|➡|⇨|↦)[ \t　]*", line)
        if not match:
            continue
        after_arrow = line[match.end():]
        right = next((name for name in candidates if after_arrow.startswith(name)), None)
        if right is None:
            continue
        first = line[:match.start()] + left
        second = "　　　→　" + right + after_arrow[len(right):]
        return [first, second]
    return [line]


def remove_redundant_auto_operations(lines: list[str]) -> list[str]:
    """同じオート状態の連続操作を除去する。

    SETマスクは変更せず、実際に状態が変わったときだけ🅰️ON/OFFを残す。
    コメント本文中の🅰️表記は対象外とする。
    """
    result: list[str] = []
    auto_state: str | None = None
    for line in lines:
        head, separator, comment = line.partition("//")
        if not separator:
            head, separator, comment = line.partition("''")
        match = re.search(r"🅰️(ON|OFF)", head)
        if match:
            state = match.group(1)
            if state == auto_state:
                head = head[: match.start()] + head[match.end():]
                head = re.sub(r"[ \t　]{2,}", "　", head)
                head = head.rstrip(" \t　")
                if separator and head:
                    head += "　"
            else:
                auto_state = state
        result.append(head + (separator + comment if separator else ""))
    return result


def format_text(text: str) -> str:
    output: list[str] = []
    character_names = character_names_from_formation(text)
    display_names = DISPLAY_NAMES | display_names_from_tl_declarations(text)
    symbolic_tl = any(
        re.match(r"^[ \t　]*(?:⭐️|⭐︎|⭐|★|☆|🔺|△)", line)
        for line in text.splitlines()
    )
    # TL表記の宣言で追加された短縮名も、キャラ欄の候補として認識する。
    character_names.update({name: "" for name in display_names})
    normalized_lines = []
    for source_line in text.splitlines():
        # 投稿由来の区切り記号だけの行は、整形結果には残さない。
        if re.fullmatch(r"\\+", source_line.strip()):
            continue
        normalized = normalize_input_line(source_line)
        normalized_lines.extend(split_inline_character_arrow(normalized))
    manual_time_buckets: set[int] = set()
    for normalized_line in normalized_lines:
        event = parse_event(0, normalized_line, character_names)
        if not event.star:
            continue
        time_match = TIME_TOKEN_RE.search(normalized_line)
        if time_match:
            manual_time_buckets.add(
                (int(time_match.group(1)) * 60 + int(time_match.group(2))) // 10
            )
    arrow_chain_active = False
    previous_event_was_star = False
    previous_event_was_indented = False
    previous_event_seconds: int | None = None
    previous_time_bucket: int | None = None
    for line_no, line in enumerate(normalized_lines, 1):
        event = parse_event(line_no, line, character_names)
        # 「1:30 開始 [54--1] 🅰️OFF」のような開始時設定は、開始行を
        # 残すとSET操作が埋もれるため、SET→オートの順で先頭へ出す。
        # コメント本文（//以降）はそのまま保持する。
        if (
            not event.name
            and re.search(r"(?:バトル開始|開始時|開始)", line)
            and (event.mask or re.search(r"🅰️(?:ON|OFF)", line))
        ):
            head, separator, comment = line.partition("//")
            auto_match = re.search(r"🅰️(?:ON|OFF)", head)
            start_set = f"[{event.mask}]" if event.mask else ""
            auto = auto_match.group(0) if auto_match else ""
            remainder = MASK_RE.sub("", head)
            remainder = re.sub(r"🅰️(?:ON|OFF)", "", remainder)
            remainder = re.sub(r"[\"“”「」『』]?\s*(?:AUTO|オート)\s*[\"“”「」『』]?", "", remainder, flags=re.IGNORECASE)
            remainder = re.sub(r"(?:バトル開始|開始時|開始)", "", remainder)
            remainder = re.sub(r"^\s*\d{1,2}:\d{1,2}(?:[-〜~]\d{1,2})?", "", remainder)
            remainder = remainder.strip(" \t　\"“”「」『』'")
            rendered = start_set + auto
            if remainder:
                rendered += "　" + remainder
            if separator:
                rendered += separator + comment
            output.append(rendered)
            arrow_chain_active = False
            previous_event_was_star = False
            previous_event_was_indented = False
            previous_event_seconds = None
            continue
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
            if arrow_chain_active and (not has_time and not event.star or same_time):
                arrow_indent = "　　　" if previous_event_was_star or previous_event_was_indented else "　　"
                if event.star and same_time:
                    # 同時刻の⭐️行は手動UB記号を残し、時刻を重複させず
                    # 矢印連鎖の続きとして表示する。
                    event = replace(event, prefix=f"⭐️　　→", arrow=True)
                else:
                    event = replace(event, prefix=f"{arrow_indent}→", arrow=True)
            elif event.arrow and not event.star:
                arrow_indent = "　　　" if previous_event_was_star or previous_event_was_indented else "　　"
                event = replace(event, prefix=f"{arrow_indent}→", arrow=True)
            arrow_chain_active = True
            if current_seconds is not None:
                previous_event_seconds = current_seconds
                previous_time_bucket = current_time_bucket
            # SETの内容は変更せず、手動操作だけ次行先頭へ移す。
            # 手動UBとSETを同じ行に置くと見落としやすいため、配置だけを
            # 変更し、マスク自体の再計算は行わない。
            inline_mask = None if event.star else (f"[{event.mask}]" if event.mask else None)
            rendered = render_event(
                event,
                inline_mask,
                display_names=display_names,
            )
            if event.star:
                # ⭐️行のキャラ名以降にある説明は手動操作タイミングの
                # コメントとして扱う。既存コメントとオート操作は除外する。
                display_name = display_names.get(event.name, event.name)
                name_index = rendered.find(display_name)
                if name_index >= 0:
                    name_end = name_index + len(display_name)
                    tail = rendered[name_end:]
                    tail_content = tail.lstrip(" 	　")
                    if tail_content and not tail_content.startswith(("//", "''")):
                        auto_match = re.match(r"🅰️(?:ON|OFF)", tail_content)
                        if auto_match:
                            operation = auto_match.group(0)
                            comment = tail_content[auto_match.end():].lstrip(" 	　")
                            if comment:
                                rendered = (
                                    rendered[:name_end]
                                    + "　"
                                    + operation
                                    + "　''"
                                    + comment
                                )
                        else:
                            rendered = rendered[:name_end] + "　''" + tail_content
            if (
                has_time
                and not event.star
                and symbolic_tl
                and not line.startswith(("　", "△", "🔺"))
            ):
                rendered = "　" + rendered
            rendered_has_leading_indent = (
                line.startswith(("　", "△", "🔺"))
                or (
                    has_time
                    and not event.star
                    and symbolic_tl
                    and not line.startswith(("△", "🔺"))
                )
            )
            if not event.arrow:
                previous_event_was_star = event.star
                previous_event_was_indented = rendered_has_leading_indent
            output.append(rendered)
            if event.star and event.mask:
                output.append(f"[{event.mask}]")
        else:
            arrow_chain_active = False
            previous_event_was_star = False
            previous_event_was_indented = False
            previous_event_seconds = None
            output.append(line.rstrip("\r"))
    output = remove_redundant_auto_operations(output)
    return "\n".join(output) + ("\n" if text.endswith(("\n", "\r")) else "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(format_text(args.input.read_text()), encoding="utf-8")


if __name__ == "__main__":
    main()
