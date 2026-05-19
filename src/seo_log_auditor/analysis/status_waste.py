"""Technique 3: status-code waste.

* Overall waste ratio = non-200 hits / total hits.
* Per-page-type breakdown so you can see whether the waste is concentrated.
* Per-status-class breakdown (2xx / 3xx / 4xx / 5xx).
* Worst-offender URLs for the 3xx and 4xx classes.
"""

from __future__ import annotations

import pandas as pd


def waste_overview(log_df: pd.DataFrame) -> dict[str, float]:
    """Return total / non200 / waste_ratio."""
    if log_df.empty:
        return {"total": 0, "non_200": 0, "waste_ratio": 0.0}
    total = len(log_df)
    non_200 = int((log_df["status"] != 200).sum())
    return {
        "total": total,
        "non_200": non_200,
        "waste_ratio": non_200 / total if total else 0.0,
    }


def status_class(status: int | float) -> str:
    if pd.isna(status):
        return "unknown"
    s = int(status)
    if 200 <= s < 300:
        return "2xx"
    if 300 <= s < 400:
        return "3xx"
    if 400 <= s < 500:
        return "4xx"
    if 500 <= s < 600:
        return "5xx"
    return "other"


def waste_by_page_type(log_df: pd.DataFrame) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame(columns=["page_type", "total", "non_200", "waste_ratio"])
    df = log_df.copy()
    df["is_non_200"] = df["status"] != 200
    grouped = df.groupby("page_type").agg(
        total=("status", "size"),
        non_200=("is_non_200", "sum"),
    )
    grouped["waste_ratio"] = grouped["non_200"] / grouped["total"]
    return grouped.sort_values("waste_ratio", ascending=False).reset_index()


def status_class_breakdown(log_df: pd.DataFrame) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame(columns=["status_class", "hits", "share"])
    classes = log_df["status"].apply(status_class)
    counts = classes.value_counts().rename("hits")
    share = (counts / counts.sum()).rename("share")
    return pd.concat([counts, share], axis=1).reset_index(names="status_class")


def four_oh_four_forensics(
    log_df: pd.DataFrame,
    sitemap_paths: list[str] | None = None,
    status_classes: tuple[str, ...] = ("4xx",),
    top_n: int = 200,
) -> pd.DataFrame:
    """For every URL hit with a status in ``status_classes``, surface the
    evidence we have for *where the link came from*:

    * ``hits``: how often it was hit.
    * ``last_seen``: most recent hit.
    * ``top_referer`` + ``referer_hits``: most common Referer header value
      (empty when the requester didn't send one -- typical for Googlebot).
    * ``distinct_referers``: how many distinct Referer values we saw.
    * ``in_sitemap``: True if the path is in the supplied sitemap (a strong
      signal: that's where Google found it).

    Sorted by hits descending. Limited to ``top_n`` rows.
    """
    if log_df.empty:
        return pd.DataFrame(
            columns=[
                "path", "hits", "last_seen", "top_referer",
                "referer_hits", "distinct_referers", "in_sitemap",
            ]
        )
    df = log_df.copy()
    df["status_class"] = df["status"].apply(status_class)
    df = df[df["status_class"].isin(status_classes)]
    if df.empty:
        return pd.DataFrame(
            columns=[
                "path", "hits", "last_seen", "top_referer",
                "referer_hits", "distinct_referers", "in_sitemap",
            ]
        )

    sitemap_set = {p.split("?", 1)[0] for p in (sitemap_paths or [])}
    referer_col = df.get("referer", pd.Series("", index=df.index)).fillna("")

    rows: list[dict] = []
    for path, group in df.groupby("path"):
        refs = referer_col.loc[group.index]
        non_empty = refs[refs != ""]
        if not non_empty.empty:
            top = non_empty.value_counts()
            top_referer = str(top.index[0])
            referer_hits = int(top.iloc[0])
            distinct = int(non_empty.nunique())
        else:
            top_referer, referer_hits, distinct = "", 0, 0
        rows.append({
            "path": path,
            "hits": int(len(group)),
            "last_seen": group["timestamp"].max(),
            "top_referer": top_referer,
            "referer_hits": referer_hits,
            "distinct_referers": distinct,
            "in_sitemap": path in sitemap_set,
        })
    return (
        pd.DataFrame(rows)
        .sort_values("hits", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )


def worst_offenders(log_df: pd.DataFrame, status_classes: tuple[str, ...] = ("3xx", "4xx", "5xx"), top_n: int = 50) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame(columns=["path", "status", "hits"])
    df = log_df.copy()
    df["status_class"] = df["status"].apply(status_class)
    df = df[df["status_class"].isin(status_classes)]
    if df.empty:
        return pd.DataFrame(columns=["path", "status", "hits"])
    grouped = (
        df.groupby(["path", "status"])
        .size()
        .rename("hits")
        .reset_index()
        .sort_values("hits", ascending=False)
        .head(top_n)
    )
    return grouped
