"""Merge raw/game-exported battle timelines without guessing divergent routes.

The merger deliberately returns conflicts instead of silently choosing one event.
It is intended as a safe intermediate representation for a later formatter/UI.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

def _load_aliases() -> tuple[dict, dict]:
    candidates = [
        Path("/home/pyodide/character_aliases.json"),
        Path(__file__).resolve().parent.parent / "data" / "character_aliases.json",
    ]
    for path in candidates:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload.get("character_aliases", {}), payload.get("learned_name_aliases", {})
    from character_aliases import CHARACTER_ALIASES, LEARNED_NAME_ALIASES
    return CHARACTER_ALIASES, LEARNED_NAME_ALIASES


CHARACTER_ALIASES, LEARNED_NAME_ALIASES = _load_aliases()

def _load_character_master() -> dict:
    candidates = [
        Path("/home/pyodide/character_master.json"),
        Path(__file__).resolve().parent.parent / "data" / "character_master.json",
        Path(__file__).resolve().parent / "character_master.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    try:
        from character_master import CHARACTER_MASTER
    except ImportError:  # Local source checkout before the first sync.
        return {}
    return CHARACTER_MASTER


CHARACTER_MASTER = _load_character_master()


TIME_LINE_RE = re.compile(
    r"^\s*(?:[⭐️⭐︎⭐★☆🔺△]\s*)?(?P<time>\d{1,2}:\d{2})(?!\s*[-〜~～－ー―‐—–]\s*\d{1,2}(?::|\b))\s*(?P<body>.+?)\s*$"
)
ARROW_RE = re.compile(r"^(?:[⭐️⭐︎⭐★☆🔺△]\s*)?(?:→|➡︎|➡|⇨|⇒|->|>)\s*(?P<body>.+)$")


@dataclass(frozen=True)
class MergeEvent:
    source: str
    order: int
    seconds: int
    name: str
    raw_name: str
    manual: bool = False
    arrow: bool = False
    raw: str = ""


def _seconds(value: str) -> int:
    minutes, seconds = value.split(":", 1)
    return int(minutes) * 60 + int(seconds)


def _clean_name(value: str) -> str:
    return value.strip(" \t　[]()（）⭐️⭐︎⭐★☆🔺△#")


def character_resolver(formation: Iterable[str] = ()):
    """Return a resolver using exact names first, then unambiguous aliases.

    Formation names are authoritative: this permits game exports such as
    ``ネラ`` to resolve against the selected ``ネフィ＝ネラ（鬼面仏心）``.
    Ambiguous short names remain unresolved instead of being guessed.
    """
    names = [n.strip() for n in formation if n and n.strip()]
    canonical: dict[str, str] = {}
    for formal, short in CHARACTER_ALIASES.items():
        canonical[formal] = short
        canonical[short] = short
    aliases: dict[str, set[str]] = {}
    for formal in names:
        candidates = {formal, _clean_name(formal)}
        short = CHARACTER_ALIASES.get(formal) or LEARNED_NAME_ALIASES.get(formal)
        if short:
            candidates.add(short)
        # The game commonly omits the prefix before the equals sign.
        if "＝" in formal:
            suffix = formal.split("＝", 1)[-1]
            candidates.add(suffix)
            candidates.add(re.split(r"[（(]", suffix, 1)[0])
        candidates.add(re.split(r"[（(]", formal, 1)[0])
        for candidate in candidates:
            aliases.setdefault(candidate, set()).add(formal)
    for formal, short in CHARACTER_ALIASES.items():
        if formal and short:
            aliases.setdefault(formal, set()).update({formal, short})
            aliases.setdefault(short, set()).add(formal)
    # The formation remains authoritative, but the synced master supplies
    # nicknames such as ``すみれ`` -> ``ヴァイオレット``.
    for unit in CHARACTER_MASTER.values():
        formal = str(unit.get("formal_name", ""))
        for candidate in unit.get("aliases", []):
            if candidate:
                aliases.setdefault(str(candidate), set()).add(formal)
        if formal:
            aliases.setdefault(formal, set()).add(formal)

    def resolve(raw: str) -> str | None:
        value = _clean_name(raw)
        if value in canonical:
            return canonical[value]
        if value in names:
            return value
        for formal, short in CHARACTER_ALIASES.items():
            if value == formal and short in names:
                return short
            if value == short and formal in names:
                return formal
        matches = aliases.get(value, set())
        return next(iter(matches)) if len(matches) == 1 else None

    return resolve


def parse_events(text: str, source: str, formation: Iterable[str] = ()) -> tuple[list[MergeEvent], list[str]]:
    """Parse timed and arrow lines, returning events and unresolved names."""
    # Browser/clipboard exports sometimes preserve HTML spacing entities.
    text = html.unescape(text).replace("\u00a0", " ")
    formation_names = [n.strip() for n in formation if n and n.strip()]
    resolve = character_resolver(formation_names)
    events: list[MergeEvent] = []
    unresolved: list[str] = []
    for order, raw in enumerate(text.splitlines()):
        match = TIME_LINE_RE.match(raw)
        arrow = False
        seconds = None
        body = ""
        if match:
            seconds, body = _seconds(match.group("time")), match.group("body")
        else:
            arrow_match = ARROW_RE.match(raw)
            if arrow_match and events:
                seconds, body, arrow = events[-1].seconds, arrow_match.group("body"), True
        if seconds is None:
            continue
        manual = bool(re.match(r"^[⭐️⭐︎⭐★☆]", raw))
        body = re.split(r"//|#", body, 1)[0].strip()
        raw_name = re.split(r"[　 \[\]【】(（'\"→]", body, 1)[0]
        # Prefer a full formation name before stripping variant parentheses.
        exact = next((n for n in sorted(formation_names, key=len, reverse=True)
                      if body == n or body.startswith(n + " ") or body.startswith(n + "　")), None)
        raw_name = exact or raw_name
        name = resolve(raw_name)
        if name is None:
            if raw_name and raw_name not in {"バトル開始", "開始", "開始時", "ボス", "敵"}:
                unresolved.append(raw_name)
            continue
        events.append(MergeEvent(source, order, seconds, name, raw_name, manual, arrow, raw))
    return events, sorted(set(unresolved))


def expand_arrow_times(text: str) -> str:
    """矢印先を元の時刻付き1行へ戻してからマージする。"""
    current_time: str | None = None
    expanded: list[str] = []
    for line in text.splitlines():
        timed = re.search(r"(?<!\d)(\d{1,2}:\d{2})(?!\d)", line)
        if timed:
            current_time = timed.group(1)
        arrow = re.match(r"^(\s*(?:[⭐️⭐︎⭐★☆🔺△]\s*)?)(?:→|➡︎|➡|⇨|⇒|->|>)\s*(.*)$", line)
        if arrow and current_time:
            expanded.append(f"{current_time}　{arrow.group(2)}")
        else:
            expanded.append(line)
    return "\n".join(expanded)


def merge_events(*event_groups: Iterable[MergeEvent]) -> dict[str, list[dict]]:
    """Classify equal events, source-only events, and same-slot conflicts."""
    buckets: dict[tuple[int, str], list[MergeEvent]] = {}
    for group in event_groups:
        for event in group:
            buckets.setdefault((event.seconds, event.name), []).append(event)
    common, only_a, only_b, conflicts = [], [], [], []
    common_keys: set[tuple[int, str]] = set()
    all_events = sorted((event for group in event_groups for event in group), key=lambda e: (-e.seconds, e.order))
    for event in all_events:
        key = (event.seconds, event.name)
        bucket = buckets[key]
        sources = {item.source for item in bucket}
        item = asdict(event)
        if len(sources) > 1:
            if key not in common_keys:
                common.append(item)
                common_keys.add(key)
        elif event.source == "a":
            only_a.append(item)
        elif event.source == "b":
            only_b.append(item)
    # Different characters at the same timestamp are not duplicates.
    by_slot: dict[int, set[str]] = {}
    for event in all_events:
        by_slot.setdefault(event.seconds, set()).add(event.name)
    for seconds, names in by_slot.items():
        if len(names) > 1:
            conflicts.append({"seconds": seconds, "names": sorted(names)})
    return {"common": common, "only_a": only_a, "only_b": only_b, "conflicts": conflicts}


def merge_texts(text_a: str, text_b: str, formation: Iterable[str] = ()) -> dict[str, object]:
    """Return one timeline containing the union of raw and formatted events.

    The formatted timeline wins for duplicate events so its annotations are kept.
    Events found only in the raw timeline are retained using their original lines.
    """
    text_a = expand_arrow_times(text_a)
    text_b = expand_arrow_times(text_b)
    events_a, unresolved_a = parse_events(text_a, "a", formation)
    events_b, unresolved_b = parse_events(text_b, "b", formation)
    formatted_lines = text_b.splitlines()

    def line_seconds(line: str) -> int | None:
        if re.search(r"\d{1,2}:\d{1,2}\s*[-〜~～－ー―‐—–]\s*\d{1,2}:?\d{1,2}", line):
            return None
        match = re.search(r"(\d{1,2}):(\d{1,2})", line)
        return _seconds(f"{match.group(1)}:{match.group(2)}") if match else None

    formatted_events = sorted(events_b, key=lambda event: event.order)
    blocks: dict[int, list[str]] = {}
    for index, event in enumerate(formatted_events):
        end = formatted_events[index + 1].order if index + 1 < len(formatted_events) else len(formatted_lines)
        for line_index in range(event.order + 1, end):
            if line_seconds(formatted_lines[line_index]) is not None:
                end = line_index
                break
        blocks[event.order] = formatted_lines[event.order:end]
    formatted_by_key: dict[tuple[int, str], list[MergeEvent]] = {}
    for event in formatted_events:
        formatted_by_key.setdefault((event.seconds, event.name), []).append(event)

    # Battle events define the order; a matching formatted block supplies all
    # following arrows, notes, SET masks, and comments until the next event.
    merged_blocks: list[tuple[int, list[str]]] = []
    used_formatted: set[int] = set()

    def normalize_added_line(line: str) -> str:
        stripped = line.strip(" \t　")
        match = re.match(r"(\d{1,2}):(\d{1,2})(.*)$", stripped)
        if not match:
            return line
        minute, second, rest = int(match.group(1)), int(match.group(2)), match.group(3).strip(" \t　")
        return f"{minute}:{second:02d}　{rest}" if rest else f"{minute}:{second:02d}"

    for battle_event in events_a:
        candidates = formatted_by_key.get((battle_event.seconds, battle_event.name), [])
        formatted_event = next((item for item in candidates if item.order not in used_formatted), None)
        if formatted_event is not None:
            merged_blocks.append((battle_event.seconds, blocks[formatted_event.order]))
            used_formatted.add(formatted_event.order)
        else:
            merged_blocks.append((battle_event.seconds, [normalize_added_line(battle_event.raw)]))

    # Add formatted-only blocks at their timestamp without changing battle
    # event order.
    for event in formatted_events:
        if event.order in used_formatted:
            continue
        block = blocks[event.order]
        target = next((index for index, (seconds, _) in enumerate(merged_blocks) if seconds < event.seconds), len(merged_blocks))
        merged_blocks.insert(target, (event.seconds, block))

    merged_lines = []
    if formatted_events:
        merged_lines.extend(formatted_lines[:formatted_events[0].order])
    for _, block in merged_blocks:
        merged_lines.extend(block)
    for index, line in enumerate(formatted_lines):
        if index in {event.order for event in formatted_events} or not line.strip():
            continue
        if line not in merged_lines and line_seconds(line) is not None:
            seconds = line_seconds(line)
            target = next((position for position, merged_line in enumerate(merged_lines)
                           if (merged_seconds := line_seconds(merged_line)) is not None and merged_seconds < seconds), len(merged_lines))
            merged_lines.insert(target, line)
    merged_text = "\n".join(merged_lines).rstrip()
    return {"text": merged_text, "unresolved": sorted(set(unresolved_a + unresolved_b))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare two Princess Connect battle timelines")
    parser.add_argument("timeline_a")
    parser.add_argument("timeline_b")
    parser.add_argument("--formation", nargs=5, metavar="NAME", required=True,
                        help="five formation names in SET order 5,4,3,2,1")
    parser.add_argument("-o", "--output", help="write JSON to this file instead of stdout")
    args = parser.parse_args(argv)
    with open(args.timeline_a, encoding="utf-8") as handle:
        text_a = handle.read()
    with open(args.timeline_b, encoding="utf-8") as handle:
        text_b = handle.read()
    events_a, unresolved_a = parse_events(text_a, "a", args.formation)
    events_b, unresolved_b = parse_events(text_b, "b", args.formation)
    result = merge_events(events_a, events_b)
    result["unresolved"] = {"a": unresolved_a, "b": unresolved_b}
    result["summary"] = {
        "common": len(result["common"]),
        "only_a": len(result["only_a"]),
        "only_b": len(result["only_b"]),
        "conflicts": len(result["conflicts"]),
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
