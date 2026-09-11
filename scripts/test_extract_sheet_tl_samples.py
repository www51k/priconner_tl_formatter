import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("extract_sheet_tl_samples.py")
spec = importlib.util.spec_from_file_location("extract_sheet_tl_samples", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class ExtractCandidateTLTests(unittest.TestCase):
    def test_fetch_one_keeps_candidate_sections_in_result(self):
        class FakeYoutubeDL:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, url, download=False):
                return {
                    "title": "sample",
                    "description": "◆TL\n1:20 クリア\n◆注釈\n0:05 補足\n◆TL全文\n1:10 サレン\n◆注釈\n",
                }

        original = module.YoutubeDL
        module.YoutubeDL = FakeYoutubeDL
        try:
            result = module.fetch_one({"url": "https://youtu.be/example"})
        finally:
            module.YoutubeDL = original
        self.assertEqual(result["candidate_tl_sections"], ["1:20 クリア", "1:10 サレン"])
        self.assertEqual(result["candidate_tl"], "1:20 クリア\n\n1:10 サレン\n")

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

    def test_extracts_youtube_style_fullwidth_tl_until_hashtags(self):
        description = """◆TL
　1:30　バトル開始　[〇〇〇〇〇]"AUTO"
☆01:20 クリア　聖槍付与後
   →　リリ

== 0:33 BOSS UB ==

#プリコネR
#クランバトル
"""
        self.assertEqual(
            module.extract_candidate_tl(description),
            "　1:30　バトル開始　[〇〇〇〇〇]\"AUTO\"\n"
            "☆01:20 クリア　聖槍付与後\n"
            "   →　リリ\n"
            "== 0:33 BOSS UB ==\n"
            ,
        )

    def test_recognizes_full_tl_header_and_stops_before_notes(self):
        description = """◆ユニオンバースト発動時間
1:30 バトル開始
1:20 クリア
0:10 サレン

◆注釈
0:05の操作は早すぎると失敗
"""
        self.assertEqual(
            module.extract_candidate_tl(description),
            "1:30 バトル開始\n1:20 クリア\n0:10 サレン\n",
        )

    def test_preserves_multiple_explicit_tl_sections_in_order(self):
        description = """◆TL
1:20 クリア
◆注釈
0:05 補足
◆ユニオンバースト発動時間
1:10 サレン
◆注釈
0:01 補足
"""
        self.assertEqual(
            module.extract_candidate_tl_sections(description),
            ["1:20 クリア", "1:10 サレン"],
        )
        self.assertEqual(module.extract_candidate_tl(description), "1:20 クリア\n\n1:10 サレン\n")

    def test_keeps_code_block_tl_before_explicit_header(self):
        description = """```cs
1:20 クリア
   → リリ
```
◆ユニオンバースト発動時間
1:10 サレン
◆注釈
0:01 補足
"""
        self.assertEqual(
            module.extract_candidate_tl_sections(description),
            ["1:20 クリア\n   → リリ", "1:10 サレン"],
        )


if __name__ == "__main__":
    unittest.main()
