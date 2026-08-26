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
        expected = self.reference_output.read_text(encoding="utf-8")
        actual = add_operations(format_text(source))
        self.assertEqual(actual, expected)

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
        self.assertEqual(kinds, {"ORIGINAL_SET", "AUTO_ON"})

    def test_structural_preprocessing_preserves_comments(self) -> None:
        text = (
            "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n"
            "53 アオイ AUTO ON // 1:04-03 【保持】\n"
        )
        formatted = format_text(text)
        self.assertIn("0:53　アオイ", formatted)
        self.assertIn("🅰️ON", formatted)
        self.assertIn("// 1:04-03 【保持】", formatted)

    def test_formation_symbols_convert_to_fixed_mask(self) -> None:
        text = "[(5)アオイ|(4)ネラ|(3)ツムギ|(2)ペコ|(1)シェフィ]\n"
        text += "0:10　アオイ　OXOXO\n0:09　アオイ　O-O-O\n"
        formatted = format_text(text)
        self.assertIn("[5-3-1]", formatted)
        self.assertEqual(formatted.count("[5-3-1]"), 2)

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


if __name__ == "__main__":
    unittest.main()
