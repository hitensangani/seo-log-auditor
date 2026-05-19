"""Technique 4: stale high-value pages.

For every URL in the sitemap, look up the most recent Googlebot hit (200 OK).
Anything that hasn't been crawled in the last ``stale_days`` is surfaced.

When internal-link-depth data becomes available (e.g. a Screaming Frog CSV
upload) we'll layer ``depth`` on top to spot Deep Crawl Leakage. For now the
sitemap stands in for "things you care about".
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd


def last_crawled_per_path(log_df: pd.DataFrame) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame(columns=["path", "last_crawled", "hits"])
    df = log_df.dropna(subset=["timestamp"])
    grouped = df.groupby("path").agg(
        last_crawled=("timestamp", "max"),
        hits=("path", "size"),
    )
    return grouped.reset_index()


def stale_pages(
    log_df: pd.DataFrame,
    sitemap_paths: list[str],
    stale_days: int = 7,
    now: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return the subset of sitemap URLs whose most recent crawl is older than
    ``stale_days`` (or absent entirely).

    Columns: ``path, last_crawled, days_since, hits, status``.
    """
    if not sitemap_paths:
        return pd.DataFrame(columns=["path", "last_crawled", "days_since", "hits", "status"])

    if now is None:
        if not log_df.empty and log_df["timestamp"].notna().any():
            now = log_df["timestamp"].max()
        else:
            now = pd.Timestamp.utcnow()
    if now.tzinfo is None:
        now = now.tz_localize("UTC")

    sitemap_paths_only = [p.split("?", 1)[0] for p in sitemap_paths]
    sitemap_df = pd.DataFrame({"path": sitemap_paths_only}).drop_duplicates()

    last_seen = last_crawled_per_path(log_df).set_index("path")
    merged = sitemap_df.merge(last_seen, on="path", how="left")

    threshold = now - timedelta(days=stale_days)
    merged["days_since"] = (now - merged["last_crawled"]).dt.total_seconds() / 86400.0
    merged["status"] = merged["last_crawled"].apply(
        lambda ts: "never" if pd.isna(ts) else ("stale" if ts < threshold else "fresh")
    )
    merged["hits"] = merged["hits"].fillna(0).astype("Int64")

    stale = merged[merged["status"].isin(("never", "stale"))]
    return stale.sort_values(
        by=["status", "days_since"], ascending=[True, False], na_position="first"
    ).reset_index(drop=True)


def crawl_depth_distribution(log_df: pd.DataFrame) -> pd.DataFrame:
    """Heuristic depth = number of path segments. Approximation until real
    internal-link data is plugged in."""
    if log_df.empty:
        return pd.DataFrame(columns=["depth", "hits"])
    depth = log_df["path"].fillna("/").str.strip("/").str.split("/").apply(
        lambda parts: len([p for p in parts if p])
    )
    return (
        depth.value_counts()
        .sort_index()
        .rename_axis("depth")
        .rename("hits")
        .reset_index()
    )
