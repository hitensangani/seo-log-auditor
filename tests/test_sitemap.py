from __future__ import annotations

from seo_log_auditor.sitemap import _apex, _parse_xml, to_paths


URLSET_NAMESPACED = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.example.com/</loc></url>
  <url><loc>https://www.example.com/products/widget-1</loc></url>
  <url><loc>https://www.example.com/blog/hello</loc></url>
</urlset>
"""

URLSET_NO_NAMESPACE = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset>
  <url><loc>https://example.com/a</loc></url>
  <url><loc>https://example.com/b</loc></url>
</urlset>
"""

SITEMAPINDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>
"""


def test_parse_xml_namespaced_urlset_returns_all_locs():
    """Regression: leaf <loc> elements were silently dropped because
    `find(a) or find(b)` is falsy for elements with no children."""
    tag, locs = _parse_xml(URLSET_NAMESPACED)
    assert tag == "urlset"
    assert len(locs) == 3
    assert locs[0] == "https://www.example.com/"
    assert "https://www.example.com/products/widget-1" in locs


def test_parse_xml_unnamespaced_urlset():
    tag, locs = _parse_xml(URLSET_NO_NAMESPACE)
    assert tag == "urlset"
    assert locs == ["https://example.com/a", "https://example.com/b"]


def test_parse_xml_sitemap_index():
    tag, locs = _parse_xml(SITEMAPINDEX)
    assert tag == "sitemapindex"
    assert locs == [
        "https://example.com/sitemap-1.xml",
        "https://example.com/sitemap-2.xml",
    ]


def test_to_paths_strips_host_and_keeps_query():
    paths = to_paths(
        [
            "https://example.com/foo",
            "https://example.com/bar?x=1",
            "https://example.com/",
        ]
    )
    assert paths == ["/foo", "/bar?x=1", "/"]


def test_to_paths_apex_match_treats_www_as_same():
    paths = to_paths(
        [
            "https://www.example.com/a",
            "https://example.com/b",
            "https://shop.example.com/c",
            "https://other.com/d",
        ],
        base_host="www.example.com",
    )
    assert "/a" in paths
    assert "/b" in paths
    assert "/c" in paths
    assert "/d" not in paths


def test_to_paths_no_filter_when_base_host_none():
    paths = to_paths(
        ["https://anything.com/a", "https://other.org/b"],
        base_host=None,
    )
    assert paths == ["/a", "/b"]


def test_apex_helper():
    assert _apex("www.example.com") == "example.com"
    assert _apex("example.com") == "example.com"
    assert _apex("shop.example.com") == "example.com"
    assert _apex("localhost:8000") == "localhost"
