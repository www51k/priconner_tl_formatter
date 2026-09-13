from sync_character_aliases import build_aliases


def test_build_aliases_uses_sheet_name_and_short_name():
    payload = build_aliases("キャラID,名称,略称\n1,ヴァイオレット,すみれ\n2,ユイ,ユイ\n")
    assert payload == {
        "character_aliases": {"ヴァイオレット": "すみれ"},
        "learned_name_aliases": {"スミレ": "すみれ"},
    }
