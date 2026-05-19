"""Technique 2: orphan pages.

Orphans = URLs Googlebot is hitting (200 OK) that don't appear in the sitemap.
These are typically stale landing pages, deleted sections still earning
backlinks, or unintentionally exposed routes.
"""

from __future__ import annotations

import pandas as pd


def find_orphans(
    log_df: pd.DataFrame,
    sitemap_paths: list[str],
    only_200: bool = True,
) -> pd.DataFrame:
    """Return a DataFrame of orphan URLs sorted by hit count, descending.

    Columns: ``path, hits, last_crawled, status_mix``.
    """
    if log_df.empty:
        return pd.DataFrame(columns=["path", "hits", "last_crawled", "status_mix"])

    df = log_df
    if only_200:
        df = df[df["status"] == 200]

    sitemap_set = set(sitemap_paths)
    # Compare on path-only first (query strings rarely appear in sitemaps)
    orphan_mask = ~df["path"].isin({_path_only(p) for p in sitemap_set})
    orphans = df.loc[orphan_mask]
    if orphans.empty:
        return pd.DataFrame(columns=["path", "hits", "last_crawled", "status_mix"])

    grouped = orphans.groupby("path").agg(
        hits=("path", "size"),
        last_crawled=("timestamp", "max"),
    )
    status_mix = (
        log_df[log_df["path"].isin(orphans["path"].unique())]
        .groupby("path")["status"]
        .apply(_format_status_mix)
        .rename("status_mix")
    )
    out = grouped.join(status_mix).sort_values("hits", ascending=False).reset_index()
    return out


def _path_only(url: str) -> str:
    return url.split("?", 1)[0]


def _format_status_mix(s: pd.Series) -> str:
    counts = s.value_counts().sort_index()
    return ", ".join(f"{int(code)}:{int(n)}" for code, n in counts.items())
