from __future__ import annotations

import plotly.express as px
import streamlit as st

from seo_log_auditor.analysis.param_traps import parameter_frequency, trap_candidates
from seo_log_auditor.ui_state import filter_to_googlebot, require_state

st.set_page_config(page_title="Parameter Traps", layout="wide")
state = require_state()

st.title("7. Parameter Infinite-Loop Detection")
st.caption(
    "Paths whose query strings have exploded into an unhealthy number of "
    "variants. Faceted nav (sort/color/size), session IDs, and tracking params "
    "are the usual culprits."
)

only_verified = st.session_state.get("only_verified_default", False)
bot_df = filter_to_googlebot(state.log_df, only_verified=only_verified)

threshold = st.slider(
    "Minimum distinct query variants to flag a path",
    min_value=10,
    max_value=500,
    value=50,
    step=10,
)

traps = trap_candidates(bot_df, min_variants=threshold)
st.metric("Trap candidates", f"{len(traps):,}")
if traps.empty:
    st.success(f"No paths with at least {threshold} query variants.")
else:
    st.dataframe(traps, use_container_width=True, hide_index=True)
    st.download_button(
        "Download trap list as CSV",
        data=traps.to_csv(index=False).encode(),
        file_name="param_traps.csv",
        mime="text/csv",
    )

st.subheader("Most common query parameters across all hits")
freq = parameter_frequency(bot_df, top_n=30)
if not freq.empty:
    fig = px.bar(freq, x="param", y="hits", text="paths_seen")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("`paths_seen` = number of distinct paths the parameter appears on.")
