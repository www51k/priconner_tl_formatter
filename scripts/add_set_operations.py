#!/usr/bin/env python3
"""整形済みTLへ、状態を継続する保守的なSET操作を追加する。

矢印連鎖は次の対象を一人ずつ追加し、動画・実プレイ未検証の一括SETは行わない。
"""

from __future__ import annotations

import argparse
import re
from dataclasses import replace
from pathlib import Path

from tl_common import (
    TIME_TOKEN_RE,
    mask_for,
    numbers_from_mask,
    parse_event,
    character_names_from_formation,
    render_event,
    MASK_RE,
    DISPLAY_NAMES,
)


def ensure_initial_operation(text: str, initial: str = "-----") -> str:
    """既存SETを保持したまま、先頭の初期SETだけを補う。

    SET付き原本は再計算しない方針だが、編成ヘッダーや本文後半にだけ
    SETがある入力では、初期状態の行まで欠落させない。
    """
    lines = text.splitlines()
    if not lines:
        return text

    header_index = next(
        (index for index, line in enumerate(lines)
         if line.startswith("[(") and "|" in line),
        -1,
    )
    first_event_index = next(
        (
            index for index, line in enumerate(lines)
            if TIME_TOKEN_RE.search(line)
            or re.match(r"^\s*(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*(?:→|➡︎|⇨|⇒)", line)
        ),
        len(lines),
    )

    # 編成ヘッダー直後の単独SET、または先頭の独立SETは既存の初期SET。
    search_start = header_index + 1 if header_index >= 0 else 0
    for line in lines[search_start:first_event_index]:
        if re.fullmatch(r"\s*\[[54321-]{5}\](?:🅰️(?:ON|OFF))?\s*", line):
            return text

    # 時刻付きの「バトル開始 [.....]」や、ヘッダーなしの先頭SETは原本を維持。
    first_nonempty = next((index for index, line in enumerate(lines) if line.strip()), None)
    if header_index < 0 and first_nonempty is not None:
        first_line = lines[first_nonempty]
        if MASK_RE.search(first_line) and (
            first_line.lstrip().startswith("[") or "バトル開始" in first_line
        ):
            return text

    insertion = ["", f"[{initial}]🅰️OFF", ""] if header_index >= 0 else [f"[{initial}]🅰️OFF", ""]
    if header_index >= 0:
        lines[header_index + 1:header_index + 1] = insertion
    else:
        lines[0:0] = insertion
    return "\n".join(lines)


def auto_note_in_line(line: str) -> bool:
    """オート操作として扱う明示的なオート記法だけを検出する。"""
    comment_positions = [pos for pos in (line.find("//"), line.find("''")) if pos >= 0]
    comment_start = min(comment_positions) if comment_positions else len(line)
    head = line[:comment_start]
    if re.search(r'''["「『]オート["」』]''', head):
        return True
    if re.search(r"(?:^|[ \t　])(?:#?オート|[（(]オート[）)])(?:$|[ \t　])", head):
        return True
    return bool(re.match(r"''[ \t　]*オート(?:[ \t　]|$)", line[comment_start:]))


def add_auto_state(line: str, state: str, character_name: str | None = None) -> str:
    """コメント本文を変えず、コメント直前へオート状態を追加する。"""
    comment_positions = [pos for pos in (line.find("//"), line.find("''")) if pos >= 0]
    comment_start = min(comment_positions) if comment_positions else len(line)
    head = line[:comment_start]
    comment = line[comment_start:]
    existing_state = re.search(r"🅰️(?:ON|OFF)", head)
    if existing_state:
        if existing_state.group(0) == f"🅰️{state}":
            return line
        head = head[:existing_state.start()] + f"🅰️{state}" + head[existing_state.end():]
        return head + comment
    auto_note = re.search(r'''["「『]オート["」』]''', head)
    if MASK_RE.search(head):
        before_state = ""
    elif character_name:
        display_name = DISPLAY_NAMES.get(character_name, character_name)
        # キャラ名は4文字幅にそろえ、その後ろに区切りを1つ置く。
        before_state = "　" * (max(0, 4 - len(display_name)) + 1)
    else:
        before_state = "　　" if comment.startswith("''") else "　" if comment else ""
    after_state = "　" if comment else ""
    if auto_note:
        head = head[: auto_note.start()].rstrip(" \t　") + f"🅰️{state}　" + head[auto_note.start():]
    else:
        head = head.rstrip(" \t　") + before_state + f"🅰️{state}" + after_state
    return head + comment


