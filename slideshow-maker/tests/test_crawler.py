from slideshow_machine.crawler import parse_count


def test_parse_count_suffixes():
    assert parse_count("1.2K") == 1200
    assert parse_count("3.5M") == 3500000
    assert parse_count("999") == 999
    assert parse_count("12,345") == 12345
