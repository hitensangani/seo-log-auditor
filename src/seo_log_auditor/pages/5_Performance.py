from __future__ import annotations

import plotly.express as px
import streamlit as st

from seo_log_auditor.analysis.performance import hits_by_size_decile, latency_summary, size_vs_latency
from seo_log_auditor.ui_state import filter_to_googlebot, require_state

st.set_page_config(page_title="Performance", layout="wide")
state = require_state()

st.title("5. Byte-Size & Latency Correlation")
st.caption(
    "We're looking for the inflection point where Googlebot effectively gives "
    "up: beyond a certain page size or response time, hit rate drops."
)

only_verified = st.session_state.get("only_verified_default", False)
bot_df = filter_to_googlebot(state.log_df, only_verified=only_verified)

stats = latency_summary(bot_df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("p50 latency", f"{stats['p50']:.0f} ms" if stats["p50"] == stats["p50"] else "n/a")
c2.metric("p90 latency", f"{stats['p90']:.0f} ms" if stats["p90"] == stats["p90"] else "n/a")
c3.metric("p99 latency", f"{stats['p99']:.0f} ms" if stats["p99"] == stats["p99"] else "n/a")
c4.metric("max latency", f"{stats['max']:.0f} ms" if stats["max"] == stats["max"] else "n/a")

st.subheader("Per-URL: median bytes vs. median latency (size = hits)")
scatter = size_vs_latency(bot_df)
if scatter.empty:
    st.info("No size/latency data to plot. The log format may not include `request_time`.")
else:
    fig = px.scatter(
        scatter,
        x="median_bytes",
        y="median_latency_ms",
        size="hits",
        color="page_type",
        hover_data=["path", "hits"],
        log_x=True,
    )
    fig.update_layout(height=480, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Hits per URL, bucketed by page-size decile")
st.caption(
    "If the average hits-per-URL collapses in the upper deciles you've found "
    "the size-based inflection point."
)
deciles = hits_by_size_decile(bot_df)
if not deciles.empty:
    deciles_display = deciles.assign(
        bucket=lambda d: d.apply(
            lambda r: f"{int(r['lower_bytes']):,} - {int(r['upper_bytes']):,} B", axis=1
        )
    )
    st.dataframe(deciles_display, use_container_width=True, hide_index=True)
    fig = px.bar(deciles_display, x="bucket", y="avg_hits_per_url", text="urls")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
