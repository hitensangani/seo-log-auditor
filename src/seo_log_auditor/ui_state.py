"""Shared Streamlit-side helpers: caching the enriched DataFrame, retrieving
the current state from session_state, and a guard that nudges users to the
sidebar when they jump to a sub-page first.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import streamlit as st

from seo_log_auditor.classify import Classifier, add_page_type, default_classifier, load_classifier
from seo_log_auditor.parsers import parse_log_file
from seo_log_auditor.sitemap import SitemapResult, fetch_sitemap, to_paths
from seo_log_auditor.verify_bot import GoogleRanges, add_verification, fetch_google_ranges


@dataclass
class AppState:
    log_df: pd.DataFrame
    sitemap: SitemapResult | None
    sitemap_paths: list[str]
    sitemap_page_types: pd.Series
    classifier: Classifier
    verification_enabled: bool


def init_session_defaults() -> None:
    st.session_state.setdefault("log_df", None)
    st.session_state.setdefault("sitemap", None)
    st.session_state.setdefault("sitemap_paths", [])
    st.session_state.setdefault("sitemap_page_types", pd.Series(dtype="string"))
    st.session_state.setdefault("classifier", default_classifier())
    st.session_state.setdefault("verification_enabled", False)
    st.session_state.setdefault("upload_signature", None)


def get_state() -> AppState | None:
    if st.session_state.get("log_df") is None:
        return None
    return AppState(
        log_df=st.session_state["log_df"],
        sitemap=st.session_state.get("sitemap"),
        sitemap_paths=st.session_state.get("sitemap_paths", []),
        sitemap_page_types=st.session_state.get("sitemap_page_types", pd.Series(dtype="string")),
        classifier=st.session_state.get("classifier") or default_classifier(),
        verification_enabled=bool(st.session_state.get("verification_enabled", False)),
    )


def require_state() -> AppState:
    state = get_state()
    if state is None:
        st.warning("Upload a log export from the home page first.")
        st.stop()
    return state  # type: ignore[return-value]


@st.cache_data(show_spinner=False)
def parse_uploads_cached(files: list[tuple[str, bytes]]) -> pd.DataFrame:
    """Parse multiple uploaded files and concatenate into one DataFrame.

    The cache key is the tuple of (name, bytes), so repeated re-runs with the
    same files come back instantly.
    """
    frames: list[pd.DataFrame] = []
    for name, content in files:
        df = parse_log_file(name, content)
        if not df.empty:
            frames.append(df)
    if not frames:
        return parse_log_file("empty.txt", b"")
    return pd.concat(frames, ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def fetch_sitemap_cached(url: str) -> SitemapResult:
    return fetch_sitemap(url)


@st.cache_data(show_spinner=False)
def fetch_google_ranges_cached() -> GoogleRanges:
    return fetch_google_ranges()


def load_classifier_from_upload(uploaded: Any) -> Classifier:
    if uploaded is None:
        return default_classifier()
    return load_classifier(uploaded.read())


def enrich(
    df: pd.DataFrame,
    classifier: Classifier,
    google_ranges: GoogleRanges,
    use_dns_fallback: bool,
) -> pd.DataFrame:
    df = add_page_type(df, classifier)
    df = add_verification(df, google_ranges, use_dns_fallback=use_dns_fallback)
    return df


def filter_to_googlebot(
    df: pd.DataFrame, only_verified: bool
) -> pd.DataFrame:
    """Helper used on every analysis page to scope to Googlebot traffic."""
    claimed_mask = df["claimed_bot"].fillna("").str.startswith(
        ("Googlebot", "AdsBot-Google", "Mediapartners-Google")
    )
    if only_verified and "is_verified_googlebot" in df.columns:
        return df[claimed_mask & df["is_verified_googlebot"].fillna(False)]
    return df[claimed_mask]
