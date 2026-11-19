"""Parsing a pasted or imported list of links."""

from youmudow.domain.url_batch import parse_url_list


def test_parses_one_url_per_line():
    text = "https://youtube.com/watch?v=a\nhttps://youtube.com/watch?v=b\n"
    assert parse_url_list(text) == [
        "https://youtube.com/watch?v=a",
        "https://youtube.com/watch?v=b",
    ]


def test_ignores_blank_lines_and_comments():
    text = "\n# my list\n\nhttps://youtube.com/watch?v=a\n\n"
    assert parse_url_list(text) == ["https://youtube.com/watch?v=a"]


def test_accepts_csv_rows_taking_the_first_column():
    text = "https://youtube.com/watch?v=a,Some title\nhttps://youtube.com/watch?v=b,Other"
    assert parse_url_list(text) == [
        "https://youtube.com/watch?v=a",
        "https://youtube.com/watch?v=b",
    ]


def test_drops_duplicates_and_unsupported_entries():
    text = (
        "https://youtube.com/watch?v=a\n"
        "not a link\n"
        "https://youtube.com/watch?v=a\n"
        "https://soundcloud.com/artist/track"
    )
    assert parse_url_list(text) == [
        "https://youtube.com/watch?v=a",
        "https://soundcloud.com/artist/track",
    ]


def test_returns_the_url_alone_when_it_has_no_commas():
    assert parse_url_list("https://youtube.com/playlist?list=PL1") == [
        "https://youtube.com/playlist?list=PL1"
    ]
