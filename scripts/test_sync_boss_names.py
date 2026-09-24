from sync_boss_names import build_boss_names


def test_build_boss_names_reads_all_columns():
    assert build_boss_names("boss1,boss2,boss3\nA,B,A\n") == ["A", "B"]


def test_build_boss_names_reads_priconne_tl_new_boss_name_sheet():
    assert build_boss_names("ボス名\nフロストハウンド\nグラットン\n") == ["フロストハウンド", "グラットン"]


def test_build_boss_names_reads_upstream_csv_with_added_columns():
    csv_text = (
        "id,name,name_en,hp,release,aliases\n"
        '1,フロストハウンド,Frost Hound,2080000000,202609,"[フロストハウンド]"\n'
        '2,ランドスロース,Land Sloth,2120000000,202609,"[ランドスロース]"\n'
    )
    assert build_boss_names(csv_text) == ["フロストハウンド", "ランドスロース"]


def test_build_boss_names_uses_name_column_after_reordering():
    assert build_boss_names("release,aliases,name,id\n202609,[],グラットン,1\n") == ["グラットン"]
