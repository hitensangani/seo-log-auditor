from __future__ import annotations

import pandas as pd

from seo_log_auditor.analysis.param_traps import parameter_frequency, trap_candidates


def _build_df(rows: list[tuple[str, str]]) -> pd.DataFrame:
    """Helper to build a minimal DataFrame with just the columns the analysis needs."""
    return pd.DataFrame(
        {
            "path": [p for p, _ in rows],
            "query": [q for _, q in rows],
            "has_params": [bool(q) for _, q in rows],
        }
    )


def test_trap_candidates_detects_explosion():
    rows = [("/category/x", f"sort=a&page={i}") for i in range(60)]
    rows += [("/category/y", "page=1")] * 5
    df = _build_df(rows)
    traps = trap_candidates(df, min_variants=50)
    assert list(traps["path"]) == ["/category/x"]
    assert int(traps.iloc[0]["variants"]) >= 50
    assert traps.iloc[0]["top_param"] in ("sort", "page")


def test_trap_candidates_threshold():
    rows = [("/x", f"q={i}") for i in range(20)]
    df = _build_df(rows)
    assert trap_candidates(df, min_variants=50).empty
    assert not trap_candidates(df, min_variants=10).empty


def test_parameter_frequency():
    rows = [
        ("/a", "page=1"),
        ("/a", "page=2"),
        ("/b", "sort=asc"),
        ("/b", "sort=desc&color=red"),
        ("/c", ""),
    ]
    df = _build_df(rows)
    freq = parameter_frequency(df)
    by_param = dict(zip(freq["param"], freq["hits"]))
    assert by_param.get("page") == 2
    assert by_param.get("sort") == 2
    assert by_param.get("color") == 1


def test_handles_empty_df():
    df = pd.DataFrame(columns=["path", "query", "has_params"])
    assert trap_candidates(df).empty
    assert parameter_frequency(df).empty
