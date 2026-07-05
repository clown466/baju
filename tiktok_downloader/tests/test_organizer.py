import pytest
from organizer import clean_series, parse_input, series_covers, VideoItem, plan_downloads


def test_series_covers_earliest_episode_wins():
    items = [
        VideoItem("2", 200, "Show A #fyp", "http://c/2.jpg"),
        VideoItem("1", 100, "Show A #tag", "http://c/1.jpg"),
        VideoItem("3", 300, "Show B", ""),  # 无封面 → 不出现
    ]
    assert series_covers(items) == {"Show A": "http://c/1.jpg"}


def test_clean_series_strips_hashtags():
    assert clean_series("Frost Oath #fyp #anime") == "Frost Oath"

def test_clean_series_replaces_illegal_chars():
    assert clean_series('Blood: Rise? "Kiwi"') == "Blood_ Rise_ _Kiwi_"

def test_clean_series_empty_becomes_unclassified():
    assert clean_series("") == "未分类"
    assert clean_series("#onlytags #fyp") == "未分类"

def test_clean_series_truncates_to_80():
    assert len(clean_series("x" * 200)) == 80

def test_clean_series_collapses_whitespace_and_trims_dots():
    assert clean_series("  A   B .") == "A B"

def test_parse_input_handle():
    assert parse_input("@somebody") == ("user", "https://www.tiktok.com/@somebody")

def test_parse_input_profile_url():
    assert parse_input("https://www.tiktok.com/@abc_1?lang=en") == ("user", "https://www.tiktok.com/@abc_1")

def test_parse_input_video_url():
    kind, url = parse_input("https://www.tiktok.com/@abc/video/123456?is_copy=1")
    assert kind == "video" and url == "https://www.tiktok.com/@abc/video/123456"

def test_parse_input_invalid_raises():
    with pytest.raises(ValueError):
        parse_input("https://example.com/foo")


def test_plan_downloads_groups_and_numbers_by_time():
    items = [
        VideoItem("b", 200, "Show A #fyp"),
        VideoItem("a", 100, "Show A"),
        VideoItem("c", 300, "Show B"),
    ]
    plan = plan_downloads(items)
    a = plan["Show A"]
    assert [t.video_id for t in a] == ["a", "b"]
    assert a[0].filename == "第01集.mp4"
    assert a[1].filename == "第02集.mp4"
    assert plan["Show B"][0].filename == "第01集.mp4"

def test_plan_downloads_three_digits_for_100_plus():
    items = [VideoItem(str(i), i, "Long") for i in range(100)]
    plan = plan_downloads(items)
    assert plan["Long"][0].filename == "第001集.mp4"
    assert plan["Long"][99].filename == "第100集.mp4"
