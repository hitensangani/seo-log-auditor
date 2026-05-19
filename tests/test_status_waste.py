from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from seo_log_auditor.analysis.status_waste import four_oh_four_forensics


def _df(rows: list[dict]) -> pd.DataFrame:
    base = pd.DataFrame(rows)
    if "timestamp" not in base.columns:
        base["timestamp"] = pd.Timestamp("2026-05-04T10:00:00", tz="UTC")
    if "referer" not in base.columns:
        base["referer"] = ""
    return base


def test_forensics_aggregates_referers_and_sitemap_membership():
    rows = [
        {"path": "/old-page", "status": 404, "referer": "https://example.com/blog/a"},
        {"path": "/old-page", "status": 404, "referer": "https://example.com/blog/a"},
        {"path": "/old-page", "status": 404, "referer": "https://twitter.com/x"},
        {"path": "/sitemap-typo", "status": 404, "referer": ""},
        {"path": "/sitemap-typo", "status": 404, "referer": ""},
        {"path": "/healthy", "status": 200, "referer": ""},
    ]
    df = _df(rows)
    out = four_oh_four_forensics(df, sitemap_paths=["/sitemap-typo", "/keep"])
    assert list(out["path"]) == ["/old-page", "/sitemap-typo"]
    old = out.iloc[0]
    assert old["hits"] == 3
    assert old["top_referer"] == "https://example.com/blog/a"
    assert old["referer_hits"] == 2
    assert old["distinct_referers"] == 2
    assert old["in_sitemap"] is False or old["in_sitemap"] == False  # noqa: E712
    typo = out.iloc[1]
    assert typo["in_sitemap"] is True or typo["in_sitemap"] == True  # noqa: E712
    assert typo["referer_hits"] == 0
    assert typo["top_referer"] == ""


def test_forensics_filters_by_status_class():
    df = _df([
        {"path": "/a", "status": 301},
        {"path": "/b", "status": 404},
        {"path": "/c", "status": 500},
    ])
    out_4xx = four_oh_four_forensics(df, status_classes=("4xx",))
    assert list(out_4xx["path"]) == ["/b"]
    out_3_5 = four_oh_four_forensics(df, status_classes=("3xx", "5xx"))
    assert set(out_3_5["path"]) == {"/a", "/c"}


def test_forensics_handles_missing_referer_column():
    """Older parsed DFs (before the referer change) shouldn't crash."""
    df = pd.DataFrame({
        "path": ["/a", "/a"],
        "status": [404, 404],
        "timestamp": pd.Timestamp("2026-05-04T10:00:00", tz="UTC"),
    })
    out = four_oh_four_forensics(df)
    assert len(out) == 1
    assert out.iloc[0]["referer_hits"] == 0
