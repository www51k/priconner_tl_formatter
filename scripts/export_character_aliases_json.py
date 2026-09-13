"""Export the legacy alias module to the JSON data source."""
from __future__ import annotations

import json
from pathlib import Path

from character_aliases import CHARACTER_ALIASES, LEARNED_NAME_ALIASES

output = Path(__file__).resolve().parent.parent / "data" / "character_aliases.json"
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(
    json.dumps(
        {"character_aliases": CHARACTER_ALIASES, "learned_name_aliases": LEARNED_NAME_ALIASES},
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)
