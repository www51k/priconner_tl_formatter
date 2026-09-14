import unittest

from priconner_tl import add_operations, format_text


class PackageApiTests(unittest.TestCase):
    def test_public_formatter_api(self):
        self.assertEqual(format_text("1:6　アオイ\n"), "1:06　アオイ\n")

    def test_public_set_operation_api_uses_packaged_rules(self):
        result = add_operations(format_text("1:00　アオイ\n"))
        self.assertIsInstance(result, str)
        self.assertIn("1:00", result)


if __name__ == "__main__":
    unittest.main()
