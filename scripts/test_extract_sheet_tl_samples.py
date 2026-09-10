import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("extract_sheet_tl_samples.py")
spec = importlib.util.spec_from_file_location("extract_sheet_tl_samples", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class ExtractCandidateTLTests(unittest.TestCase):
    def test_extracts_character_only_lines_after_tl_header(self):
        description = """◆編成
ユカリ

◆TL

開始(ーー〇〇ー)
スズナ
    →スズナ

※1
補足
"""
        self.assertEqual(
            module.extract_candidate_tl(description),
            "開始(ーー〇〇ー)\nスズナ\n    →スズナ\n",
        )

    def test_falls_back_to_timestamp_lines_without_header(self):
        self.assertEqual(
            module.extract_candidate_tl("1:23 ユカリ\n→スズナ\n説明"),
            "1:23 ユカリ\n→スズナ\n",
        )


if __name__ == "__main__":
    unittest.main()
