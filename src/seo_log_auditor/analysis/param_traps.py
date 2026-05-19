"""Technique 7: parameter infinite-loop detection.

A "crawl trap" is a path with an explosive number of distinct query-string
combinations -- typically driven by faceted navigation (sort/color/size),
session IDs, or tracking params. We surface paths whose unique-query-variant
count exceeds a threshold and break down which parameter keys are the worst
offenders.
"""

from __future__ import annotations

from urllib.parse import parse_qsl

import pandas as pd


def trap_candidates(
    log_df: pd.DataFrame,
    min_variants: int = 50,
) -> pd.DataFrame:
    """Paths with at least ``min_variants`` distinct query strings.

    Columns: ``path, variants, hits, sample_query, top_param``.
    """
    if log_df.empty:
        return pd.DataFrame(columns=["path", "variants", "hits", "sample_query", "top_param"])

    df = log_df[log_df["has_params"].fillna(False)]
    if df.empty:
        return pd.DataFrame(columns=["path", "variants", "hits", "sample_query", "top_param"])

    grouped = df.groupby("path").agg(
        variants=("query", "nunique"),
        hits=("path", "size"),
        sample_query=("query", "first"),
    )
    grouped = grouped[grouped["variants"] >= min_variants]
    if grouped.empty:
        return pd.DataFrame(columns=["path", "variants", "hits", "sample_query", "top_param"])

    grouped["top_param"] = [_top_param_for_path(df, p) for p in grouped.index]
    return grouped.sort_values("variants", ascending=False).reset_index()


def parameter_frequency(log_df: pd.DataFrame, top_n: int = 30) -> pd.DataFrame:
    """Most common query-parameter keys across all logged hits.

    Columns: ``param, hits, paths_seen``.
    """
    if log_df.empty:
        return pd.DataFrame(columns=["param", "hits", "paths_seen"])
    rows: list[tuple[str, str]] = []
    for path, query in zip(log_df["path"], log_df["query"]):
        if not query:
            continue
        for k, _ in parse_qsl(query, keep_blank_values=True):
            rows.append((path, k))
    if not rows:
        return pd.DataFrame(columns=["param", "hits", "paths_seen"])
    df = pd.DataFrame(rows, columns=["path", "param"])
    out = (
        df.groupby("param")
        .agg(hits=("param", "size"), paths_seen=("path", "nunique"))
        .sort_values("hits", ascending=False)
        .head(top_n)
        .reset_index()
    )
    return out


def _top_param_for_path(df: pd.DataFrame, path: str) -> str:
    """Return the parameter key that appears in the most distinct query
    variants for ``path``."""
    queries = df.loc[df["path"] == path, "query"].dropna().unique()
    counts: dict[str, int] = {}
    for q in queries:
        seen_in_q: set[str] = set()
        for k, _ in parse_qsl(q, keep_blank_values=True):
            if k in seen_in_q:
                continue
            seen_in_q.add(k)
            counts[k] = counts.get(k, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]
