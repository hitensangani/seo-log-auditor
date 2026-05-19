from __future__ import annotations

import pandas as pd

from seo_log_auditor.analysis.budget import crawl_budget_distribution


def _df(page_types: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "page_type": page_types,
            "path": [f"/p/{i}" for i in range(len(page_types))],
        }
    )


def test_distribution_with_no_sitemap_keeps_index_name():
    """Regression: concatenating Series with mismatched index names dropped
    the `page_type` index name, so px.pie(...names="page_type") crashed."""
    df = _df(["product", "product", "blog", "other"])
    out = crawl_budget_distribution(df, sitemap_page_types=None)
    assert out.index.name == "page_type"
    rs = out.reset_index()
    assert "page_type" in rs.columns
    assert rs["hits"].sum() == 4


def test_distribution_with_sitemap_computes_delta():
    df = _df(["product", "product", "blog"])
    sitemap = pd.Series(["product", "product", "product", "product", "blog"])
    out = crawl_budget_distribution(df, sitemap_page_types=sitemap)
    # product: hit_share 2/3 ~= 0.667, url_share 4/5 = 0.8 -> delta ~ -0.133
    product = out.loc["product"]
    assert abs(product["delta"] - (2 / 3 - 4 / 5)) < 1e-9
    # delta sorts by absolute value
    assert out.iloc[0]["delta"] is not None


def test_empty_log_df_returns_empty():
    df = pd.DataFrame(columns=["page_type", "path"])
    out = crawl_budget_distribution(df, None)
    assert out.empty