def add_auto_operations(text: str) -> str:
    """オート記法を状態へ反映する。

    オート記法があっても、そのUB対象が直前のSET状態に含まれる場合は
    SETを優先し、オート区間を作らない。SETとオートを独立に付与すると、
    同じUBへ二つの発動条件を重ねてしまうため、SET後状態を先に走査する。
    """
    lines = text.splitlines()
    character_names = character_names_from_formation(text)
    events = [parse_event(line_no, line, character_names) for line_no, line in enumerate(lines, 1)]

    set_state: set[str] = set()
    effective_auto_indexes: list[int] = []
    for index, event in enumerate(events):
        mask_match = MASK_RE.search(lines[index])
        if not event.name or event.name == "ボス":
            if mask_match:
                set_state = numbers_from_mask(mask_match.group(1))
            continue
        number = character_names.get(event.name)
        auto_requested = auto_note_in_line(lines[index])
        # 手動UBはオート区間へ入れない。SET対象ならSETを優先し、
        # オート記法は説明として残すがON/OFF操作は生成しない。
        if (
            auto_requested
            and not event.manual
            and (number is None or number not in set_state)
        ):
            effective_auto_indexes.append(index)
        if mask_match:
            set_state = numbers_from_mask(mask_match.group(1))

    auto_indexes = [
        index
        for index, event in enumerate(events)
        if index in set(effective_auto_indexes)
    ]
    groups: list[list[int]] = []
    for index in auto_indexes:
        previous = next(
            (
                candidate
                for candidate in range(index - 1, -1, -1)
                if events[candidate].name and events[candidate].name != "ボス"
            ),
            None,
        )
        if groups and previous == groups[-1][-1]:
            groups[-1].append(index)
        else:
            groups.append([index])
    for group in groups:
        previous = next(
            (
                candidate
                for candidate in range(group[0] - 1, -1, -1)
                if events[candidate].name and events[candidate].name != "ボス"
            ),
            None,
        )
        if previous is None:
            previous = next(
                (
                    candidate
                    for candidate in range(group[0] - 1, -1, -1)
                    if re.fullmatch(r"\s*\[[54321-]{5}\](?:🅰️(?:ON|OFF))?\s*", lines[candidate])
                ),
                None,
            )
        if previous is not None:
            lines[previous] = add_auto_state(lines[previous], "ON", events[previous].name)
        lines[group[-1]] = add_auto_state(lines[group[-1]], "OFF", events[group[-1]].name)
    return "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")


def compact_forward_set_operations(text: str) -> str:
    """正順で包含関係にある生成SETを、UB条件を保って集約する。

    逆順解析で得たマスク列を、正順に見直す。後のマスクが前のマスクを
    包含し、追加されるキャラがその間に手動・矢印・オート発動しない場合、
    後のマスクを前へ移して中間操作を省略できる。原本SETは呼び出し側で
    除外するため、投稿者指定のマスクは変更しない。
    """
    lines = text.splitlines()
    character_names = character_names_from_formation(text)
    events = [parse_event(line_no, line, character_names) for line_no, line in enumerate(lines, 1)]

    def mask_indexes() -> list[int]:
        return [
            index
            for index, line in enumerate(lines)
            if (
                MASK_RE.search(line)
                and not line.lstrip().startswith("[(")
                and "🅰️" not in line
            )
        ]

    def event_number(event, number: str) -> bool:
        return character_names.get(event.name) == number

    changed = True
    while changed:
        changed = False
        indexes = mask_indexes()
        for left, right in zip(indexes, indexes[1:]):
            left_match = MASK_RE.search(lines[left])
            right_match = MASK_RE.search(lines[right])
            if not left_match or not right_match:
                continue
            left_state = numbers_from_mask(left_match.group(1))
            right_state = numbers_from_mask(right_match.group(1))
            if not left_state <= right_state:
                continue
            added = right_state - left_state
            if not added:
                continue

            safe = True
            for index in range(left + 1, right + 1):
                event = events[index]
                for number in added:
                    if not event_number(event, number):
                        continue
                    # 追加対象の最初の発動が通常SETなら、前倒ししても
                    # そのUB条件を満たす。手動・矢印・オートは個別条件を
                    # 持つため、まとめず元の境界を残す。
                    if (
                        event.manual
                        or event.arrow
                        or auto_note_in_line(lines[index])
                        or index != right
                    ):
                        safe = False
                        break
                if not safe:
                    break
            if not safe:
                continue

            # 後の絶対マスクを前の位置へ移し、後のマスクだけを除去する。
            lines[left] = MASK_RE.sub(right_match.group(0), lines[left], count=1)
            if lines[right].strip().startswith("[") and MASK_RE.fullmatch(lines[right].strip()):
                lines.pop(right)
                events.pop(right)
            else:
                lines[right] = MASK_RE.sub("", lines[right], count=1)
                events[right] = parse_event(right + 1, lines[right], character_names)
            changed = True
            break
    return "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")


