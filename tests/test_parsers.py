from __future__ import annotations

from pathlib import Path

import pandas as pd

from seo_log_auditor.parsers import (
    parse_csv,
    parse_log_file,
    parse_loki_json,
    parse_nginx_line,
    parse_text,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_loki.json"


def test_parse_nginx_line_basic():
    line = (
        '66.249.66.1 - - [04/May/2026:09:30:00 +0000] "GET /products/x HTTP/1.1" '
        '200 12345 "-" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" '
        '542 0.123'
    )
    parsed = parse_nginx_line(line)
    assert parsed is not None
    assert parsed.ip == "66.249.66.1"
    assert parsed.method == "GET"
    assert parsed.path == "/products/x"
    assert parsed.query == ""
    assert parsed.status == 200
    assert parsed.bytes_ == 12345
    assert parsed.latency_ms == 123.0


def test_parse_nginx_line_with_query():
    line = (
        '1.2.3.4 - - [04/May/2026:09:30:00 +0000] "GET /search?q=foo&p=1 HTTP/1.1" '
        '200 999 "-" "bot"'
    )
    parsed = parse_nginx_line(line)
    assert parsed is not None
    assert parsed.path == "/search"
    assert parsed.query == "q=foo&p=1"
    assert parsed.referer == ""  # "-" treated as empty


def test_parse_nginx_line_captures_referer():
    line = (
        '1.2.3.4 - - [04/May/2026:09:30:00 +0000] "GET /broken HTTP/1.1" '
        '404 200 "https://example.com/blog/post-with-broken-link" "Mozilla/5.0"'
    )
    parsed = parse_nginx_line(line)
    assert parsed is not None
    assert parsed.referer == "https://example.com/blog/post-with-broken-link"


def test_parse_nginx_line_returns_none_on_garbage():
    assert parse_nginx_line("not a log line") is None


def test_parse_loki_json_fixture():
    df = parse_loki_json(FIXTURE.read_text())
    assert len(df) == 6
    # Schema sanity
    for col in ("timestamp", "ip", "path", "status", "bytes", "user_agent", "referer", "claimed_bot", "has_params"):
        assert col in df.columns
    # All rows are claimed Googlebot
    assert (df["claimed_bot"] == "Googlebot").all()
    # has_params correctly flagged
    assert df["has_params"].sum() == 3
    # Sorted by timestamp
    assert df["timestamp"].is_monotonic_increasing


def test_parse_log_file_dispatch_json():
    df = parse_log_file("export.json", FIXTURE.read_bytes())
    assert len(df) == 6


def test_parse_log_file_dispatch_text():
    text = (
        '66.249.66.1 - - [04/May/2026:09:30:00 +0000] "GET /a HTTP/1.1" 200 100 "-" "Googlebot/2.1"\n'
        '66.249.66.2 - - [04/May/2026:09:31:00 +0000] "GET /b HTTP/1.1" 200 100 "-" "Googlebot/2.1"\n'
    )
    df = parse_log_file("logs.txt", text)
    assert len(df) == 2


def test_parse_csv_with_line_column():
    csv = (
        "Time,Line\n"
        '"2026-05-04T09:30:00Z","66.249.66.1 - - [04/May/2026:09:30:00 +0000] \\"GET /a HTTP/1.1\\" 200 100 \\"-\\" \\"Googlebot/2.1\\""\n'
    )
    # The escaping above is tricky in CSV; build it programmatically instead.
    df_text = pd.DataFrame(
        {
            "Time": ["2026-05-04T09:30:00Z"],
            "Line": [
                '66.249.66.1 - - [04/May/2026:09:30:00 +0000] "GET /a HTTP/1.1" 200 100 "-" "Googlebot/2.1"'
            ],
        }
    ).to_csv(index=False)
    df = parse_csv(df_text)
    assert len(df) == 1
    assert df.iloc[0]["path"] == "/a"


def test_returns_empty_with_no_valid_rows():
    df = parse_text("nothing here matters\nstill garbage\n")
    assert df.empty
    # Schema columns still present
    for col in ("timestamp", "ip", "path", "status"):
        assert col in df.columns
