#!/usr/bin/env python3
"""Fetch the public character sheet and build a versioned name master.

The generated files are committed by CI and consumed offline by the web app.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_SPREADSHEET_ID = "1S2AOOnx6_Wk95atC_s0Rimeo1YPyYxaegQj8dCovjt4"
DEFAULT_GID = "1793615076"


def fetch_csv(spreadsheet_id: str, gid: str, opener=urlopen) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    request = Request(url, headers={"User-Agent": "priconner-tl-formatter/1.0"})
    with opener(request, timeout=30) as response:
        payload = response.read()
    return payload.decode("utf-8-sig")


def build_master(csv_text: str) -> dict[str, dict[str, object]]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    if len(rows) < 3:
        raise ValueError("引用情報シートにデータ行がありません")
    # The sheet's stable data columns are G:J and L:O (zero-based 6:10, 11:15).
    records: dict[str, dict[str, object]] = {}

    def add(formal: str, alias: str, unit_id: str, image: str) -> None:
        formal, alias, unit_id = formal.strip(), alias.strip(), unit_id.strip()
        if not unit_id or not (formal or alias):
            return
        item = records.setdefault(unit_id, {"formal_name": formal or alias, "aliases": [], "image_url": image.strip()})
        if formal and not item["formal_name"]:
            item["formal_name"] = formal
        if image.strip() and not item["image_url"]:
            item["image_url"] = image.strip()
        aliases = item["aliases"]
        for value in (formal, alias):
            if value and value not in aliases:
                aliases.append(value)

    for row in rows[2:]:
        row += [""] * (15 - len(row))
        add(row[6], row[7], row[8], row[9])
        # L:O is the generated all-alias index: alias, ID, formal name, image.
        add(row[13], row[11], row[12], row[14])
    if not records:
        raise ValueError("キャラクターマスタを1件も取得できませんでした")
    return dict(sorted(records.items()))


def write_outputs(master: dict[str, dict[str, object]], json_path: Path, python_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    python_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(master, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    python_path.write_text(
        "\"\"\"Generated from the public character sheet; do not edit manually.\"\"\"\n"
        "CHARACTER_MASTER = " + repr(master) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", default=os.getenv("CHARACTER_SHEET_ID", DEFAULT_SPREADSHEET_ID))
    parser.add_argument("--gid", default=os.getenv("CHARACTER_SHEET_GID", DEFAULT_GID))
    parser.add_argument("--json", default="data/character_master.json")
    parser.add_argument("--python", dest="python_path", default="scripts/character_master.py")
    args = parser.parse_args(argv)
    text = fetch_csv(args.spreadsheet_id, args.gid)
    master = build_master(text)
    write_outputs(master, Path(args.json), Path(args.python_path))
    print(f"同期完了: {len(master)}キャラ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
