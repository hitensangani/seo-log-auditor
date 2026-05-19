"""Technique 1: crawl budget distribution.

Compares two distributions side-by-side:

* **Hit share**: % of total Googlebot hits that landed on each page_type.
* **URL share**: % of canonical URLs (from the sitemap) that belong to each
  page_type.

A large positive ``delta`` (hit_share - url_share) means a page type is
disproportionately consuming crawl budget. Negative deltas point at neglected
page types.
"""

from __future__ import annotations

import pandas as pd


def crawl_budget_distribution(
    log_df: pd.DataFrame,
    sitemap_page_types: pd.Series | None = None,
) -> pd.DataFrame:
    """Return a DataFrame indexed by ``page_type`` with hit/url shares + delta.

    Columns: ``hits, hit_share, sitemap_urls, url_share, delta``.
    Sorted by absolute delta descending so the worst leaks are on top.
    """
    if log_df.empty:
        return pd.DataFrame(
            columns=["hits", "hit_share", "sitemap_urls", "url_share", "delta"]
        )

    hits = log_df.groupby("page_type").size().rename("hits")
    hit_share = (hits / hits.sum()).rename("hit_share")

    if sitemap_page_types is not None and not sitemap_page_types.empty:
        urls = sitemap_page_types.value_counts().rename("sitemap_urls")
        url_share = (urls / urls.sum()).rename("url_share")
    else:
        urls = pd.Series(dtype="Int64", name="sitemap_urls")
        url_share = pd.Series(dtype="float64", name="url_share")

    out = pd.concat([hits, hit_share, urls, url_share], axis=1).fillna(
        {"hits": 0, "hit_share": 0.0, "sitemap_urls": 0, "url_share": 0.0}
    )
    # Concatenating Series whose indexes have differing names (e.g. when no
    # sitemap is loaded) drops the index name. Restore it so reset_index()
    # downstream produces a proper `page_type` column.
    out.index.name = "page_type"
    out["delta"] = out["hit_share"] - out["url_share"]
    out = out.sort_values("delta", key=lambda s: s.abs(), ascending=False)
    return out


def hits_over_time(
    log_df: pd.DataFrame, freq: str = "1h"
) -> pd.DataFrame:
    """Time-bucketed hit counts per page_type for the trend chart."""
    if log_df.empty:
        return pd.DataFrame()
    df = log_df.dropna(subset=["timestamp"]).copy()
    df["bucket"] = df["timestamp"].dt.floor(freq)
    return (
        df.groupby(["bucket", "page_type"])
        .size()
        .rename("hits")
        .reset_index()
    )
