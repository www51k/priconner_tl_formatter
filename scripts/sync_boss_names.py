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

DEFAULT_SOURCE_URL = "https://raw.githubusercontent.com/priconner51bk-prog/priconner_master_data/main/dist/clan_battle_bosses.csv"


def fetch_csv(url: str, opener=urlopen) -> str:
    request = Request(url, headers={"User-Agent": "priconner-tl-formatter/1.0"})
    with opener(request, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def build_boss_names(csv_text: str) -> list[str]:
    rows = list(csv.reader(io.StringIO(csv_text)))
    if rows and rows[0] == ["ボス名"]:
        names = [row[0].strip() for row in rows[1:] if row and row[0].strip()]
        if not names:
            raise ValueError("ボス名を1件も取得できませんでした")
        return list(dict.fromkeys(names))

    # 上流CSVは列の追加・並べ替えがあるため、名前列の位置はヘッダーから判定する。
    if rows:
        header = [column.strip().lower() for column in rows[0]]
        if "name" in header:
            name_index = header.index("name")
            names = [row[name_index].strip() for row in rows[1:] if len(row) > name_index and row[name_index].strip()]
            if not names:
                raise ValueError("ボス名を1件も取得できませんでした")
            return list(dict.fromkeys(names))

    if len(rows) < 2 or not rows[0] or rows[0][0].strip() != "boss1":
        header = ",".join(rows[0]) if rows else "(空)"
        raise ValueError(f"ボス名CSVのヘッダーが想定外です: {header}")
    names = [cell.strip() for cell in rows[1] if cell.strip()]
    if not names:
        raise ValueError("ボス名を1件も取得できませんでした")
    return list(dict.fromkeys(names))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-url", default=os.getenv("BOSS_SOURCE_URL", DEFAULT_SOURCE_URL))
    parser.add_argument("--json", default="data/boss_names.json")
    args = parser.parse_args(argv)
    names = build_boss_names(fetch_csv(args.source_url))
    output = Path(args.json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"boss_names": names}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ボス名同期完了: {len(names)}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
