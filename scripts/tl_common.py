"""共通のTL解析・表記処理。"""

from __future__ import annotations

import re
from dataclasses import dataclass

CHARACTERS = ("アオイ", "ネラ", "ツムギ", "ペコ", "シェフィ")
CHAR_NUMBERS = {name: number for name, number in zip(CHARACTERS, "54321")}
# 長い正式名を使う編成では、ここへ4文字の表示用略称を登録する。
DISPLAY_NAMES = {name: name for name in CHARACTERS}
TIME_RE = re.compile(r"\d+:\d{2}(?:-\d{2})?")
TIME_TOKEN_RE = re.compile(r"(?<!\d)(\d+):(\d{1,2})(?:-(\d{1,2}))?")
BARE_TIME_RE = re.compile(r"\d{1,2}(?=\s|　|$)")
BARE_TIME_TOKEN_RE = re.compile(r"^([^\d]*)(\d{1,2})(?=\s|　|$)")
MASK_RE = re.compile(r"\[([0-9-]{5})\]")
FORMATION_ON_CHARS = "OO️o○◯〇⭕0０"
FORMATION_OFF_CHARS = "Xx×✖✕☓_ー－—-─＿"
FORMATION_RE = re.compile(
    rf"\[?[{re.escape(FORMATION_ON_CHARS + FORMATION_OFF_CHARS)}]{{5}}\]?"
)


def normalize_input_line(line: str) -> str:
    """コメントを保護したまま、入力行の構造部分だけを正規化する。"""
    source = str(line).rstrip("\r")
    head, separator, comment = source.partition("//")
    # 丸・ばつの絵文字は先に1文字へ寄せてから5文字マスクを判定する。
    head = head.replace("⭕️", "O").replace("⭕", "O")
    head = head.replace("❌", "X")
    formation_chars = re.escape(FORMATION_ON_CHARS + FORMATION_OFF_CHARS)
    head = re.sub(rf"\(([{formation_chars}]{{5}})\)", r"[\1]", head)
    has_formation = FORMATION_RE.search(head) is not None
    has_auto = re.search(
        r"(?:オート|AUTO)[ \t　]*(?:ON|OFF|オン|オフ)|🅰️(?:ON|OFF)",
        head,
        re.IGNORECASE,
    ) is not None
    if not has_formation and not has_auto and not re.match(
        r"^[ \t　]*(?:⭐️|⭐︎|⭐|★|☆)?[ \t　]*(?:\d{1,2}:\d{1,2}|\d{1,2}(?=[ \t　])|->|>|→|➡︎|⇨|⇒)",
        source,
    ):
        # 時刻のない発動行も、数値SETマスクがあれば構造行として扱う。
        if MASK_RE.search(head) is None:
            return source
    head = head.replace("【", "[").replace("】", "]")
    head = head.replace("〇️", "O").replace("〇", "O")
    formation = FORMATION_RE.search(head)
    if formation:
        pattern = formation.group(0).strip("[]")
        converted = "".join(
            char if char in FORMATION_ON_CHARS else "-"
            for char in pattern
        )
        converted = "".join(
            str(5 - index) if char != "-" else "-"
            for index, char in enumerate(converted)
        )
        head = head[: formation.start()] + f"[{converted}]" + head[formation.end() :]
    head = re.sub(
        r'''["「『]?(?:オート|AUTO)[ \t　]*(ON|OFF|オン|オフ)["」』]?''',
        lambda match: "🅰️ON" if match.group(1).upper() in {"ON", "オン"} else "🅰️OFF",
        head,
        flags=re.IGNORECASE,
    )
    head = re.sub(r"(\[[54321-]{5}\])[ \t　]+(🅰️(?:ON|OFF))", r"\1\2", head)
    head = re.sub(r"[\"“”「」『』]\s*(🅰️(?:ON|OFF))\s*[\"“”「」『』]", r"\1", head)
    head = re.sub(r"(\[[54321-]{5}\])[ \t　]+(🅰️(?:ON|OFF))", r"\1\2", head)
    head = re.sub(r"^[ \t　]*(?:⭐️|⭐︎|⭐|★|☆)", "⭐️", head)
    head = re.sub(r"^[ \t　]*(?:->|>|➡︎|⇨|⇒)", "　　→", head)
    head = re.sub(r"[ \t]+", "　", head)
    return head + (separator + comment if separator else "")


@dataclass
class Event:
    line_no: int
    raw: str
    prefix: str
    name: str | None
    star: bool
    arrow: bool
    mask: str | None


def mask_for(numbers: set[str]) -> str:
    """キャラ番号の集合を固定位置5・4・3・2・1のマスクへ変換する。"""
    return "[" + "".join(number if number in numbers else "-" for number in "54321") + "]"


def numbers_from_mask(mask: str) -> set[str]:
    return {number for number, value in zip("54321", mask) if value == number}


