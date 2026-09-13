#!/usr/bin/env python3
"""Fetch the character-name sheet and build the runtime alias JSON."""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

DEFAULT_SPREADSHEET_ID = "1dBdhRLehzwKyKKKt0OLBDXqy4F2L_cd_HF6-KOqu4vM"
DEFAULT_GID = "1581974480"


def fetch_csv(spreadsheet_id: str, gid: str, opener=urlopen) -> str:
    url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"
    request = Request(url, headers={"User-Agent": "priconner-tl-formatter/1.0"})
    with opener(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def build_aliases(csv_text: str) -> dict[str, dict[str, str]]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    if not rows or rows[0][:3] != ["キャラID", "名称", "略称"]:
        raise ValueError("キャラタブのヘッダーが想定と異なります")
    aliases: dict[str, str] = {}
    for row in rows[1:]:
        if len(row) < 3:
            continue
        formal, short = row[1].strip(), row[2].strip()
        if formal and short and formal != short:
            aliases[formal] = short
    return {"character_aliases": dict(sorted(aliases.items())), "learned_name_aliases": {}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", default=os.getenv("CHARACTER_ALIAS_SHEET_ID", DEFAULT_SPREADSHEET_ID))
    parser.add_argument("--gid", default=os.getenv("CHARACTER_ALIAS_SHEET_GID", DEFAULT_GID))
    parser.add_argument("--json", default="data/character_aliases.json")
    args = parser.parse_args(argv)
    payload = build_aliases(fetch_csv(args.spreadsheet_id, args.gid))
    output = Path(args.json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"エイリアス同期完了: {len(payload['character_aliases'])}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
