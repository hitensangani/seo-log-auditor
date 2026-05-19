"""Streamlit entry point.

Run with::

    seo-log-auditor              # via the installed CLI
    uvx seo-log-auditor          # zero-install via uv
    streamlit run -m seo_log_auditor.app   # if you've cloned the source
"""

from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import streamlit as st

from seo_log_auditor.analysis.status_waste import waste_overview
from seo_log_auditor.classify import default_classifier, load_classifier
from seo_log_auditor.ui_state import (
    enrich,
    fetch_google_ranges_cached,
    fetch_sitemap_cached,
    filter_to_googlebot,
    get_state,
    init_session_defaults,
    parse_uploads_cached,
)
from seo_log_auditor.sitemap import to_paths


st.set_page_config(
    page_title="seo-log-auditor",
    page_icon=":mag:",
    layout="wide",
)
init_session_defaults()


# --------------------------------------------------------------------------- #
# Sidebar inputs
# --------------------------------------------------------------------------- #


def _sidebar() -> None:
    with st.sidebar:
        st.header("Inputs")
        uploads = st.file_uploader(
            "Grafana / Loki export",
            accept_multiple_files=True,
            help=(
                "Drop one or more files exported from Grafana Explore. "
                "JSON / JSONL / NDJSON / CSV / TXT / LOG are all auto-detected. "
                "No extension filter is applied so Finder won't grey anything out."
            ),
        )
        sitemap_url = st.text_input(
            "Sitemap URL",
            value=st.session_state.get("sitemap_url", ""),
            placeholder="https://example.com/sitemap.xml",
            help="Plain sitemap or sitemap index. Used for orphan detection and stale-page analysis.",
        )
        st.session_state["sitemap_url"] = sitemap_url

        patterns_file = st.file_uploader(
            "Page-pattern rules (optional)",
            type=["yaml", "yml"],
            help="A YAML file mapping URL regexes to page types. See config/page_patterns.example.yaml.",
        )

        verify_bots = st.toggle(
            "Verify Googlebot via reverse DNS",
            value=st.session_state.get("verification_enabled", False),
            help="On top of the IP-range check, run a forward-confirmed reverse DNS lookup for any IP that didn't match. Slow on first run; cached afterwards.",
        )
        st.session_state["verification_enabled"] = verify_bots

        only_verified_default = st.session_state.get("only_verified_default", False)
        st.session_state["only_verified_default"] = st.checkbox(
            "Restrict analysis to verified Googlebot",
            value=only_verified_default,
            help="When on, every analysis page filters to hits that passed the Google IP-range / rDNS check.",
        )

        run = st.button("Load / refresh", type="primary", use_container_width=True)
        clear = st.button(
            "Clear cache & re-fetch",
            use_container_width=True,
            help="Drops cached log parses, sitemap fetches, and Google IP-range data. Use after editing inputs or fixing a sitemap URL.",
        )

    if clear:
        st.cache_data.clear()
        for key in ("log_df", "sitemap", "sitemap_paths", "sitemap_page_types"):
            st.session_state[key] = None if key == "log_df" else st.session_state.get(key)
        st.session_state["log_df"] = None
        st.success("Cleared cached data. Click **Load / refresh** to re-run.")

    if run:
        _process_inputs(uploads, sitemap_url, patterns_file, verify_bots)


