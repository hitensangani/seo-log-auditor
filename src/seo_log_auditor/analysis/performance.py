"""Technique 5: byte-size and latency correlation.

We're looking for the inflection point where Googlebot effectively gives up:
beyond a certain page size or response time, hit rate drops off a cliff.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def size_vs_latency(log_df: pd.DataFrame) -> pd.DataFrame:
    """Per-URL median size and latency, suitable for a scatter plot."""
    if log_df.empty:
        return pd.DataFrame(columns=["path", "page_type", "median_bytes", "median_latency_ms", "hits"])
    df = log_df.dropna(subset=["bytes"]).copy()
    grouped = df.groupby(["path", "page_type"]).agg(
        median_bytes=("bytes", "median"),
        median_latency_ms=("latency_ms", "median"),
        hits=("path", "size"),
    )
    return grouped.reset_index()


def hits_by_size_decile(log_df: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    """Bucket URLs by response size, then summarise hit-rate per bucket. The
    sweet spot for spotting "Googlebot gives up at N MB" lives here.

    Columns: ``decile, lower_bytes, upper_bytes, urls, total_hits, avg_hits_per_url``.
    """
    if log_df.empty:
        return pd.DataFrame(columns=["decile", "lower_bytes", "upper_bytes", "urls", "total_hits", "avg_hits_per_url"])

    per_url = log_df.dropna(subset=["bytes"]).groupby("path").agg(
        median_bytes=("bytes", "median"),
        hits=("path", "size"),
    )
    if per_url.empty or per_url["median_bytes"].nunique() < 2:
        return pd.DataFrame(columns=["decile", "lower_bytes", "upper_bytes", "urls", "total_hits", "avg_hits_per_url"])

    try:
        per_url["decile"] = pd.qcut(per_url["median_bytes"], q=bins, labels=False, duplicates="drop")
    except ValueError:
        per_url["decile"] = pd.cut(per_url["median_bytes"], bins=bins, labels=False)

    edges = (
        per_url.groupby("decile")["median_bytes"]
        .agg(lower_bytes="min", upper_bytes="max")
    )
    summary = per_url.groupby("decile").agg(
        urls=("median_bytes", "size"),
        total_hits=("hits", "sum"),
        avg_hits_per_url=("hits", "mean"),
    )
    out = edges.join(summary).reset_index()
    return out


def latency_summary(log_df: pd.DataFrame) -> dict[str, float]:
    if log_df.empty or log_df["latency_ms"].dropna().empty:
        return {"p50": np.nan, "p90": np.nan, "p99": np.nan, "max": np.nan}
    s = log_df["latency_ms"].dropna()
    return {
        "p50": float(s.quantile(0.5)),
        "p90": float(s.quantile(0.9)),
        "p99": float(s.quantile(0.99)),
        "max": float(s.max()),
    }
