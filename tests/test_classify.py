from __future__ import annotations

import pandas as pd

from seo_log_auditor.classify import add_page_type, default_classifier, load_classifier


YAML = """
patterns:
  - name: product
    match: "^/products/[^/?]+/?$"
  - name: paginated
    match: "[?&]page="
  - name: blog
    match: "^/blog/"
default: other
"""


def test_load_classifier_yaml():
    c = load_classifier(YAML)
    assert c.classify("/products/widget") == "product"
    assert c.classify("/category/widgets?page=2") == "paginated"
    assert c.classify("/blog/foo") == "blog"
    assert c.classify("/random") == "other"


def test_first_match_wins():
    # /products/widget?page=2 should hit product first, not paginated, because
    # product pattern is listed first... actually the regex needs ^/products/[^/?]+/?$,
    # which excludes the query. So this URL falls through to paginated.
    c = load_classifier(YAML)
    assert c.classify("/products/widget?page=2") == "paginated"


def test_default_classifier_handles_static_assets():
    c = default_classifier()
    assert c.classify("/static/app.js") == "static_asset"
    assert c.classify("/img/foo.PNG") == "static_asset"
    assert c.classify("/page?utm_source=x") == "session_param"


def test_add_page_type_adds_column():
    df = pd.DataFrame({"full_url": ["/products/a", "/blog/b", "/x"]})
    c = load_classifier(YAML)
    out = add_page_type(df, c)
    assert list(out["page_type"]) == ["product", "blog", "other"]


def test_invalid_regex_raises():
    bad = """
patterns:
  - name: bad
    match: "([unclosed"
"""
    try:
        load_classifier(bad)
    except ValueError:
        return
    raise AssertionError("expected ValueError")
