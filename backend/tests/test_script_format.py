from app.script_format import parse_script, validate_script

SAMPLE = """1-1  夜  外  博物馆门前
出场人物：林修(仅声音)

▲ 地面水洼映出红灯笼的倒影。
【字幕：第九号私人博物馆】
林修(vo)：我叫林修。

1-2  夜  内  博物馆大殿
出场人物：林修

▲ 殿内陈列着青铜器。
林修(惊诧)：哎，你怎么烧了？
"""

def test_parse_scenes():
    s = parse_script(SAMPLE)
    assert s.episode == 1
    assert len(s.scenes) == 2
    assert s.scenes[0].number == 1
    assert s.scenes[0].time == "夜"
    assert s.scenes[0].place_type == "外"
    assert s.scenes[0].location == "博物馆门前"
    assert "林修(vo)：我叫林修。" in s.scenes[0].lines

def test_validate_ok():
    assert validate_script(SAMPLE, expected_episode=1) == []

def test_validate_wrong_episode():
    errs = validate_script(SAMPLE, expected_episode=2)
    assert any("集数" in e for e in errs)

def test_validate_scene_gap():
    bad = SAMPLE.replace("1-2", "1-3")
    errs = validate_script(bad, expected_episode=1)
    assert any("场号" in e for e in errs)

def test_validate_no_scene():
    errs = validate_script("随便一段文字，没有场次头", expected_episode=1)
    assert any("场次" in e for e in errs)
