import pytest
from organizer import clean_series, parse_input


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
