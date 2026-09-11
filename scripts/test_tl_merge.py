import unittest

from tl_merge import merge_events, parse_events


FORMATION = [
    "アオイ（パイロット）",
    "ネフィ＝ネラ（鬼面仏心）",
    "ツムギ（ジオ・ゲヘナ）",
    "ペコリーヌ（ニューイヤー）",
    "シェフィ（サマー）",
]


class TLMergeTests(unittest.TestCase):
    def test_game_short_name_resolves_to_formation_name(self):
        events, unresolved = parse_events("01:15 ネラ\n01:08 シェフィ（サマー）", "a", FORMATION)
        self.assertEqual(unresolved, [])
        self.assertEqual([event.name for event in events], [
            "ネフィ＝ネラ（鬼面仏心）", "シェフィ（サマー）"
        ])

    def test_same_event_is_common_and_different_names_are_conflicts(self):
        a, _ = parse_events("01:15 ネラ\n01:08 シェフィ（サマー）", "a", FORMATION)
        b, _ = parse_events("01:15 ネラ\n01:08 ペコリーヌ（ニューイヤー）", "b", FORMATION)
        merged = merge_events(a, b)
        self.assertEqual(len(merged["common"]), 1)
        self.assertEqual(merged["conflicts"], [{
            "seconds": 68,
            "names": ["シェフィ（サマー）", "ペコリーヌ（ニューイヤー）"],
        }])

    def test_unresolved_short_name_is_reported(self):
        events, unresolved = parse_events("01:00 未登録", "a", FORMATION)
        self.assertEqual(events, [])
        self.assertEqual(unresolved, ["未登録"])


if __name__ == "__main__":
    unittest.main()
