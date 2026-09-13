#!/usr/bin/env python3
"""Fetch the current full boss list and build the runtime boss-name JSON."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_SPREADSHEET_ID = "1JQfLmv_OZnnDeLyr2WByM0rLLSFP-mwUsmXM_oBIwRQ"
DEFAULT_GID = "688432019"  # clan_battle_bosses


def fetch_csv(spreadsheet_id: str, gid: str, opener=urlopen) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    request = Request(url, headers={"User-Agent": "priconner-tl-formatter/1.0"})
    with opener(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def build_boss_names(csv_text: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    if rows and rows[0][:5] == ["id", "name", "name_en", "aliases", "release"]:
        names = [row[1].strip() for row in rows[1:] if len(row) >= 2 and row[1].strip()]
        if not names:
            raise ValueError("ボス名を1件も取得できませんでした")
        return list(dict.fromkeys(names))
    if len(rows) < 2 or not rows[0] or rows[0][0] != "boss1":
        raise ValueError("★boss_nameタブのヘッダーが想定と異なります")
    names = [cell.strip() for cell in rows[1] if cell.strip()]
    if not names:
        raise ValueError("ボス名を1件も取得できませんでした")
    return list(dict.fromkeys(names))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", default=os.getenv("BOSS_SHEET_ID", DEFAULT_SPREADSHEET_ID))
    parser.add_argument("--gid", default=os.getenv("BOSS_SHEET_GID", DEFAULT_GID))
    parser.add_argument("--json", default="data/boss_names.json")
    args = parser.parse_args(argv)
    names = build_boss_names(fetch_csv(args.spreadsheet_id, args.gid))
    output = Path(args.json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"boss_names": names}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ボス名同期完了: {len(names)}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
