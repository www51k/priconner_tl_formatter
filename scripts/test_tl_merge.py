import json
import tempfile
import unittest
from pathlib import Path

from tl_merge import expand_arrow_times, main, merge_events, merge_texts, parse_events


FORMATION = [
    "アオイ（パイロット）",
    "ネフィ＝ネラ（鬼面仏心）",
    "ツムギ（ジオ・ゲヘナ）",
    "ペコリーヌ（ニューイヤー）",
    "シェフィ（サマー）",
]


class TLMergeTests(unittest.TestCase):
    def test_same_second_events_remain_arrow_chain_across_source_blank_lines(self):
        from priconner_tl.formatter import format_text

        battle = "0:44 クレジッタ\n0:44 グレア\n0:42 ミホ"
        formatted = "0:44 ジッタ [--321]\n\n0:44 グレア\n0:42 ミホ"
        output = format_text(merge_texts(battle, formatted)["text"])
        self.assertIn("0:44　ジッタ　　[--321]\n　　→　グレア\n0:42　ミホ", output)

    def test_merge_formats_ten_second_boundary_before_unknown_boss(self):
        from priconner_tl.formatter import format_text

        battle = "0:23 マホ\n0:17 アーク・デアム\n0:16 アメス\n0:16 アメス"
        formatted = "0:23 マホ\n0:16 アメス"
        output = format_text(merge_texts(battle, formatted)["text"])
        self.assertIn("0:23　マホ\n\n0:17　アーク・デアム\n0:16　アメス", output)
        self.assertIn("→　アメス", output)

    def test_unregistered_boss_is_retained_through_formatting(self):
        from priconner_tl.merge import merge_texts as package_merge_texts
        from priconner_tl.formatter import format_text

        battle = "00:02 アメス\n00:02 クレジッタ\n00:02 グレア\n00:02 アーク・デアム"
        formatted = "0:02 アメス\n0:02 クレジッタ\n0:02 グレア"
        for merge in (merge_texts, package_merge_texts):
            with self.subTest(merge=merge.__module__):
                result = merge(battle, formatted)
                output = format_text(result["text"])
                self.assertIn("アーク・デアム", output)
                self.assertGreater(output.index("アーク・デアム"), output.index("グレア"))
                self.assertIn("アーク・デアム", result["unresolved"])

    def test_boss_events_are_preserved_and_formal_names_match(self):
        from priconner_tl.merge import merge_texts as package_merge_texts

        for merge in (merge_texts, package_merge_texts):
            with self.subTest(merge=merge.__module__):
                result = merge(
                    "1:10 フロストハウンド\n1:00 ボス\n0:50 敵UB\n",
                    "1:10 ボス　[54321] 注記\n0:55 シオリ\n",
                    ["シオリ"],
                )
                self.assertEqual(result["unresolved"], [])
                self.assertIn("1:10 ボス　[54321] 注記", result["text"])
                self.assertNotIn("フロストハウンド", result["text"])
                self.assertIn("1:00　ボス", result["text"])
                self.assertIn("0:50　敵UB", result["text"])
                self.assertLess(result["text"].index("1:00"), result["text"].index("0:55"))

    def test_arrow_expansion_keeps_each_target_as_independent_event(self):
        events, unresolved = parse_events(
            expand_arrow_times("0:40　すみれ\n　　　→　ティア\n　　　→　シオリ"),
            "b",
            ["すみれ", "ティア", "シオリ"],
        )
        self.assertEqual(unresolved, [])
        self.assertEqual([event.seconds for event in events], [40, 40, 40])
        self.assertEqual([event.name for event in events], ["すみれ", "ティア", "シオリ"])

    def test_same_second_events_are_not_sorted_lexically(self):
        result = merge_texts(
            "0:40 ヴァイオレット\n0:40 ティア\n0:40 シオリ\n0:40 タマキ",
            "0:40 すみれ\n0:40 ティア\n0:40 シオリ\n0:40 タマキ",
            ["すみれ", "ティア", "シオリ", "タマキ"],
        )
        text = result["text"]
        self.assertLess(text.index("すみれ"), text.index("ティア"))
        self.assertLess(text.index("ティア"), text.index("シオリ"))
        self.assertLess(text.index("シオリ"), text.index("タマキ"))
    def test_formal_and_alias_resolve_to_one_canonical_character_name(self):
        events, unresolved = parse_events(
            "0:40 ヴァイオレット\n0:39 すみれ", "a", ["すみれ"]
        )
        assert unresolved == []
        assert [event.name for event in events] == ["すみれ", "すみれ"]
    def test_same_second_formal_alias_keeps_battle_order(self):
        result = merge_texts(
            "00:40 ヴァイオレット\n00:40 ティア\n00:40 シオリ\n00:40 タマキ\n",
            "0:40　すみれ　　[5-3-1]\n　　　→　ティア　　[543-1]\n　　　→　シオリ　　[54321]\n　　　→　タマキ　　[-43--]\n",
            ["すみれ", "ティア", "シオリ", "タマキ"],
        )
        assert [line.split("　", 1)[1].split("　", 1)[0] for line in result["text"].splitlines()] == [
            "すみれ", "ティア", "シオリ", "タマキ"
        ]

    def test_arrows_are_expanded_to_original_time_before_merge(self):
        self.assertEqual(expand_arrow_times("0:40　すみれ\n　　　→　タマキ"), "0:40　すみれ\n0:40　タマキ")
    def test_range_set_line_stays_inside_formatted_block(self):
        result = merge_texts(
            "01:00 シオリ\n",
            "1:00-0:59　''※シオリSET\n[543-1]\n1:00　シオリ\n",
            ["シオリ"],
        )
        self.assertIn("1:00-0:59", result["text"])
        self.assertIn("[543-1]", result["text"])

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

    def test_cli_writes_merge_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a_path, b_path, out_path = root / "a.txt", root / "b.txt", root / "out.json"
            a_path.write_text("01:15 ネラ\n01:08 シェフィ（サマー）\n", encoding="utf-8")
            b_path.write_text("01:15 ネラ\n01:08 ペコリーヌ（ニューイヤー）\n", encoding="utf-8")
            exit_code = main([str(a_path), str(b_path), "--formation", *FORMATION, "-o", str(out_path)])
            self.assertEqual(exit_code, 0)
            result = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(result["summary"], {"common": 1, "only_a": 1, "only_b": 1, "conflicts": 1})
            self.assertEqual(result["unresolved"], {"a": [], "b": []})

    def test_html_spacing_entities_are_decoded(self):
        events, unresolved = parse_events("01:15&#x20;ネラ&#x20;\n", "a", FORMATION)
        self.assertEqual(unresolved, [])
        self.assertEqual(events[0].name, "ネフィ＝ネラ（鬼面仏心）")

    def test_merge_texts_uses_battle_order_and_keeps_formatted_annotations(self):
        battle = "\n".join([
            "01:06 シェフィ（サマー）",
            "01:00 ペコリーヌ（ニューイヤー）",
            "00:55 アオイ（パイロット）",
        ])
        formatted = "\n".join([
            "[5-321]🅰️ON",
            "",
            "　1:06　シェフィ（サマー）　[5-321]",
            "　　→　ネラ＝ネフィ（鬼面仏心）",
            "⭐️1:00-00　:59　※シェフィSET",
            "　0:55　アオイ（パイロット）　[543-1]",
        ])

        result = merge_texts(battle, formatted, FORMATION)
        output = result["text"]

        self.assertEqual(result["unresolved"], ["ネラ＝ネフィ"])
        self.assertLess(output.index("1:06"), output.index("0:55"))
        self.assertIn("[5-321]🅰️ON", output)
        self.assertIn("1:06　ネラ＝ネフィ（鬼面仏心）", output)
        self.assertEqual(output.count("シェフィ（サマー）"), 1)

    def test_merge_texts_retains_battle_only_event_in_timeline_order(self):
        battle = "01:06 シェフィ（サマー）\n01:04 ペコリーヌ（ニューイヤー）"
        formatted = "01:06　シェフィ（サマー）　[5-321]"

        output = merge_texts(battle, formatted, FORMATION)["text"]
        self.assertLess(output.index("1:06"), output.index("1:04"))
        self.assertIn("1:04　ペコリーヌ（ニューイヤー）", output)


if __name__ == "__main__":
    unittest.main()
