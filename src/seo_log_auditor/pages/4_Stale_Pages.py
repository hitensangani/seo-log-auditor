from __future__ import annotations

import plotly.express as px
import streamlit as st

from seo_log_auditor.analysis.frequency import crawl_depth_distribution, stale_pages
from seo_log_auditor.ui_state import filter_to_googlebot, require_state

st.set_page_config(page_title="Stale Pages", layout="wide")
state = require_state()

st.title("4. Stale High-Value Pages")
st.caption(
    "Sitemap URLs that Googlebot hasn't visited in N days, or never. "
    "These are the prime candidates for the 'Deep Crawl Leakage' you described."
)

if not state.sitemap_paths:
    st.warning(
        "No sitemap loaded. Add a sitemap URL in the sidebar and click **Load / refresh**."
    )
    st.stop()

only_verified = st.session_state.get("only_verified_default", False)
bot_df = filter_to_googlebot(state.log_df, only_verified=only_verified)

stale_days = st.slider("Stale threshold (days)", 1, 30, value=7)

stale = stale_pages(bot_df, state.sitemap_paths, stale_days=stale_days)

never = (stale["status"] == "never").sum()
old = (stale["status"] == "stale").sum()
c1, c2 = st.columns(2)
c1.metric("Never crawled", f"{never:,}")
c2.metric(f"Crawled but >{stale_days}d old", f"{old:,}")

st.dataframe(stale, use_container_width=True, hide_index=True)

st.download_button(
    "Download stale list as CSV",
    data=stale.to_csv(index=False).encode(),
    file_name="stale_pages.csv",
    mime="text/csv",
)

st.divider()
st.subheader("Heuristic depth distribution (placeholder for technique 4 deeper layer)")
st.caption(
    "Until you upload a Screaming Frog / Sitebulb crawl with internal-link depth, "
    "we approximate depth as the number of path segments. The real metric needs "
    "shortest-path-from-homepage data."
)
depth = crawl_depth_distribution(bot_df)
if not depth.empty:
    fig = px.bar(depth, x="depth", y="hits", text="hits")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
