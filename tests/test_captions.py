from tiktok_publisher.captions import pick_random_caption, split_caption_variants


def test_split_delimiter():
    raw = "a|||b|||c"
    assert split_caption_variants(raw) == ["a", "b", "c"]


def test_split_newlines():
    raw = "line1\nline2"
    assert split_caption_variants(raw) == ["line1", "line2"]


def test_pick_random():
    v = ["x", "y"]
    assert pick_random_caption(v) in v
