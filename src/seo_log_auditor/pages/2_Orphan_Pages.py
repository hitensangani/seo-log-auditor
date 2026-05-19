from __future__ import annotations

import streamlit as st

from seo_log_auditor.analysis.orphans import find_orphans
from seo_log_auditor.ui_state import filter_to_googlebot, require_state

st.set_page_config(page_title="Orphan Pages", layout="wide")
state = require_state()

st.title("2. Orphan Pages")
st.caption(
    "Pages Googlebot is hitting (200 OK) that aren't in your sitemap. These "
    "often turn out to be old marketing landing pages or deleted sections still "
    "earning backlinks -- they consume crawl budget without being part of your "
    "intentional site architecture."
)

if not state.sitemap_paths:
    st.warning(
        "No sitemap loaded. Add a sitemap URL in the sidebar and click **Load / refresh**."
    )
    st.stop()

only_verified = st.session_state.get("only_verified_default", False)
bot_df = filter_to_googlebot(state.log_df, only_verified=only_verified)

include_non_200 = st.toggle(
    "Include non-200 hits",
    value=False,
    help="By default we only flag URLs that successfully responded with 200, since 4xx orphans are usually less interesting.",
)

orphans = find_orphans(bot_df, state.sitemap_paths, only_200=not include_non_200)

st.metric("Orphan URLs", f"{len(orphans):,}")
if orphans.empty:
    st.success("No orphans found.")
    st.stop()

st.dataframe(orphans, use_container_width=True, hide_index=True)

st.download_button(
    "Download orphans as CSV",
    data=orphans.to_csv(index=False).encode(),
    file_name="orphans.csv",
    mime="text/csv",
)
