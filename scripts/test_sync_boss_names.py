from sync_boss_names import build_boss_names


def test_build_boss_names_reads_all_columns():
    assert build_boss_names("boss1,boss2,boss3\nA,B,A\n") == ["A", "B"]
