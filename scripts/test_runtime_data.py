import json
import tempfile
import unittest
from pathlib import Path

from reconcile_runtime_data import ROOT, reconcile


class RuntimeDataTests(unittest.TestCase):
    def test_checked_in_browser_and_package_data_match(self):
        for name in ("character_aliases.json", "character_master.json", "boss_names.json"):
            with self.subTest(name=name):
                self.assertEqual(
                    (ROOT / "data" / name).read_bytes(),
                    (ROOT / "priconner_tl" / "data" / name).read_bytes(),
                )

    def test_reconcile_preserves_reviewed_aliases_and_new_sheet_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            browser = root / "data"
            packaged = root / "priconner_tl" / "data"
            browser.mkdir(parents=True)
            packaged.mkdir(parents=True)
            (browser / "character_aliases.json").write_text(json.dumps({
                "character_aliases": {"ヴァイオレット": "ヴァイオレット", "新キャラ": "新"},
                "learned_name_aliases": {},
            }), encoding="utf-8")
            (packaged / "character_aliases.json").write_text(json.dumps({
                "character_aliases": {"ヴァイオレット": "すみれ", "旧キャラ": "旧"},
                "learned_name_aliases": {"スミレ": "すみれ"},
            }), encoding="utf-8")
            (browser / "character_master.json").write_text("{}\n", encoding="utf-8")
            (browser / "boss_names.json").write_text(
                json.dumps({"boss_names": ["新ボス"]}), encoding="utf-8")
            (packaged / "boss_names.json").write_text(
                json.dumps({"boss_names": ["旧ボス"]}), encoding="utf-8")
            reconcile(root)
            aliases = json.loads((browser / "character_aliases.json").read_text(encoding="utf-8"))
            self.assertEqual(aliases["character_aliases"], {
                "ヴァイオレット": "すみれ", "新キャラ": "新", "旧キャラ": "旧",
            })
            self.assertEqual(aliases["learned_name_aliases"], {"スミレ": "すみれ"})
            self.assertEqual((browser / "character_aliases.json").read_bytes(),
                             (packaged / "character_aliases.json").read_bytes())
            self.assertEqual(json.loads((browser / "boss_names.json").read_text(encoding="utf-8")),
                             {"boss_names": ["新ボス", "旧ボス"]})


if __name__ == "__main__":
    unittest.main()