def ensure_arrow_successor_masks(text: str) -> str:
    """矢印先の発動前後に必要なSET番号を補う。"""
    lines = text.splitlines()
    character_names = character_names_from_formation(text)
    events = [parse_event(line_no, line, character_names) for line_no, line in enumerate(lines, 1)]
    for index, event in enumerate(events):
        if not event.arrow or event.name not in character_names:
            continue
        current_number = character_names.get(event.name)
        if event.manual or current_number is None:
            continue
        previous_mask = next(
            (
                candidate
                for candidate in range(index - 1, -1, -1)
                if MASK_RE.search(lines[candidate])
                and not lines[candidate].lstrip().startswith("[(")
            ),
            None,
        )
        if previous_mask is not None:
            previous_match = MASK_RE.search(lines[previous_mask])
            if previous_match and current_number not in numbers_from_mask(previous_match.group(1)):
                lines[previous_mask] = MASK_RE.sub(
                    mask_for(numbers_from_mask(previous_match.group(1)) | {current_number}),
                    lines[previous_mask],
                    count=1,
                )
        next_arrow = next(
            (
                candidate
                for candidate in events[index + 1 :]
                if candidate.name is not None
            ),
            None,
        )
        if next_arrow is None or not next_arrow.arrow:
            continue
        number = character_names.get(next_arrow.name)
        match = MASK_RE.search(lines[index])
        if number is None or match is None:
            continue
        state = numbers_from_mask(match.group(1))
        if number in state:
            continue
        lines[index] = MASK_RE.sub(mask_for(state | {number}), lines[index], count=1)
    return "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")


def apply_explicit_set_timing(text: str) -> str:
    """``#...SET``の注記を、直前のボス行のSETタイミングへ反映する。"""
    lines = text.splitlines()
    character_names = character_names_from_formation(text)
    events = [parse_event(line_no, line, character_names) for line_no, line in enumerate(lines, 1)]
    for cue_index, event in enumerate(events):
        if event.name not in character_names or not re.search(r"#.*SET", lines[cue_index], re.IGNORECASE):
            continue
        number = character_names[event.name]
        boss_index = next(
            (
                index
                for index in range(cue_index - 1, -1, -1)
                if "ボス" in lines[index] and TIME_TOKEN_RE.search(lines[index])
            ),
            None,
        )
        if boss_index is None:
            continue
        first_later_mask = next(
            (
                index
                for index in range(boss_index + 1, len(lines))
                if MASK_RE.search(lines[index])
                and not lines[index].lstrip().startswith("[(")
            ),
            None,
        )
        if first_later_mask is None:
            continue
        later_match = MASK_RE.search(lines[first_later_mask])
        if later_match is None:
            continue
        target_state = numbers_from_mask(later_match.group(1)) | {number}
        boss_mask = mask_for(target_state)
        if MASK_RE.search(lines[boss_index]):
            lines[boss_index] = MASK_RE.sub(boss_mask, lines[boss_index], count=1)
        else:
            lines[boss_index] = lines[boss_index].rstrip() + "　" + boss_mask

        # SET指示より前の発動へ対象番号を先行投入しない。
        for index in range(boss_index):
            match = MASK_RE.search(lines[index])
            if match and not lines[index].lstrip().startswith("[("):
                state = numbers_from_mask(match.group(1))
                state.discard(number)
                lines[index] = MASK_RE.sub(mask_for(state), lines[index], count=1)

        # ボス行で確定した同一状態の後続SETは重複なので削除する。
        for index in range(boss_index + 1, len(lines)):
            match = MASK_RE.search(lines[index])
            if not match or lines[index].lstrip().startswith("[("):
                continue
            if match.group(1) == boss_mask[1:-1]:
                if MASK_RE.fullmatch(lines[index].strip()):
                    lines[index] = ""
                else:
                    lines[index] = MASK_RE.sub("", lines[index], count=1).rstrip()
    return "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")


