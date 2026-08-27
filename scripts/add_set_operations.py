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
    CHAR_NUMBERS,
    TIME_TOKEN_RE,
    mask_for,
    numbers_from_mask,
    parse_event,
    character_names_from_formation,
    render_event,
    MASK_RE,
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


def add_operations(
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
    events = [parse_event(line_no, line, character_names) for line_no, line in enumerate(lines, 1)]
    character_numbers = dict(CHAR_NUMBERS)
    character_numbers.update(character_names)
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
        if first_event and first_event.name and not first_event.star and not first_event.arrow:
            effective_initial = mask_for({character_numbers[first_event.name]})[1:-1]

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
        if event.star:
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
            kind = "manual" if event.star else "arrow" if event.arrow else "normal"
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
            elif not event.star and event_seconds(event) is not None:
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
        if events[index].star:
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
        if event.star and event.arrow:
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
        if event.star:
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
            if not event.star:
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
                and not event.star
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
            if next_event is not None and not next_event.star:
                state.add(character_numbers[next_event.name])

        # 明確な解除理由がないキャラは、次の予定がなくてもSETを継続する。
        # 手動対象は上で解除し、未来の矢印先は連鎖開始前に解除済み。
        # 矢印連鎖の途中では解除を保留し、最後の矢印行へまとめる。
        # 連鎖中に毎行解除すると、同じ連鎖のSET操作が細切れになる。
        if not arrow_chain_continues:
            state.difference_update(active_early_exclusions)
        if event.star:
            state.difference_update(deferred_arrow_releases)
            deferred_arrow_releases.clear()
        active_early_exclusions.difference_update(
            early_exclusions_by_end.get(index, set())
        )
        if event.star:
            # 手動UB後、次の操作が通常の⭐️なし発動なら、
            # 次の同キャラ発動へ向けて対象を直後から再SETする。
            # 全体の次行ではなく、キャラ別の次回種別を使う。
            if character_decisions[number][index]["next_kind"] == "normal":
                state.add(number)

        # 次の操作が通常の⭐️なし発動なら、その対象の準備を現在の操作へ便乗する。
        # 次の操作が⭐️または矢印の場合は、誤発防止のため個別に扱う。
        next_event = next_operation(index)
        if next_event is not None and not next_event.star and not next_event.arrow:
            state.add(character_numbers[next_event.name])

        changed_mask = mask_for(state) if state != before_action else None
        operation_kinds[index] = classify_operation(before_action, state)
        reason_parts: list[str] = []
        if event.star:
            reason_parts.append("手動UB")
        if chain or delayed_chain:
            reason_parts.append("矢印連鎖")
        next_event = next_operation(index)
        if next_event is not None and not next_event.star and not next_event.arrow:
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
        if event.star and changed_mask is not None:
            # 手動行は情報量が多いため、SET操作を次行先頭の独立行へ分離する。
            standalone_after[index] = changed_mask
            masks[index] = None
        else:
            masks[index] = changed_mask

    # 同時刻の⭐️矢印は、直前の矢印行で対象キャラをSET外にしておく。
    # 表示上は⭐️を残すが、手動UBの誤発防止を優先する。
    for index, event in enumerate(events):
        if not event.star or not event.arrow:
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

    def add_auto_state(line: str, state: str) -> str:
        """UB条件メモの前後へオート状態だけを追加する。"""
        if f"🅰️{state}" in line:
            return line
        head, separator, comment = line.partition("//")
        auto_note = re.search(r'''["「『]オート["」』]''', head)
        if auto_note:
            head = (
                head[: auto_note.start()].rstrip(" \t　")
                + f"🅰️{state}　"
                + head[auto_note.start():]
            )
        else:
            trailing = re.search(r"[ \t　]*$", head).group(0)
            head = head[: len(head) - len(trailing)] + f"🅰️{state}" + trailing
        return head + (separator + comment if separator else "")

    # 引用符付き「オート」は操作表記へ変換せず、UB条件区間の前後へ
    # オート状態を付ける。区間内のメモ本文は原文のまま保持する。
    auto_indexes = [
        index
        for index, event in enumerate(events)
        if event.name and re.search(r'''["「『]オート["」』]''', lines[index])
    ]
    groups: list[list[int]] = []
    for index in auto_indexes:
        if groups and index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    for group in groups:
        previous = previous_event(group[0])
        if previous is not None:
            rendered[previous] = add_auto_state(rendered[previous], "ON")
        rendered[group[-1]] = add_auto_state(rendered[group[-1]], "OFF")

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
