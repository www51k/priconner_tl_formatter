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

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/priconner51bk-prog/priconner_master_data/main/dist/characters.csv"


def fetch_csv(url: str, opener=urlopen) -> str:
    request = Request(url, headers={"User-Agent": "priconner-tl-formatter/1.0"})
    with opener(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def build_aliases(csv_text: str) -> dict[str, dict[str, str]]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    if rows and rows[0][:4] == ["id", "name", "name_en", "aliases"]:
        aliases: dict[str, str] = {}
        for row in rows[1:]:
            if len(row) < 2 or not row[1].strip():
                continue
            formal = row[1].strip()
            values = []
            if len(row) >= 4 and row[3].strip():
                try:
                    values = json.loads(row[3])
                except json.JSONDecodeError:
                    values = [row[3]]
            # Runtime convention is formal name -> display alias. The unified
            # sheet stores both in the aliases array, so choose the first
            # non-formal alias as the display form.
            for value in values:
                alias = str(value).strip()
                if alias and alias != formal:
                    aliases[formal] = alias
                    break
        return {
            "character_aliases": dict(sorted(aliases.items())),
            "learned_name_aliases": {"スミレ": "すみれ"},
        }
    if not rows or rows[0][:3] != ["キャラID", "名称", "略称"]:
        raise ValueError("キャラタブのヘッダーが想定と異なります")
    aliases: dict[str, str] = {}
    for row in rows[1:]:
        if len(row) < 3:
            continue
        formal, short = row[1].strip(), row[2].strip()
        if formal and short and formal != short:
            aliases[formal] = short
    # 旧TLで使われていた表記も、シートの正式な略称へ寄せる。
    return {
        "character_aliases": dict(sorted(aliases.items())),
        "learned_name_aliases": {"スミレ": "すみれ"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=os.getenv("CHARACTER_SOURCE_URL", DEFAULT_SOURCE_URL))
    parser.add_argument("--json", default="data/character_aliases.json")
    args = parser.parse_args(argv)
    payload = build_aliases(fetch_csv(args.source_url))
    output = Path(args.json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"エイリアス同期完了: {len(payload['character_aliases'])}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
