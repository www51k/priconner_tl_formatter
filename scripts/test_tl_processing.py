#!/usr/bin/env python3
"""TL整形・SET追加の代表ケースを確認する軽量テスト。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from add_set_operations import add_operations  # noqa: E402
from format_tl import format_text  # noqa: E402
from validate_tl import validate  # noqa: E402
from review_tl import collect_review_items  # noqa: E402


class TlProcessingTests(unittest.TestCase):
    reference_source = ROOT / "202608_1b58000_16.org"
    reference_output = ROOT / "202608_1b58000_16.txt"

    @unittest.skipUnless(
        reference_source.exists() and reference_output.exists(),
        "ローカルTL fixtureがある場合だけ実行する",
    )
    def test_reference_tl_is_reproducible(self) -> None:
        source = self.reference_source.read_text(encoding="utf-8")
        actual = add_operations(format_text(source))
        self.assertIn("\n[-----]🅰️OFF\n", actual)

    @unittest.skipUnless(
        reference_output.exists(),
        "ローカルTL fixtureがある場合だけ実行する",
    )
    def test_ideal_output_is_stable_when_formatted_again(self) -> None:
        source = self.reference_output.read_text(encoding="utf-8")
        formatted = format_text(source)
        self.assertEqual(format_text(formatted), formatted)
        self.assertEqual(add_operations(formatted), formatted)

    @unittest.skipUnless(
        reference_output.exists(),
        "ローカルTL fixtureがある場合だけ実行する",
    )
    def test_reference_tl_passes_validation(self) -> None:
        text = self.reference_output.read_text(encoding="utf-8")
        self.assertEqual(validate(text), [])

    @unittest.skipUnless(
        reference_source.exists(),
        "ローカルTL fixtureがある場合だけ実行する",
    )
    def test_report_contains_operation_categories(self) -> None:
        source = self.reference_source.read_text(encoding="utf-8")
        report: list[str] = []
        add_operations(format_text(source), report=report)
        report_text = "\n".join(report)
        self.assertIn("ADD", report_text)
        self.assertIn("REMOVE", report_text)
        self.assertIn("矢印連鎖", report_text)

    def test_review_queue_ignores_boss_and_comments(self) -> None:
        text = (
            "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n\n"
            "[5----]🅰️OFF\n"
            "0:10　アオイ　//最速・微ディレイ・欠損\n"
            "0:09　ボス\n"
        )
        items = collect_review_items(text)
        self.assertEqual(items, [])

    def test_review_queue_finds_original_set_and_auto(self) -> None:
        text = (
            "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n\n"
            "[5----]🅰️OFF\n"
            "0:10　アオイ　[5---1]🅰️ON\n"
        )
        kinds = {item["kind"] for item in collect_review_items(text, text)}
        self.assertEqual(kinds, set())

    def test_review_queue_finds_added_auto_on(self) -> None:
        source = ""
        formatted = "🅰️ON\n"
        kinds = {item["kind"] for item in collect_review_items(formatted, source)}
        self.assertEqual(kinds, {"AUTO_ON"})

    def test_structural_preprocessing_preserves_comments(self) -> None:
        text = (
            "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n"
            "53 アオイ AUTO ON // 1:04-03 【保持】\n"
        )
        formatted = format_text(text)
        self.assertIn("0:53　アオイ", formatted)
        self.assertIn("🅰️ON", formatted)
        self.assertIn("// 1:04-03 【保持】", formatted)

    def test_bare_auto_state_after_mask_is_normalized(self) -> None:
        text = (
            "[(5)サレン|(4)アネモネ|(3)プレシア|(2)リリア|(1)クリア]\n"
            "1:20　クリア　ピアースcl早め　[〇〇✕〇✕]on\n"
            "1:18　プレシア（オート）　[✕〇✕✕✕]off\n"
        )
        formatted = format_text(text)
        self.assertIn("[54-2-]🅰️ON　ピアースcl早め", formatted)
        self.assertIn("[-4---]🅰️OFF　（オート）", formatted)
        self.assertNotIn("]on", formatted)
        self.assertNotIn("]off", formatted)

    def test_single_quote_between_set_and_auto_is_removed(self) -> None:
        self.assertEqual(
            format_text("1:30　バトル開始　[54---]'🅰️OFF\n"),
            "[54---]🅰️OFF\n",
        )

    def test_single_quote_used_for_auto_is_not_left_after_conversion(self) -> None:
        self.assertEqual(
            format_text("1:11 ペコリーヌ　'オートOFF\n"),
            "1:11　ペコ　　　🅰️OFF\n",
        )

    def test_double_quote_comment_is_preserved(self) -> None:
        self.assertEqual(
            format_text("0:10　アオイ　''手動確認\n"),
            "0:10　アオイ　　''手動確認\n",
        )

    def test_all_set_and_all_release_become_masks(self) -> None:
        self.assertEqual(
            format_text("1:03　クリア　　全set\n1:02　クリア　全解除\n"),
            "1:03　クリア　　[54321]\n1:02　クリア　　[-----]\n",
        )

    def test_all_set_words_inside_comments_are_preserved(self) -> None:
        text = "1:03　クリア　''全set 全解除\n1:02　クリア　// 全set 全解除\n"
        self.assertEqual(
            format_text(text),
            "1:03　クリア　　''全set 全解除\n1:02　クリア　　// 全set 全解除\n",
        )

    def test_start_line_places_set_and_auto_at_the_top(self) -> None:
        self.assertEqual(
            format_text('1:30　開始　　　[54--1]　"🅰️OFF\n'),
            "[54--1]🅰️OFF\n",
        )

    def test_auto_note_is_separated_from_character_name(self) -> None:
        self.assertEqual(
            format_text("0:04　アネモネ（オート）\n"),
            "0:04　アネモネ　（オート）\n",
        )

    def test_arrow_row_columns_are_aligned(self) -> None:
        text = "1:21　モネ　　　[543-1]\n　　　→　アカリ　　[54--1]\n"
        self.assertEqual(
            format_text(text),
            "1:21　モネ　　　[543-1]\n　　→　アカリ　　[54--1]\n",
        )

    def test_star_following_arrow_keeps_three_space_indent(self) -> None:
        self.assertEqual(
            format_text("⭐️1:20　クリア\n　　　→　レイ\n"),
            "⭐️1:20　クリア\n　　　→　レイ\n",
        )

    def test_non_star_time_is_indented_when_same_bucket_has_manual_ub(self) -> None:
        text = (
            "0:09　ネネカ　　[54321]　➡　クルル後✕OOO✕\n"
            "⭐️0:06　アメス　　ルーチェcl（マホ暗転明け,遅いと1sクルル打てない)\n"
        )
        formatted = format_text(text)
        self.assertIn("　0:09　ネネカ", formatted)
        self.assertIn("クルル後[-432-]", formatted)

    def test_inline_character_arrow_becomes_following_arrow_line(self) -> None:
        self.assertEqual(
            format_text("0:47 シナツ→クリア\n"),
            "0:47　シナツ\n　　→　クリア\n",
        )

    def test_auto_after_inline_arrow_is_not_assigned_to_previous_character(self) -> None:
        formatted = format_text("1:01　マホ　〇〇〇〇〇　➡　クルル後〇✕〇✕✕**オートon**\n")
        self.assertNotIn("🅰️ON", formatted)
        self.assertIn("オートon", formatted)
        self.assertNotIn("**オートon**", formatted)

    def test_bold_auto_decoration_is_removed_but_sentence_is_preserved(self) -> None:
        self.assertEqual(
            format_text("1:01　マホ　**オートon**\n"),
            "1:01　マホ　　　🅰️ON\n",
        )
        sentence = "1:01　マホ　''ここは**オートonの方が良いかも**\n"
        self.assertEqual(
            format_text(sentence),
            "1:01　マホ　　　''ここは**オートonの方が良いかも**\n",
        )

    def test_damage_memo_is_not_treated_as_formation_mask(self) -> None:
        formatted = format_text(
            "0:09　ネネカ　[1000]\n"
            "0:08　アメス　(1000)\n"
            "0:07　マホ　1000\n"
            "0:06　ネネカ　クルル後〇✕〇✕✕\n"
        )
        self.assertIn("ネネカ　　[1000]", formatted)
        self.assertIn("アメス　　(1000)", formatted)
        self.assertIn("マホ　　　1000", formatted)

    def test_learning_style_names_work_without_formation_header(self) -> None:
        formatted = format_text(
            "1:30　クローチェ　〇〇〇〇〇\n"
            "1:20　ペコリーヌ　〇〇〇〇〇\n"
        )
        self.assertIn("1:30　クロ　　　[54321]", formatted)
        self.assertIn("1:20　ペコ　　　[54321]", formatted)

    def test_learning_style_time_and_name_without_separator(self) -> None:
        formatted = format_text("1:16サレン通常戻り目安\n0:17フィオ\n1:02★ペコの通常開始見てオートON\n")
        self.assertIn("1:16　サレン", formatted)
        self.assertIn("0:17　フィオ", formatted)
        self.assertIn("⭐️1:02　ペコ", formatted)

    def test_formation_symbols_convert_to_fixed_mask(self) -> None:
        text = "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n"
        text += "0:10　アオイ　OXOXO\n0:09　アオイ　O-O-O\n"
        formatted = format_text(text)
        self.assertIn("[5-3-1]", formatted)
        self.assertEqual(formatted.count("[5-3-1]"), 2)

    def test_multiple_formation_symbol_styles_convert_to_fixed_mask(self) -> None:
        for pattern in ("〇－〇－〇", "0-0-0", "OXOXO", "⭕️❌⭕️❌⭕️"):
            with self.subTest(pattern=pattern):
                self.assertEqual(format_text(pattern + "\n"), "[5-3-1]\n")

    def test_parenthesized_formation_symbols_do_not_leave_parentheses(self) -> None:
        formatted = format_text("0:14　ティア　(〇〇〇〇〇)\n")
        self.assertEqual(formatted, "0:14　ティア　　[54321]\n")

    def test_unregistered_characters_and_untimed_lines_are_formatted(self) -> None:
        text = (
            "【〇－〇〇〇】\"オートオフ\"\n"
            "1:16　ユニ　【－〇〇〇〇】\n"
            "　　　ルルィ　【〇〇－〇〇】\n"
        )
        formatted = format_text(text)
        self.assertIn("[5-321]", formatted)
        self.assertIn("1:16　ユニ", formatted)
        self.assertIn("ルルィ", formatted)
        self.assertIn("[54-21]", formatted)

    def test_battle_start_mask_is_not_replaced_by_empty_set(self) -> None:
        text = (
            "1:30　バトル開始　[54---]\"AUTO\"🅰️ON\n"
            "1:16　ユニ　[-4321]\n"
        )
        result = add_operations(format_text(text))
        self.assertTrue(result.startswith("[54---]🅰️ON\n"))
        self.assertNotIn("[-----]", result)

    def test_start_label_is_not_treated_as_character(self) -> None:
        text = "1:30　開始時　〇－〇〇〇　オートOFF\n1:18　アオイ　〇－〇－〇\n"
        result = add_operations(format_text(text))
        self.assertTrue(result.startswith("[5-321]🅰️OFF\n"))

    def test_auto_off_is_inserted_at_the_top(self) -> None:
        result = add_operations("⭐️0:10　アオイ\n")
        self.assertTrue(result.startswith("[-----]🅰️OFF\n\n"))

    def test_formation_header_precedes_auto_off(self) -> None:
        text = "[(5)ユキノ|(4)ティア|(3)ミソラ|(2)ソノ|(1)イサナミ]\n⭐️0:10　ユキノ\n"
        result = add_operations(format_text(text))
        self.assertTrue(result.startswith("[(5)ユキノ|(4)ティア|(3)ミソラ|(2)ソノ|(1)イサナミ]\n\n[-----]🅰️OFF"))

    def test_formation_header_maps_unregistered_characters(self) -> None:
        text = (
            "[(5)ユニ|(4)スミレ|(3)グレイス|(2)ルルィ|(1)シオリ]\n"
            "⭐️1:16　ユニ\n"
            "1:01　スミレ\n"
        )
        result = add_operations(format_text(text))
        self.assertIn("[-4---]", result)

    def test_untimed_following_events_are_rendered_as_arrows(self) -> None:
        text = (
            "0:49　スミレ　【〇－－〇〇】\n"
            "　　　ルルィ　【〇〇－〇〇】\n"
            "　　　シオリ　【〇〇〇〇〇】\n"
        )
        formatted = format_text(text)
        self.assertIn("0:49　スミレ", formatted)
        self.assertIn("→　ルルィ", formatted)
        self.assertIn("→　シオリ", formatted)

    def test_same_second_events_are_rendered_as_arrows(self) -> None:
        text = "0:49　スミレ\n0:49　ルルィ\n0:49　シオリ\n"
        formatted = format_text(text)
        self.assertEqual(formatted.count("→"), 2)

    def test_validation_uses_character_numbers_from_formation_header(self) -> None:
        text = (
            "[(5)フブキ|(4)シェフィ|(3)アオイ|(2)ペコ|(1)ネラ]\n"
            "[--321]\n"
            "⭐️0:55　シェフィ\n"
        )
        self.assertEqual(validate(text), [])

    def test_original_mask_makes_unstarred_auto_line_valid(self) -> None:
        text = (
            "[(5)フブキ|(4)スミレ|(3)アオイ|(2)ペコ|(1)ネラ]\n"
            "[----4]\n"
            "0:18　スミレ　[54321]\n"
        )
        self.assertEqual(validate(text), [])

    def test_japanese_auto_labels_are_normalized(self) -> None:
        formatted = format_text('【〇〇－－－】"オートオフ"\n')
        self.assertEqual(formatted, '[54---]🅰️OFF\n')
        self.assertEqual(format_text('【〇〇－－－】オートオフ\n'), '[54---]🅰️OFF\n')
        self.assertEqual(format_text('【〇〇－－－】 "オートオフ"\n'), '[54---]🅰️OFF\n')
        self.assertEqual(format_text('[5-321]　“🅰️OFF”\n'), '[5-321]🅰️OFF\n')
        self.assertEqual(format_text('[5-321]　🅰️OFF\n'), '[5-321]🅰️OFF\n')

    def test_formation_header_resolves_long_names_and_fullwidth_notes(self) -> None:
        text = (
            "[(5)ヴァイオレット|(4)ネフィ＝ネラ|(3)クルル|(2)ニュリノ|(1)水マホ]\n"
            "1:10　クルル（オート）　ニュリノSET\n"
            "　　⇒ニュリノ　クルル・ニュリノ解除　オートoff\n"
        )
        formatted = format_text(text)
        self.assertIn("1:10　クルル", formatted)
        self.assertIn("→　ニュリノ", formatted)
        self.assertIn("🅰️OFF", formatted)

    def test_arrow_variants_are_normalized(self) -> None:
        self.assertEqual(format_text("⇒ユニ\n"), "　　→　ユニ\n")

    def test_same_second_manual_ub_is_not_converted_to_arrow(self) -> None:
        text = (
            "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n"
            "0:57　ペコ\n"
            "⭐️0:57-56　シェフィ　''汐沓cl最速\n"
        )
        formatted = format_text(text)
        self.assertIn("⭐️0:57-56　シェフィ", formatted)
        self.assertNotIn("→　シェフィ", formatted)

    def test_inserts_one_blank_line_at_ten_second_boundaries(self) -> None:
        text = "0:21　アオイ\n0:20　ペコ\n0:19　ツムギ\n0:10　ネラ\n0:09　シェフィ\n"
        formatted = format_text(text)
        self.assertEqual(
            formatted,
            "0:21　アオイ\n0:20　ペコ\n\n0:19　ツムギ\n0:10　ネラ\n\n"
            "0:09　シェフィ\n",
        )

    def test_preserves_mask_content_but_moves_manual_mask_to_next_line(self) -> None:
        text = (
            "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n"
            "⭐️0:20　アオイ　[5-3--]\n"
            "0:19　ツムギ　[5-3--]\n"
        )
        self.assertEqual(
            format_text(text),
            "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n"
            "⭐️0:20　アオイ\n[5-3--]\n"
            "\n0:19　ツムギ　　[5-3--]\n",
        )

    def test_spreadsheet_formal_names_render_as_abbreviations(self) -> None:
        text = "[(5)ペコリーヌ|(4)ラビリスタ|(3)ヴァイオレット|(2)ハツネ＆シオリ|(1)ミソギ＆ミミ＆キョウカ]\n"
        text += "0:10　ペコリーヌ\n0:09　ラビリスタ\n0:08　ヴァイオレット\n"
        text += "0:07　ハツネ＆シオリ\n0:06　ミソギ＆ミミ＆キョウカ\n"
        formatted = format_text(text)
        self.assertIn("0:10　ペコ\n", formatted)
        self.assertIn("0:09　ラビ\n", formatted)
        self.assertIn("0:08　すみれ", formatted)
        self.assertIn("0:07　ハツシオ", formatted)
        self.assertIn("0:06　リトリリ", formatted)


if __name__ == "__main__":
    unittest.main()
