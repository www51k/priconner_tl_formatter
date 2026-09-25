"""Keep browser data and the installed Python package on the same snapshot."""
from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def reconcile(root: Path = ROOT) -> None:
    browser = root / "data"
    packaged = root / "priconner_tl" / "data"
    packaged.mkdir(parents=True, exist_ok=True)

    browser_aliases = json.loads((browser / "character_aliases.json").read_text(encoding="utf-8"))
    packaged_aliases = json.loads((packaged / "character_aliases.json").read_text(encoding="utf-8"))
    # The generated sheet can omit legacy characters or use a formal name as
    # its first alias. Keep the existing, reviewed short names for those cases.
    merged = {
        key: dict(sorted({**browser_aliases.get(key, {}), **packaged_aliases.get(key, {})}.items()))
        for key in ("character_aliases", "learned_name_aliases")
    }
    payload = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    (browser / "character_aliases.json").write_text(payload, encoding="utf-8")
    (packaged / "character_aliases.json").write_text(payload, encoding="utf-8")

    shutil.copyfile(browser / "character_master.json", packaged / "character_master.json")

    browser_bosses = json.loads((browser / "boss_names.json").read_text(encoding="utf-8"))["boss_names"]
    packaged_bosses = json.loads((packaged / "boss_names.json").read_text(encoding="utf-8"))["boss_names"]
    bosses = json.dumps({"boss_names": list(dict.fromkeys([*browser_bosses, *packaged_bosses]))},
                       ensure_ascii=False, indent=2) + "\n"
    (browser / "boss_names.json").write_text(bosses, encoding="utf-8")
    (packaged / "boss_names.json").write_text(bosses, encoding="utf-8")


if __name__ == "__main__":
    reconcile()
