"""共通のTL解析・表記処理。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from character_aliases import CHARACTER_ALIASES, LEARNED_NAME_ALIASES

CHARACTERS = ("アオイ", "ネラ", "ツムギ", "ペコ", "シェフィ")
CHAR_NUMBERS = {name: number for name, number in zip(CHARACTERS, "54321")}
# 長い正式名を使う編成では、ここへ4文字の表示用略称を登録する。
DISPLAY_NAMES = {name: name for name in CHARACTERS} | CHARACTER_ALIASES | LEARNED_NAME_ALIASES
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
FORMATION_ENTRY_RE = re.compile(r"\(([54321])\)([^|)\]]+)")


def normalize_input_line(line: str) -> str:
    """コメントを保護したまま、入力行の構造部分だけを正規化する。"""
    source = str(line).rstrip("\r")
    # // と '' は備考の開始位置。最初に現れた方以降を完全保持する。
    comment_positions = [pos for pos in (source.find("//"), source.find("''")) if pos >= 0]
    if comment_positions:
        comment_start = min(comment_positions)
        head, comment = source[:comment_start], source[comment_start:]
    else:
        head, comment = source, ""
    # 敵UB見出しは、枠記号を外して通常のボス行へ変換する。
    boss_header = re.match(
        r"^\\?===【\s*(\d{1,2}:\d{1,2})\s*(?:敵UB|ボスUB|敵|ボス)\s*】===$",
        head,
        flags=re.IGNORECASE,
    )
    if boss_header:
        head = f"{boss_header.group(1)}　ボス"
    # 見出し（例: ===【0:33 敵UB】===）はイベント行ではないため、
    # 早期returnの前にボス表記だけを統一する。
    head = re.sub(r"(?:敵|ボス)UB", "ボス", head, flags=re.IGNORECASE)
    head = re.sub(r"敵", "ボス", head)
    # 時刻の前後を装飾線で囲んだボス行も、装飾を外して通常行にする。
    decorated_boss = re.match(
        r"^[\\\-_=~ー]+(\d{1,2}:\d{1,2})\s*ボス[\\\-_=~ー]*(.*)$",
        head,
        flags=re.IGNORECASE,
    )
    if decorated_boss:
        head = f"{decorated_boss.group(1)}　ボス{decorated_boss.group(2)}"
    else:
        # ボス名が一覧にない場合でも、装飾線で囲まれた時刻＋ダメージ
        # 表記はボス行として扱う（例: バイオドーザー ---[4.06億]）。
        decorated_boss_record = re.match(
            r"^[\\\-_=~ー]+(\d{1,2}:\d{1,2})\s+.+?\s+[\\\-_=~ー]+\s*(\[[^\n\]]+\])\s*$",
            head,
            flags=re.IGNORECASE,
        )
        if decorated_boss_record:
            head = f"{decorated_boss_record.group(1)}　ボス　{decorated_boss_record.group(2)}"
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
        r"^[ \t　]*(?:⭐️|⭐︎|⭐|★|☆|△)?[ \t　]*(?:\d{1,2}:\d{1,2}|\d{1,2}(?=[ \t　])|->|>|→|➡︎|⇨|⇒)",
        source,
    ):
        # 時刻のない発動行も、数値SETマスクがあれば構造行として扱う。
        if MASK_RE.search(head) is None:
            return head + comment
    head = head.replace("【", "[").replace("】", "]")
    # ボス表記の揺れは、構造部に限って「ボス」へ統一する。コメント内
    # の文章は変更しない。
    head = re.sub(r"(?:敵|ボス)UB", "ボス", head, flags=re.IGNORECASE)
    head = re.sub(r"敵", "ボス", head)
    # 投稿で使われる省略表記を、SETマスクとして採用する。コメントは
    # 上で切り離しているため、備考中の同じ語は変更しない。
    head = re.sub(r"全解除", "[-----]", head)
    head = re.sub(r"全set", "[54321]", head, flags=re.IGNORECASE)
    # 実データでは全角括弧がキャラ名の注記にも使われるため、
    # 構造マスクの括弧だけを先に正規化し、注記本文は保持する。
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
    # キャラ間矢印より後ろは後続キャラ・備考の領域。オート表記を
    # 前のキャラへ誤付与しないよう、矢印前だけ正規化する。
    arrow_boundary = re.search(r"(?:→|⇒|->|➡︎|➡|⇨|↦)", head)
    if arrow_boundary and not head[: arrow_boundary.start()].strip():
        # 矢印から始まる継続行（⇒ニュリノ）は、その行のオート操作を
        # 継続先へ適用するため、通常どおり正規化する。
        arrow_boundary = None
    auto_head = head[: arrow_boundary.start()] if arrow_boundary else head
    auto_tail = head[arrow_boundary.start() :] if arrow_boundary else ""
    # オート語だけを強調したMarkdown装飾は不要なので外す。文章全体を
    # 強調しているケース（例: **オートonの方が良いかも**）には一致しない。
    bold_auto = r"\*\*((?:オート|AUTO)[ \t　]*(?:ON|OFF|オン|オフ))\*\*"
    auto_head = re.sub(bold_auto, r"\1", auto_head, flags=re.IGNORECASE)
    auto_tail = re.sub(bold_auto, r"\1", auto_tail, flags=re.IGNORECASE)
    auto_head = re.sub(
        r'''["「『]?(?:オート|AUTO)[ \t　]*(ON|OFF|オン|オフ)["」』]?''',
        lambda match: "🅰️ON" if match.group(1).upper() in {"ON", "オン"} else "🅰️OFF",
        auto_head,
        flags=re.IGNORECASE,
    )
    # YouTube備考欄・Discord投稿では、SETマスクの後ろに裸の on/off が
    # 付くことがある。コメント本文ではなく構造部だけを対象にする。
    auto_head = re.sub(
        r"(?<!🅰️)(?<![A-Za-z])(ON|OFF|オン|オフ)(?![A-Za-z])",
        lambda match: "🅰️ON" if match.group(1).upper() in {"ON", "オン"} else "🅰️OFF",
        auto_head,
        flags=re.IGNORECASE,
    )
    head = auto_head + auto_tail
    head = re.sub(r"(\[[54321-]{5}\])[ \t　]+(🅰️(?:ON|OFF))", r"\1\2", head)
    head = re.sub(r"[\"“”「」『』]\s*(🅰️(?:ON|OFF))\s*[\"“”「」『』]", r"\1", head)
    # YouTube/Discordの転記でSETとオート表記の間に残る単独の
    # アポストロフィだけを除去する。備考記号の ``''`` は保持する。
    head = re.sub(r"(?<!')['’](?=🅰️)|(?<=🅰️)['’](?!')", "", head)
    head = re.sub(r"(\[[54321-]{5}\])[ \t　]+(🅰️(?:ON|OFF))", r"\1\2", head)
    head = re.sub(r"^[ \t　]*(?:⭐️|⭐︎|⭐|★|☆)", "⭐️", head)
    head = re.sub(r"^[ \t　]*△", "🔺", head)
    # 投稿では時刻の後ろに手動記号が置かれることがあるが、手動UBの
    # 判定と表示を一貫させるため時刻の前へ移す。
    head = re.sub(
        r"^([ \t　]*)(\d{1,2}:\d{1,2}(?:[-〜~]\d{1,2})?)([ \t　]*)(?:⭐️|⭐︎|⭐|★|☆)",
        r"\1⭐️\2\3",
        head,
    )
    # 理想出力では矢印の前を全角3文字に統一する。
    head = re.sub(r"^[ \t　]*(?:->|>|→|➡︎|⇨|⇒)", "　　　→", head)
    head = re.sub(r"[ \t]+", "　", head)
    return head + comment


@dataclass
class Event:
    line_no: int
    raw: str
    prefix: str
    name: str | None
    star: bool
    arrow: bool
    mask: str | None
    manual_hint: bool = False

    @property
    def manual(self) -> bool:
        """SET計算上、手動発動として扱うべきかを返す。"""
        return self.star or self.manual_hint


def tl_declarations(text: str) -> list[tuple[str, str]]:
    """TL前の正式名・TL表記一覧を抽出する。最後の省略にも対応する。"""
    lines = text.splitlines()
    first_event = next(
        (i for i, line in enumerate(lines) if re.search(r"(?:\d{1,2}:\d{1,2}|⭐️|☆|△|⇒|→)", line)),
        len(lines),
    )
    declarations: list[tuple[str, str]] = []
    for index, line in enumerate(lines[:first_event]):
        formal = line.strip()
        if not formal or formal.startswith(("\\", "ーー", "--", "//", "TL表記")):
            continue
        # 別形式の編成メモ（例: ``キュリア R42最強 CR15 クリア``）は、
        # 行頭をTL表記、末尾を正式名として扱う。
        reverse_alias = re.fullmatch(r"(\S+)\s+.*\s+(\S+)", formal)
        if reverse_alias and re.search(r"\bCR\d+\b", formal, re.IGNORECASE):
            declarations.append((reverse_alias.group(2), reverse_alias.group(1)))
            continue
        if re.search(r"[ \t　]", formal):
            continue
        next_index = index + 1
        while next_index < first_event and (
            not lines[next_index].strip()
            or re.fullmatch(r"\\+", lines[next_index].strip())
        ):
            next_index += 1
        tl_match = (
            re.fullmatch(r"TL表記は\s*(\S+)", lines[next_index].strip())
            if next_index < first_event
            else None
        )
        if tl_match:
            declarations.append((formal, tl_match.group(1)))
            continue
        previous_index = index - 1
        while previous_index >= 0 and (
            not lines[previous_index].strip()
            or re.fullmatch(r"\\+", lines[previous_index].strip())
        ):
            previous_index -= 1
        if previous_index >= 0 and lines[previous_index].strip().startswith("TL表記は"):
            declarations.append((formal, formal))
    return declarations


def character_names_from_formation(text: str) -> dict[str, str]:
    """編成表から正式名・略称と固定番号の対応を取り出す。"""
    numbers: dict[str, str] = {}
    for line in text.splitlines():
        for match in FORMATION_ENTRY_RE.finditer(line):
            formal_name = match.group(2).strip()
            number = match.group(1)
            numbers[formal_name] = number
            alias = DISPLAY_NAMES.get(formal_name)
            if alias and alias not in numbers:
                numbers[alias] = number
    # 編成表がない投稿では、TL前の正式名／TL表記の5人の列挙順を
    # 記載順（1,2,3,4,5）を、そのままSET番号へ対応させる。
    declarations = tl_declarations(text)
    if len(declarations) == 5:
        for number, (formal, tl_name) in zip("12345", declarations):
            numbers.setdefault(formal, number)
            numbers.setdefault(tl_name, number)
    elif not numbers:
        # 編成表・宣言がない手動TLでも、5人だけが本文へ登場する場合は
        # ブラウザ版の編成自動入力と同じく、本文の初出順を5→1番へ対応させる。
        # 5人未満では番号を推測せず、従来どおりSETを自動生成しない。
        candidates = sorted(
            set(DISPLAY_NAMES) | set(DISPLAY_NAMES.values()),
            key=len,
            reverse=True,
        )
        first_seen: list[str] = []
        for line in text.splitlines():
            if not re.match(r"^\s*(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*(?:\d{1,2}:\d{1,2}|\d{1,2}(?=\s|　)|→|➡︎|⇨|⇒)", line):
                continue
            for candidate in candidates:
                if re.search(re.escape(candidate) + r"(?=\s|　|\[|\(|（|$)", line):
                    if candidate not in first_seen:
                        first_seen.append(candidate)
                    break
        if len(first_seen) == 5:
            for number, name in zip("54321", first_seen):
                numbers[name] = number
    return numbers


def display_names_from_tl_declarations(text: str) -> dict[str, str]:
    """本文冒頭の「正式名／TL表記」宣言を表示名へ反映する。"""
    aliases: dict[str, str] = {}
    for formal, tl_name in tl_declarations(text):
            # 本文のTL表記を正式名へ戻す。正式名が本文に直接書かれて
            # いる場合も、同じ正式名のまま表示できるよう登録する。
            aliases[formal] = formal
            aliases[tl_name] = formal
    return aliases


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
        if end is not None and len(end) == 1:
            end = str((int(match.group(2)) // 10) * 10 + int(end))
        return f"{minute}:{second}" + (f"-{end.zfill(2)}" if end is not None else "")

    def shorten_full_range(match: re.Match[str]) -> str:
        start_minute, end_minute = match.group(1), match.group(3)
        if int(start_minute) != int(end_minute):
            return match.group(0)
        return f"{match.group(1)}:{match.group(2)}-{match.group(4)}"

    normalized = re.sub(
        r"(\d{1,2}):(\d{1,2})[ \t　]*[〜~～－ー―‐—–-][ \t　]*(\d{1,2}):(\d{1,2})(?=\D|$)",
        shorten_full_range,
        prefix,
        count=1,
    )
    normalized = re.sub(
        r"(\d{1,2}:\d{1,2})[ \t　]*[〜~～－ー―‐—–-][ \t　]*(\d{1,2})(?=\D|$)",
        r"\1-\2",
        normalized,
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
    stripped = re.sub(r"^(?:⭐️|⭐︎|⭐|🔺|△)+", "", stripped).lstrip("　 \t")
    if bool(TIME_RE.match(stripped) or BARE_TIME_RE.match(stripped)) or stripped.startswith("→"):
        return True
    # 時刻を省略した矢印先・発動行（例: 「ルルィ [54321]」）を認識する。
    return bool(MASK_RE.search(stripped) and not stripped.startswith("["))


def parse_event(
    line_no: int,
    line: str,
    character_names: dict[str, str] | None = None,
) -> Event:
    mask_match = MASK_RE.search(line)
    mask = mask_match.group(1) if mask_match else None
    if not is_event_line(line):
        return Event(line_no, line, "", None, False, False, mask)

    arrow = "→" in line and not bool(TIME_RE.match(line.lstrip("　 \t")))
    star = "⭐️" in line or "⭐︎" in line or "⭐" in line
    name = None
    prefix = line

    # 名前の直後は、区切り空白・SETマスク・行末のいずれかであることを要求する。
    # Discord/YouTube由来のTLは編成表を含まないことが多い。編成表が
    # ない場合でも、既知の正式名・略称を候補にしてキャラ欄を分離する。
    candidates = list(character_names or {}) + list(DISPLAY_NAMES) + list(CHARACTERS)
    for candidate in sorted(set(candidates), key=len, reverse=True):
        match = re.search(re.escape(candidate) + r"(?=　|\s|\[|\(|（|$)", line)
        if match:
            name = candidate
            prefix = line[: match.start()]
            break

    if name is None:
        # 学習データでは時刻とキャラ名が連結した行（1:16サレン）や、
        # 時刻直後に手動記号が付く行（1:02★ペコ）がある。通常の
        # 「キャラ名と備考の連結」には適用せず、時刻との境界だけ補う。
        time_match = re.match(r"^(.*?\d{1,2}:\d{1,2}(?:[-〜~]\d{1,2})?)(.*)$", line)
        if time_match:
            between = time_match.group(2)
            body = between.lstrip("　 \t")
            star_prefix = re.match(r"(?:⭐️|⭐︎|⭐|★|☆)", body)
            if star_prefix:
                body = body[star_prefix.end():]
            had_separator = bool(re.match(r"^[　 \t]", between))
            for candidate in sorted(set(candidates), key=len, reverse=True):
                if not body.startswith(candidate):
                    continue
                # 空白で区切られていた行は、★/⭐️付きだけを対象にする。
                if had_separator and not star_prefix:
                    continue
                name = candidate
                prefix = line[: line.find(candidate)]
                break

    if name is None and mask is not None:
        # CHARACTERSに未登録のキャラも書式整形だけは可能にする。
        # SETの意味付けは編成表でキャラ番号が確定した後に行う。
        body = line
        body = re.sub(r"^\s*(?:⭐️|⭐︎|⭐|★|☆)?\s*", "", body)
        body = re.sub(r"^(?:\d{1,2}:\d{1,2}|\d{1,2})\s*", "", body)
        body = re.sub(r"^→\s*", "", body)
        generic = re.match(r"([^\s　\[\]【】()（）]+)(?=[\s　\[\(（]|$)", body)
        if generic and (
            len(generic.group(1)) <= 4
            or generic.group(1) in (character_names or {})
        ):
            name = generic.group(1)
            prefix = line[: line.find(name)]

    if name is None and is_event_line(line) and TIME_RE.search(line):
        # 編成表のない投稿では、短いキャラ名が時刻直後に現れる。
        # コメントや説明文を名前と誤認しないよう、時刻直後の先頭語だけを対象にする。
        body = line
        body = re.sub(r"^\s*(?:⭐️|⭐︎|⭐|★|☆|🔺|△)?\s*", "", body)
        body = re.sub(r"^(?:\d{1,2}:\d{1,2}(?:[-〜~]\d{1,2})?|\d{1,2})\s*", "", body)
        body = re.sub(r"^(?:→|⇒|->|>|➡︎|➡|⇨)\s*", "", body)
        generic = re.match(r"([^\s　\[\]【】()（）'\"「」『』]+)", body)
        if generic and len(generic.group(1)) <= 8:
            candidate = generic.group(1)
            if candidate not in {"開始時", "開始", "バトル開始", "ボス", "止めぽ"}:
                name = candidate
                prefix = line[: line.find(candidate)]

    if name is None:
        # 時刻付きの未登録キャラも、編成表から後で番号を解決できるよう抽出する。
        body = line
        body = re.sub(r"^\s*(?:⭐️|⭐︎|⭐|★|☆)?\s*", "", body)
        body = re.sub(r"^(?:\d{1,2}:\d{1,2}|\d{1,2})\s*", "", body)
        body = re.sub(r"^→\s*", "", body)
        generic = re.match(r"([^\s　\[\]【】()（）]+)(?=[\s　\[\(（]|$)", body)
        if generic and (
            len(generic.group(1)) <= 4
            or generic.group(1) in (character_names or {})
        ):
            name = generic.group(1)
            prefix = line[: line.find(name)]

    # 開始行・ボス行はキャラクター発動ではない。
    if name in {"開始時", "開始", "バトル開始", "止めぽ"}:
        name = None

    manual_hint = False
    if name is not None and mask is None:
        # ``#`` や ``//`` は単なるコメントであり、それだけでは手動
        # 要素にしない。通常のキャラ行はSET対象とし、直後の `'` / `''`
        # だけを手動候補として扱う。
        name_end = line.find(name) + len(name)
        suffix = line[name_end:]
        suffix_stripped = suffix.strip(" \t　")
        structural_suffix = re.split(r"//|''", suffix, maxsplit=1)[0]
        structural_suffix = structural_suffix.strip(" \t　")
        is_quoted_auto_note = bool(
            re.fullmatch(r"[\"‘’“”「」『』']*オート[\"‘’“”「」『』']*", suffix_stripped)
        )
        is_auto_note = bool(
            re.fullmatch(r"(?:#?オート|[（(]オート[）)])", structural_suffix)
        )
        is_auto_marker = bool(re.fullmatch(r"🅰️(?:ON|OFF)", structural_suffix))
        comment_only = suffix_stripped.startswith(("#", "//"))
        if (
            not comment_only
            and not is_quoted_auto_note
            and not is_auto_note
            and not is_auto_marker
            and (suffix_stripped.startswith("'") or structural_suffix)
        ):
            manual_hint = True

    return Event(line_no, line, prefix, name, star, arrow, mask, manual_hint)


def render_event(
    event: Event,
    mask: str | None = None,
    allow_long_name: bool = False,
    display_names: dict[str, str] | None = None,
) -> str:
    """イベント行のキャラ欄とSET表記を正規化する。"""
    if not event.name:
        return event.raw

    prefix = normalize_time_prefix(event.prefix.rstrip(" \t　"))
    if event.arrow:
        # 元の🔺などの注記は残し、矢印と名前の間は全角スペース1個にする。
        prefix += "　"
    else:
        prefix += "　"

    display_name = (display_names or DISPLAY_NAMES).get(event.name, event.name)
    if len(display_name) > 4 and not allow_long_name:
        raise ValueError(f"表示名が全角4文字を超えています。4文字略称を登録してください: {event.name}")
    name_field = display_name + "　" * max(0, 4 - len(display_name))
    rest = event.raw[event.raw.find(event.name) + len(event.name):]
    # 先頭のSETマスクだけを取り出し、備考中の追加マスクは保持する。
    rest = MASK_RE.sub("", rest, count=1)
    rest = rest.strip(" \t　")

    auto_match = re.search(r"🅰️(?:ON|OFF)", rest)
    auto = auto_match.group(0) if auto_match else None
    if auto:
        rest = (rest[:auto_match.start()] + rest[auto_match.end():]).strip(" \t　")

    prefix_parts: list[str] = []
    if mask is not None:
        prefix_parts.append(mask)
    if auto:
        prefix_parts.append(auto)
    suffix = "".join(prefix_parts)
    if rest:
        suffix += ("　" if suffix else "") + rest
    if not suffix:
        return prefix + display_name
    return prefix + name_field + "　" + suffix