def ensure_arrow_targets_are_set(text: str) -> str:
    """最終出力でも、SET発動する矢印先を発動前状態へ含める。"""
    lines = text.splitlines()
    names = character_names_from_formation(text)
    events = [parse_event(line_no, line, names) for line_no, line in enumerate(lines, 1)]
    for index, event in enumerate(events):
        if not event.arrow or event.manual or event.name not in names:
            continue
        number = names[event.name]
        target_index = index if MASK_RE.search(lines[index]) else next(
            (
                candidate
                for candidate in range(index - 1, -1, -1)
                if MASK_RE.search(lines[candidate])
                and not lines[candidate].lstrip().startswith("[(")
            ),
            None,
        )
        if target_index is None:
            continue
        match = MASK_RE.search(lines[target_index])
        if match and number not in numbers_from_mask(match.group(1)):
            lines[target_index] = MASK_RE.sub(
                mask_for(numbers_from_mask(match.group(1)) | {number}),
                lines[target_index],
                count=1,
            )
    return "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")


def refine_character_set_operations(
    text: str,
    initial: str = "-----",
    report: list[str] | None = None,
    ignore_original_set: bool = False,
) -> str:
    lines = text.splitlines()
    # SET付き原本は投稿者の指定を学習済みの正解として扱う。
    # 再計算すると同じマスクの重複や、手動UB直後の意図しない変更が
    # 混入するため、再計算は明示的な --ignore-original-set の場合だけ行う。
    if not ignore_original_set and any(MASK_RE.search(line) for line in lines):
        return ensure_initial_operation(text, initial)
    character_names = character_names_from_formation(text)
    if not character_names:
        # 番号が確定できない場合はSETを推測せず、オートだけ反映する。
        return add_auto_operations(text)
    events = [parse_event(line_no, line, character_names) for line_no, line in enumerate(lines, 1)]
    character_numbers = dict(character_names)
    for line in lines:
        for match in re.finditer(r"\(([54321])\)([^|)\]]+)", line):
            character_numbers[match.group(2).strip()] = match.group(1)
    effective_initial = initial
    header_index = next(
        (index for index, line in enumerate(lines) if line.startswith("[") and "|" in line),
        -1,
    )
    first_event_index = next(
        (index for index, event in enumerate(events) if event.name),
        len(lines),
    )
    explicit_start = False
    start_mask_index: int | None = None

    # 編成表がないTLでは、先頭の数値SET行を開始状態として扱う。
    # 「1:30 バトル開始 [54---]」のように時刻付きの場合も、同じ行の
    # マスクを初期状態として使用し、独立した[-----]行を挿入しない。
    for relative_index, line in enumerate(lines[: first_event_index]):
        match = MASK_RE.search(line)
        if match and (line.lstrip().startswith("[") or "バトル開始" in line):
            effective_initial = match.group(1)
            explicit_start = True
            start_mask_index = relative_index
            break

    if not explicit_start:
        first_line_with_mask = next(
            (
                (index, MASK_RE.search(line))
                for index, line in enumerate(lines)
                if line.strip() and MASK_RE.search(line)
            ),
            None,
        )
        if first_line_with_mask is not None:
            index, match = first_line_with_mask
            line = lines[index]
            if index == next(
                (i for i, candidate in enumerate(lines) if candidate.strip()),
                index,
            ) or "バトル開始" in line:
                effective_initial = match.group(1)
                explicit_start = True
                start_mask_index = index

    if header_index >= 0:
        for relative_index, line in enumerate(
            lines[header_index + 1 : first_event_index], header_index + 1
        ):
            match = re.fullmatch(r"\[([54321-]{5})\](?:🅰️(?:ON|OFF))?", line.strip())
            if match:
                effective_initial = match.group(1)
                explicit_start = True
                start_mask_index = relative_index
                break

    # 原文に開始SETがなく、最初の発動が⭐️なし・矢印なしなら、
    # そのキャラだけを開始SETへ追加する。以後の特殊判断は自動推測しない。
    if not explicit_start:
        first_event = events[first_event_index] if first_event_index < len(events) else None
        if first_event and first_event.name and not first_event.manual and not first_event.arrow:
            first_number = character_numbers.get(first_event.name)
            if first_number is not None:
                effective_initial = mask_for({first_number})[1:-1]

    def event_seconds(event) -> int | None:
        match = TIME_TOKEN_RE.search(event.prefix)
        if not match:
            return None
        return int(match.group(1)) * 60 + int(match.group(2))

    # Phase 1: キャラ別制約を先に走査する。
    # 発動順の意味は本文の上から下で保つが、各キャラの手動・通常・矢印
    # の予定を先に分離しておくことで、SET追加や解除の判断を混在させない。
    character_constraints: dict[str, dict[str, list[int]]] = {
        number: {"manual": [], "auto": [], "arrow": []}
        for number in character_numbers.values()
    }
    for index, event in enumerate(events):
        if event.name not in character_numbers:
            continue
        number = character_numbers[event.name]
        if event.manual:
            character_constraints[number]["manual"].append(index)
        elif event.arrow:
            character_constraints[number]["arrow"].append(index)
        else:
            character_constraints[number]["auto"].append(index)

    # キャラごとの次回判断を作る。ここではまだ全体のSET状態を変更せず、
    # 各キャラについて「次が手動・矢印・通常のどれか」を確定する。
    character_decisions: dict[str, dict[int, dict[str, object]]] = {
        number: {}
        for number in character_numbers.values()
    }
    for number in "54321":
        indexes = sorted(
            character_constraints[number]["manual"]
            + character_constraints[number]["auto"]
            + character_constraints[number]["arrow"]
        )
        # 次回発動を確定するため、キャラごとの発動一覧は下から上へ走査する。
        # これにより、手動UB後に同じキャラが矢印へ進む場合などを先に把握できる。
        next_index = None
        next_kind = None
        future_arrow = False
        future_normal_timed = False
        for index in reversed(indexes):
            event = events[index]
            kind = "manual" if event.manual else "arrow" if event.arrow else "normal"
            character_decisions[number][index] = {
                "kind": kind,
                "next_index": next_index,
                "next_kind": next_kind,
                # 直後の判断に加え、後続予定も保持する。矢印連鎖の途中で
                # 通常発動が挟まる場合など、解除を早めないために使う。
                "future_arrow": future_arrow,
                "future_normal_timed": future_normal_timed,
            }
            next_index = index
            next_kind = kind
            if event.arrow:
                future_arrow = True
            elif not event.manual and event_seconds(event) is not None:
                future_normal_timed = True

    # キャラ別の制約から、手動UBの解除位置を先に確定する。
    # 時刻差ではなく、発動順とキャラの一致を優先して解除位置を決める。
    manual_release_indexes: dict[int, int | None] = {}
    for number in character_numbers.values():
        for manual_index in character_constraints[number]["manual"]:
            manual_event = events[manual_index]
            candidates = [
                candidate_index
                for candidate_index in range(manual_index)
                if events[candidate_index].name
            ]
            same_character_candidates = [
                candidate_index
                for candidate_index in candidates
                if events[candidate_index].name == manual_event.name
            ]
            # 解除操作は、可能なら対象キャラ自身の直前発動へ便乗する。
            # 同じキャラの安全な発動がない場合だけ、直近の別キャラ行を使う。
            manual_release_indexes[manual_index] = (
                same_character_candidates[-1]
                if same_character_candidates
                else candidates[-1]
                if candidates
                else None
            )

    # 手動UB対象は、時刻差ではなく、発動順上の最後の適切な行で解除する。
    early_exclusions_by_start: dict[int, set[str]] = {}
    early_exclusions_by_end: dict[int, set[str]] = {}
    for manual_index, release_index in manual_release_indexes.items():
        number = character_numbers[events[manual_index].name]
        if release_index is not None:
            start_index = release_index
            early_exclusions_by_start.setdefault(start_index, set()).add(number)
            early_exclusions_by_end.setdefault(manual_index, set()).add(number)
        else:
            effective_initial = effective_initial.replace(number, "-")

    state = numbers_from_mask(effective_initial)
    active_early_exclusions: set[str] = set()
    deferred_arrow_releases: set[str] = set()
    rendered = list(lines)
    masks: dict[int, str | None] = {}
    standalone_after: dict[int, str] = {}
    operation_kinds: dict[int, str] = {}
    operation_reasons: dict[int, list[str]] = {}

    def assign_mask(index: int, mask: str) -> None:
        previous = previous_event(index)
        if previous is not None and masks.get(previous) == mask:
            return
        if events[index].manual:
            standalone_after[index] = mask
            masks[index] = None
        else:
            masks[index] = mask

    def classify_operation(before: set[str], after: set[str]) -> str:
        """SET差分を、追加・解除・全置換の操作種別へ分類する。"""
        added = after - before
        removed = before - after
        if not added and not removed:
            return "KEEP"
        if after == set("54321"):
            return "SET_ALL"
        if not after:
            return "CLEAR_ALL"
        if added and not removed:
            return "ADD"
        if removed and not added:
            return "REMOVE"
        return "REPLACE"

    def previous_event(index: int) -> int | None:
        for candidate in range(index - 1, -1, -1):
            if events[candidate].name:
                return candidate
        return None

    def arrow_chain(index: int) -> list[int]:
        result: list[int] = []
        candidate = index + 1
        while candidate < len(events) and events[candidate].arrow:
            if events[candidate].name in character_numbers:
                result.append(candidate)
            candidate += 1
        return result

    def arrow_chain_after_stop(index: int) -> list[int]:
        """止めぽ・空行を挟んで始まる矢印連鎖を見つける。"""
        saw_stop = False
        candidate = index + 1
        while candidate < len(events):
            line = lines[candidate]
            if "止めぽ" in line or line.lstrip().startswith("+---"):
                saw_stop = True
                candidate += 1
                continue
            if events[candidate].name in character_numbers:
                return []
            if saw_stop and events[candidate].arrow and events[candidate].name in character_numbers:
                return [candidate] + arrow_chain(candidate)
            candidate += 1
        return []

    def next_character(index: int):
        for candidate in events[index + 1 :]:
            if candidate.name in character_numbers:
                return candidate
        return None

    def next_operation(index: int):
        for candidate in events[index + 1 :]:
            if candidate.name in character_numbers:
                return candidate
        return None

    def arrow_release_anchor(index: int, fallback: int | None) -> int | None:
        """矢印連鎖の先行SET解除を置く最初の安全な発動行を返す。"""
        fixed_indexes = [
            candidate_index
            for candidate_index in range(index)
            if events[candidate_index].mask is not None
            and not ignore_original_set
        ]
        if not fixed_indexes:
            if fallback is not None:
                preceding = previous_event(fallback)
                if preceding is not None and events[preceding].arrow:
                    return preceding
            return fallback
        fixed_index = fixed_indexes[-1]
        for candidate_index in range(fixed_index + 1, index):
            if events[candidate_index].name:
                return candidate_index
        return fallback

    # Phase 2: キャラ別制約を統合し、本文の上から下へSET状態を確定する。
    # 実際の操作順に合わせて、ADDは上から連続統合し、REMOVEは
    # Phase 1で下から確認した解除条件を使って安全な位置へ配置する。
    for index, (line, event) in enumerate(zip(lines, events)):
        if not event.name or event.name not in character_numbers:
            rendered[index] = line.rstrip("\r")
            if event.mask is not None and not ignore_original_set and index != start_mask_index:
                state = numbers_from_mask(event.mask)
            elif event.mask is not None and ignore_original_set and index != start_mask_index:
                rendered[index] = MASK_RE.sub("", rendered[index]).strip()
            continue

        # 同時刻の⭐️矢印は表示上の矢印を残すが、SET計算では手動UB。
        # 矢印として扱うと、手動対象をSET内へ戻すことがある。
        if event.manual and event.arrow:
            event = replace(event, arrow=False)

        active_early_exclusions.update(early_exclusions_by_start.get(index, set()))
        chain = arrow_chain(index)
        delayed_chain = [] if chain else arrow_chain_after_stop(index)
        arrow_chain_continues = (
            event.arrow
            and index + 1 < len(events)
            and events[index + 1].arrow
        )
        number = character_numbers[event.name]
        has_future_character = any(
            candidate.name in character_numbers for candidate in events[index + 1 :]
        )

        # stateは、現在行の発動直前の状態として扱う。
        before = set(state)
        if event.manual:
            # ⭐️手動UB対象は発動直前までにSET外へする。
            state.discard(number)
        else:
            state.add(number)

        if chain or delayed_chain:
            # 後続の矢印先は、矢印元の発動直前までSET外にする。
            # 止めぽや空行などのメモを挟む場合も、直前の発動行を更新する。
            future_numbers = {
                character_numbers[events[arrow_index].name]
                for arrow_index in (chain or delayed_chain)
                if events[arrow_index].name
            }
            state.difference_update(future_numbers)
            if not event.manual:
                state.add(number)

        # 直前行のSET状態を変更すれば、現在行の発動前に反映できる。
        previous = previous_event(index)
        if (
            previous is not None
            and (events[previous].mask is None or ignore_original_set)
            and state != before
        ):
            assignment_index = previous
            if chain or delayed_chain:
                future_numbers = {
                    character_numbers[events[arrow_index].name]
                    for arrow_index in (chain or delayed_chain)
                    if events[arrow_index].name
                }
                anchor = arrow_release_anchor(index, previous)
                if future_numbers and anchor is not None and (
                    events[anchor].mask is None or ignore_original_set
                ):
                    # 矢印先の解除だけを、連鎖直前の安全な行へ前倒しする。
                    anchor_state = set(before)
                    anchor_state.difference_update(future_numbers)
                    assign_mask(anchor, mask_for(anchor_state))
                    assignment_index = None
            if assignment_index is not None:
                assign_mask(assignment_index, mask_for(state))

        before_action = set(state)
        if not event.arrow and chain:
            # 元キャラ発動直後に、最初の矢印先だけを追加する。
            state.add(character_numbers[events[chain[0]].name])
            for arrow_index in chain[1:]:
                state.discard(character_numbers[events[arrow_index].name])
        elif event.arrow and chain:
            # 矢印先発動直後に、次の矢印先だけを追加する。
            decision = character_decisions[number][index]
            future_same_arrow = decision["future_arrow"]
            # 同じキャラに次の発動予定がない場合は、発動済みでもSET継続する。
            # 次の発動がある場合だけ、手動・矢印の誤発防止を優先して解除する。
            if (
                arrow_chain_continues
                or decision["next_index"] is None
                or decision["next_kind"] == "normal"
            ):
                pass
            elif future_same_arrow and next_operation(index) is not None and next_operation(index).star:
                deferred_arrow_releases.add(number)
            else:
                state.discard(number)
            for arrow_index in chain[1:]:
                state.discard(character_numbers[events[arrow_index].name])
            state.add(character_numbers[events[chain[0]].name])

        if chain or delayed_chain:
            # 危険な矢印連鎖では、後続の矢印先を先行SETしない。
            # ただし、将来の確定した通常発動キャラは既存状態として維持する。
            next_arrow = (chain or delayed_chain)[0]
            state.add(character_numbers[events[next_arrow].name])
            # 時刻付きの通常発動が後続するキャラは、発動予定が確定しているため
            # 発動後もSETを継続する。矢印先の先行SETとは区別する。
            if (
                not event.arrow
                and not event.manual
                and character_decisions[number][index]["future_normal_timed"]
            ):
                state.add(number)
        elif event.arrow and has_future_character:
            # 矢印先の発動後は、その矢印先だけを解除し、
            # 既存の予定SETを維持しながら次の通常キャラを追加する。
            decision = character_decisions[number][index]
            future_same_arrow = decision["future_arrow"]
            next_op = next_operation(index)
            if (
                decision["next_index"] is None
                or decision["next_kind"] == "normal"
            ):
                pass
            elif future_same_arrow and next_op is not None and next_op.star:
                deferred_arrow_releases.add(number)
            else:
                state.discard(number)
            next_event = next_character(index)
            if next_event is not None and not next_event.manual:
                state.add(character_numbers[next_event.name])

        # 明確な解除理由がないキャラは、次の予定がなくてもSETを継続する。
        # 手動対象は上で解除し、未来の矢印先は連鎖開始前に解除済み。
        # 矢印連鎖の途中では解除を保留し、最後の矢印行へまとめる。
        # 連鎖中に毎行解除すると、同じ連鎖のSET操作が細切れになる。
        if not arrow_chain_continues:
            state.difference_update(active_early_exclusions)
        if event.manual:
            state.difference_update(deferred_arrow_releases)
            deferred_arrow_releases.clear()
        active_early_exclusions.difference_update(
            early_exclusions_by_end.get(index, set())
        )
        if event.manual:
            # 手動UB後、次の操作が通常の⭐️なし発動なら、
            # 次の同キャラ発動へ向けて対象を直後から再SETする。
            # 全体の次行ではなく、キャラ別の次回種別を使う。
            if character_decisions[number][index]["next_kind"] == "normal":
                state.add(number)

        # 次の操作が通常の⭐️なし発動なら、その対象の準備を現在の操作へ便乗する。
        # 次の操作が⭐️または矢印の場合は、誤発防止のため個別に扱う。
        next_event = next_operation(index)
        if next_event is not None and not next_event.manual and not next_event.arrow:
            state.add(character_numbers[next_event.name])

        changed_mask = mask_for(state) if state != before_action else None
        operation_kinds[index] = classify_operation(before_action, state)
        reason_parts: list[str] = []
        if event.manual:
            reason_parts.append("手動UB")
        if chain or delayed_chain:
            reason_parts.append("矢印連鎖")
        next_event = next_operation(index)
        if next_event is not None and not next_event.manual and not next_event.arrow:
            reason_parts.append(f"次の通常発動{next_event.name}へ便乗")
        if active_early_exclusions:
            reason_parts.append("手動対象の誤発防止")
        if reason_parts:
            operation_reasons[index] = reason_parts
        if event.mask is not None and not ignore_original_set:
            # 原本にSETがある行は、原本指定を固定し、自動更新しない。
            state = numbers_from_mask(event.mask)
            masks[index] = mask_for(state)
            operation_kinds[index] = "REPLACE"
            continue
        if event.manual and changed_mask is not None:
            # 手動行は情報量が多いため、SET操作を次行先頭の独立行へ分離する。
            standalone_after[index] = changed_mask
            masks[index] = None
        else:
            masks[index] = changed_mask

    # 同時刻の⭐️矢印は、直前の矢印行で対象キャラをSET外にしておく。
    # 表示上は⭐️を残すが、手動UBの誤発防止を優先する。
    for index, event in enumerate(events):
        if not event.manual or not event.arrow:
            continue
        previous = previous_event(index)
        number = character_numbers.get(event.name)
        if previous is not None and number and masks.get(previous) is not None:
            previous_state = numbers_from_mask(masks[previous])
            previous_state.discard(number)
            masks[previous] = mask_for(previous_state)

    # Phase 3: 確定した状態を出力へ反映する。
    # 変更のない行は省略し、絶対マスクとして表示する。
    for index, event in enumerate(events):
        if event.name in character_numbers:
            rendered[index] = render_event(event, masks.get(index))

    output: list[str] = []
    for index, line in enumerate(rendered):
        output.append(line)
        if index in standalone_after:
            output.append(standalone_after[index])

    # 後半の自動解除（🅰️OFF）が存在しても、先頭の初期SETとは別物。
    # 開始SETが原文にない場合は必ず先頭へ追加する。
    if not explicit_start:
        if output and output[0].startswith("[(") and "|" in output[0]:
            output = output[:1] + ["", f"[{effective_initial}]🅰️OFF"] + output[1:]
        else:
            output = [f"[{effective_initial}]🅰️OFF", ""] + output

    if report is not None:
        for index, kind in operation_kinds.items():
            if kind == "KEEP":
                continue
            mask = masks.get(index) or standalone_after.get(index, "")
            reasons = ", ".join(operation_reasons.get(index, [])) or "状態差分"
            report.append(
                f"行{index + 1}: {kind} {mask} / {reasons}"
            )

    return "\n".join(output) + ("\n" if text.endswith(("\n", "\r")) else "")


