#!/usr/bin/env python3
"""Google SheetsのYouTube備考欄からTLサンプルをローカル抽出する。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    from yt_dlp import YoutubeDL
except ModuleNotFoundError:  # pragma: no cover - optional for text-only tests
    YoutubeDL = None  # type: ignore[assignment,misc]


def _load_gspread_utils():
    """Load the scanner project's Sheets helper only when Sheets access is used."""
    scanner_root = Path(
        os.environ.get("TL_MOVIE_SCANNER_ROOT", "/Users/waka/git/priconner_tl_movie_scanner")
    )
    if str(scanner_root) not in sys.path:
        sys.path.insert(0, str(scanner_root))
    try:
        import gspread_utils  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Google Sheets access requires gspread_utils; set TL_MOVIE_SCANNER_ROOT "
            "to the scanner project directory."
        ) from exc
    return gspread_utils


URL_RE = re.compile(r"https?://(?:www\.)?youtu\.be/[^\s]+|https?://(?:www\.)?youtube\.com/watch\?[^\s]+")
TL_LINE_RE = re.compile(
    r"^\s*(?:(?:[⭐☆★](?:️)?|🔺|△)?(?:\d{1,2}:\d{1,2}|\d{1,2})(?:[-〜~]\d{1,2})?|(?:[⭐☆★](?:️)?|🔺|△)?\s*(?:→|⇒|->|➡︎|➡|⇨))"
)
TL_HEADER_RE = re.compile(
    r"^\s*(?:[◆◇■□#]\s*)?(?:TL(?:全文)?|ユニオンバースト発動時間)\s*(?:⭐[️️]?は目押し)?\s*$",
    re.IGNORECASE,
)
SECTION_STOP_RE = re.compile(r"^\s*(?:※|注釈|備考|参考|#|◆|◇|■|□)")


def extract_candidate_tl(description: str) -> str:
    """説明欄のTL候補を抽出する（編成・SET意味は解釈しない）。"""
    sections = extract_candidate_tl_sections(description)
    return "\n\n".join(sections) + ("\n" if sections else "")


def extract_candidate_tl_sections(description: str) -> list[str]:
    """明示見出しごとのTL候補を、原文順のまま分割して返す。"""
    lines = [line.rstrip() for line in description.splitlines()]
    header_indexes = [i for i, line in enumerate(lines) if TL_HEADER_RE.match(line)]
    if header_indexes:
        sections = []
        prefix_lines = lines[: header_indexes[0]]
        in_code_block = False
        code_prefix = []
        for line in prefix_lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block and TL_LINE_RE.match(line) and not URL_RE.search(line):
                code_prefix.append(line)
        prefix = code_prefix or [
            line for line in prefix_lines if TL_LINE_RE.match(line) and not URL_RE.search(line)
        ]
        if prefix:
            sections.append("\n".join(prefix))
        for header_index in header_indexes:
            selected = []
            for line in lines[header_index + 1:]:
                if TL_HEADER_RE.match(line) or (SECTION_STOP_RE.match(line) and selected):
                    break
                if line.strip() and not URL_RE.search(line):
                    selected.append(line)
            if selected:
                sections.append("\n".join(selected))
        return sections
    selected = [line for line in lines if TL_LINE_RE.match(line) and not URL_RE.search(line)]
    return ["\n".join(selected)] if selected else []


def extract_urls(spreadsheet_id: str) -> list[dict[str, object]]:
    gspread_utils = _load_gspread_utils()
    spreadsheet = gspread_utils._get_spreadsheet(spreadsheet_id)
    samples: list[dict[str, object]] = []
    for worksheet in spreadsheet.worksheets():
        rows = worksheet.get_all_values()
        for row_number, row in enumerate(rows[2:], 3):
            url = row[5].strip() if len(row) > 5 else ""
            if not URL_RE.match(url):
                continue
            samples.append({
                "sheet": worksheet.title,
                "row": row_number,
                "url": url,
            })
    return samples


def fetch_one(sample: dict[str, object]) -> dict[str, object]:
    if YoutubeDL is None:
        raise RuntimeError("YouTube description access requires yt-dlp")
    options = {
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
        "socket_timeout": 20,
        "retries": 0,
        "extractor_retries": 0,
        "fragment_retries": 0,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
        "remote_components": ["ejs:github"],
    }
    with YoutubeDL(options) as ydl:
        try:
            info = ydl.extract_info(str(sample["url"]), download=False) or {}
            sample["title"] = info.get("title", "")
            sample["description"] = info.get("description", "")
            sample["description_fetch_ok"] = bool(info)
            description = str(sample["description"])
            sample["candidate_tl_sections"] = extract_candidate_tl_sections(description)
            sample["candidate_tl"] = extract_candidate_tl(description)
        except Exception as exc:  # noqa: BLE001 - one bad URL must not stop the batch
            sample["description_fetch_ok"] = False
            sample["fetch_error"] = f"{type(exc).__name__}: {exc}"
            sample["candidate_tl_sections"] = []
            sample["candidate_tl"] = ""
    return sample


def fetch_descriptions(samples: list[dict[str, object]], workers: int = 8) -> list[dict[str, object]]:
    completed: dict[int, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one, sample): index for index, sample in enumerate(samples)}
        for future in as_completed(futures):
            index = futures[future]
            completed[index] = future.result()
    return [completed[index] for index in range(len(samples))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spreadsheet_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    samples = fetch_descriptions(extract_urls(args.spreadsheet_id))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(sample, ensure_ascii=False) + "\n" for sample in samples),
        encoding="utf-8",
    )
    print(f"extracted {len(samples)} samples to {args.output}")


if __name__ == "__main__":
    main()