def _process_inputs(uploads, sitemap_url: str, patterns_file, verify_bots: bool) -> None:
    if not uploads:
        st.sidebar.error("Please upload at least one log file.")
        return

    with st.spinner("Parsing log files"):
        files = [(u.name, u.getvalue()) for u in uploads]
        df = parse_uploads_cached(files)

    if df.empty:
        st.sidebar.error("Couldn't parse any rows. Is this a Grafana/Loki export of nginx access logs?")
        return

    if patterns_file is not None:
        try:
            classifier = load_classifier(patterns_file.getvalue())
        except Exception as exc:  # noqa: BLE001
            st.sidebar.error(f"Failed to parse page-pattern rules: {exc}")
            return
    else:
        classifier = default_classifier()

    sitemap_paths: list[str] = []
    sitemap_result = None
    sitemap_page_types = pd.Series(dtype="string")
    if sitemap_url.strip():
        with st.spinner(f"Fetching sitemap {sitemap_url}"):
            sitemap_result = fetch_sitemap_cached(sitemap_url.strip())
        host = urlparse(sitemap_url).netloc or None
        sitemap_paths = to_paths(sitemap_result.urls, base_host=host)
        sitemap_page_types = classifier.classify_series(sitemap_paths)

        # Surface what happened so the user isn't guessing
        with st.sidebar:
            st.caption(
                f"Sitemap: fetched {len(sitemap_result.fetched)} document(s), "
                f"{len(sitemap_result.urls):,} URLs, {len(sitemap_paths):,} paths after host filter."
            )
            if sitemap_result.urls and not sitemap_paths:
                st.warning(
                    "All sitemap URLs were filtered out by host matching. "
                    "Your sitemap may live on a different domain than the URLs inside it."
                )
            for err in sitemap_result.errors[:5]:
                st.error(f"Sitemap error: {err}")
            if len(sitemap_result.errors) > 5:
                st.caption(f"...and {len(sitemap_result.errors) - 5} more sitemap errors.")

    with st.spinner("Looking up Google IP ranges"):
        ranges = fetch_google_ranges_cached()

    with st.spinner("Enriching log data (page types + bot verification)"):
        enriched = enrich(df, classifier, ranges, use_dns_fallback=verify_bots)

    st.session_state["log_df"] = enriched
    st.session_state["sitemap"] = sitemap_result
    st.session_state["sitemap_paths"] = sitemap_paths
    st.session_state["sitemap_page_types"] = sitemap_page_types
    st.session_state["classifier"] = classifier
    st.session_state["upload_signature"] = tuple((u.name, len(u.getvalue())) for u in uploads)


# --------------------------------------------------------------------------- #
# Body: KPI overview
# --------------------------------------------------------------------------- #


def _body() -> None:
    st.title("Crawl audit: nginx-ingress Googlebot logs")
    st.caption(
        "Upload a Grafana/Loki export of `{app=\"ingress-nginx\"} |= \"Googlebot\"`, "
        "add your sitemap, and dig in. Each technique lives on its own page in the sidebar."
    )

    state = get_state()
    if state is None:
        st.info(
            "**Get started:** download 30 days of nginx-ingress logs from Grafana "
            "Explore, drop the file into the sidebar, paste your sitemap URL, and hit "
            "**Load / refresh**."
        )
        return

    df = state.log_df
    only_verified = st.session_state.get("only_verified_default", False)
    bot_df = filter_to_googlebot(df, only_verified=only_verified)

    waste = waste_overview(bot_df)
    unique_urls = bot_df["path"].nunique()
    unique_ips = bot_df["ip"].nunique()
    verified_share = (
        bot_df["is_verified_googlebot"].fillna(False).mean() if not bot_df.empty else 0.0
    )

    span = ""
    if not bot_df.empty and bot_df["timestamp"].notna().any():
        first = bot_df["timestamp"].min()
        last = bot_df["timestamp"].max()
        span = f"{first:%Y-%m-%d %H:%M} -> {last:%Y-%m-%d %H:%M} UTC"

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bot hits", f"{waste['total']:,}")
    c2.metric("Unique URLs", f"{unique_urls:,}")
    c3.metric("Unique IPs", f"{unique_ips:,}")
    c4.metric("Waste ratio", f"{waste['waste_ratio']:.1%}")
    c5.metric("Verified Googlebot", f"{verified_share:.0%}")
    if span:
        st.caption(f"Time range: {span}")

    st.divider()
    st.subheader("Hits over time")
    if bot_df["timestamp"].notna().any():
        ts_df = (
            bot_df.dropna(subset=["timestamp"])
            .assign(bucket=lambda d: d["timestamp"].dt.floor("1h"))
            .groupby(["bucket", "page_type"])
            .size()
            .rename("hits")
            .reset_index()
        )
        fig = px.area(ts_df, x="bucket", y="hits", color="page_type")
        fig.update_layout(height=380, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No timestamps in the loaded data; trend chart unavailable.")

    st.subheader("What to look at next")
    st.markdown(
        """
- **Crawl Budget** -- where the hits are going vs. where your URLs live.
- **Orphan Pages** -- URLs being crawled that aren't in your sitemap.
- **Status Waste** -- the share of hits hitting redirects or dead ends.
- **Stale Pages** -- sitemap URLs Google hasn't visited recently.
- **Performance** -- size and latency vs. how often Google revisits.
- **Bot Verification** -- real Googlebot vs. spoofed user-agents.
- **Parameter Traps** -- query-string explosions sucking up crawl budget.
        """
    )


_sidebar()
_body()