def normalize_time_prefix(prefix: str) -> str:
    """時刻範囲を M:SS-SS 形式へ統一する。"""
    def replace(match: re.Match[str]) -> str:
        minute = str(int(match.group(1)))
        if minute not in {"0", "1"}:
            raise ValueError(f"分は0または1の一桁で指定してください: {match.group(0)}")
        second = match.group(2).zfill(2)
        end = match.group(3)
        return f"{minute}:{second}" + (f"-{end.zfill(2)}" if end is not None else "")

    normalized = re.sub(
        r"(\d{1,2}:\d{1,2})[ \t　]*[〜~～－ー―‐—–-][ \t　]*(\d{1,2})(?=\D|$)",
        r"\1-\2",
        prefix,
        count=1,
    )
    normalized = TIME_TOKEN_RE.sub(replace, normalized, count=1)
    if TIME_RE.search(normalized) is None:
        bare_match = BARE_TIME_TOKEN_RE.match(normalized)
        if bare_match:
            normalized = f"{bare_match.group(1)}0:{bare_match.group(2).zfill(2)}" + normalized[bare_match.end():]
    return normalized


def is_event_line(line: str) -> bool:
    stripped = line.lstrip("　 \t")
    stripped = re.sub(r"^(?:⭐️|⭐︎|⭐|🔺)+", "", stripped).lstrip("　 \t")
    if bool(TIME_RE.match(stripped) or BARE_TIME_RE.match(stripped)) or stripped.startswith("→"):
        return True
    # 時刻を省略した矢印先・発動行（例: 「ルルィ [54321]」）を認識する。
    return bool(MASK_RE.search(stripped) and not stripped.startswith("["))


def parse_event(line_no: int, line: str) -> Event:
    mask_match = MASK_RE.search(line)
    mask = mask_match.group(1) if mask_match else None
    if not is_event_line(line):
        return Event(line_no, line, "", None, False, False, mask)

    arrow = "→" in line and not bool(TIME_RE.match(line.lstrip("　 \t")))
    star = "⭐️" in line or "⭐︎" in line or "⭐" in line
    name = None
    prefix = line

    # 名前の直後は、区切り空白・SETマスク・行末のいずれかであることを要求する。
    for candidate in CHARACTERS:
        match = re.search(re.escape(candidate) + r"(?=　|\s|\[|$)", line)
        if match:
            name = candidate
            prefix = line[: match.start()]
            break

    if name is None and mask is not None:
        # CHARACTERSに未登録のキャラも書式整形だけは可能にする。
        # SETの意味付けは編成表でキャラ番号が確定した後に行う。
        body = line
        body = re.sub(r"^\s*(?:⭐️|⭐︎|⭐|★|☆)?\s*", "", body)
        body = re.sub(r"^(?:\d{1,2}:\d{1,2}|\d{1,2})\s*", "", body)
        body = re.sub(r"^→\s*", "", body)
        generic = re.match(r"([^\s　\[\]]+)(?=[\s　\[]|$)", body)
        if generic and len(generic.group(1)) <= 4:
            name = generic.group(1)
            prefix = line[: line.find(name)]

    if name is None:
        # 時刻付きの未登録キャラも、編成表から後で番号を解決できるよう抽出する。
        body = line
        body = re.sub(r"^\s*(?:⭐️|⭐︎|⭐|★|☆)?\s*", "", body)
        body = re.sub(r"^(?:\d{1,2}:\d{1,2}|\d{1,2})\s*", "", body)
        body = re.sub(r"^→\s*", "", body)
        generic = re.match(r"([^\s　\[\]]+)(?=[\s　\[]|$)", body)
        if generic and len(generic.group(1)) <= 4:
            name = generic.group(1)
            prefix = line[: line.find(name)]

    # 開始行・ボス行はキャラクター発動ではない。
    if name in {"開始時", "開始", "バトル開始", "ボス", "止めぽ"}:
        name = None

    return Event(line_no, line, prefix, name, star, arrow, mask)


def render_event(event: Event, mask: str | None = None) -> str:
    """イベント行のキャラ欄とSET表記を正規化する。"""
    if not event.name:
        return event.raw

    prefix = normalize_time_prefix(event.prefix.rstrip(" \t　"))
    if event.arrow:
        # 元の🔺などの注記は残し、矢印と名前の間は全角スペース1個にする。
        prefix += "　"
    else:
        prefix += "　"

    display_name = DISPLAY_NAMES.get(event.name, event.name)
    if len(display_name) > 4:
        raise ValueError(f"表示名が全角4文字を超えています。4文字略称を登録してください: {event.name}")
    name_field = display_name + "　" * (4 - len(display_name))
    rest = event.raw[event.raw.find(event.name) + len(event.name):]
    rest = MASK_RE.sub("", rest)
    rest = rest.strip(" \t　")

    parts: list[str] = []
    if mask is not None:
        parts.append(mask)
    if rest:
        parts.append(rest)
    suffix = "　".join(parts)
    if not suffix:
        return prefix + display_name
    return prefix + name_field + "　" + suffix
