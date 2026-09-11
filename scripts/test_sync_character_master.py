import unittest

from sync_character_master import build_master


class CharacterMasterSyncTests(unittest.TestCase):
    def test_builds_formal_and_alias_rows_by_id(self):
        csv_text = "\n".join([
            ",No,当月ボス一覧,画像,, ,正式名称,追加の愛称,ID,画像,,愛称含む全登録一覧,ID,キャラ名,画像",
            ",,,,,,,,,,,,,,,",
            ",,,,,,ヴァイオレット,すみれ,133101,icon.png,,,,,,",
            ",,,,,,,,,,,スミレ,133101,ヴァイオレット,icon.png",
        ])
        master = build_master(csv_text)
        self.assertEqual(master["133101"]["formal_name"], "ヴァイオレット")
        self.assertEqual(master["133101"]["aliases"], ["ヴァイオレット", "すみれ", "スミレ"])
        self.assertEqual(master["133101"]["image_url"], "icon.png")

    def test_empty_sheet_is_rejected(self):
        with self.assertRaises(ValueError):
            build_master("a,b,c\n1,2,3\n")


if __name__ == "__main__":
    unittest.main()
