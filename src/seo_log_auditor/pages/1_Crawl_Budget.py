from __future__ import annotations

import plotly.express as px
import streamlit as st

from seo_log_auditor.analysis.budget import crawl_budget_distribution, hits_over_time
from seo_log_auditor.ui_state import filter_to_googlebot, require_state

st.set_page_config(page_title="Crawl Budget", layout="wide")
state = require_state()

only_verified = st.session_state.get("only_verified_default", False)
bot_df = filter_to_googlebot(state.log_df, only_verified=only_verified)

st.title("1. Crawl Budget Distribution")
st.caption(
    "How Googlebot is *actually* spending its budget vs. how your URLs are "
    "structured. A large positive delta means a page type is over-crawled; a "
    "large negative delta means you're being neglected there."
)

dist = crawl_budget_distribution(
    bot_df,
    sitemap_page_types=state.sitemap_page_types if not state.sitemap_page_types.empty else None,
)

if dist.empty:
    st.info("No data yet.")
    st.stop()

st.dataframe(
    dist.style.format({
        "hit_share": "{:.1%}",
        "url_share": "{:.1%}",
        "delta": "{:+.1%}",
    }),
    use_container_width=True,
)

col1, col2 = st.columns(2)
with col1:
    st.subheader("Hit share by page type")
    fig = px.pie(dist.reset_index(), names="page_type", values="hits", hole=0.4)
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Hit share vs. URL share")
    cmp = dist.reset_index()[["page_type", "hit_share", "url_share"]].melt(
        id_vars="page_type", var_name="series", value_name="share"
    )
    fig = px.bar(cmp, x="page_type", y="share", color="series", barmode="group")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Hits over time, by page type")
ts = hits_over_time(bot_df, freq="1h")
if not ts.empty:
    fig = px.area(ts, x="bucket", y="hits", color="page_type")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No timestamps available for the trend chart.")