def add_operations(
    text: str,
    initial: str = "-----",
    report: list[str] | None = None,
    ignore_original_set: bool = False,
) -> str:
    """キャラ別SET精査後に、オートだけを反映する処理パイプライン。"""
    source_has_set = any(MASK_RE.search(line) for line in text.splitlines())
    character_refined = refine_character_set_operations(
        text,
        initial=initial,
        report=report,
        ignore_original_set=ignore_original_set,
    )
    if not source_has_set and not ignore_original_set:
        character_refined = ensure_arrow_successor_masks(character_refined)
        character_refined = compact_forward_set_operations(character_refined)
        character_refined = apply_explicit_set_timing(character_refined)
        character_refined = ensure_arrow_targets_are_set(character_refined)
    return add_auto_operations(character_refined)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--initial", default="-----", help="開始SETマスク。既定値は[-----]")
    parser.add_argument("--report", type=Path, help="SET変更理由の確認レポート出力先")
    parser.add_argument(
        "--ignore-original-set",
        action="store_true",
        help="開始SET以外の原本SET操作を無視して再計算する",
    )
    args = parser.parse_args()
    if len(args.initial) != 5 or any(c not in "54321-" for c in args.initial):
        parser.error("--initial は5文字の5/4/3/2/1/-で指定してください")
    report: list[str] = []
    args.output.write_text(
        add_operations(
            args.input.read_text(),
            args.initial,
            report,
            ignore_original_set=args.ignore_original_set,
        ),
        encoding="utf-8",
    )
    if args.report is not None:
        args.report.write_text("\n".join(report) + ("\n" if report else ""), encoding="utf-8")


if __name__ == "__main__":
    main()
