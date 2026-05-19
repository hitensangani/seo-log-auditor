from __future__ import annotations

import plotly.express as px
import streamlit as st

from seo_log_auditor.analysis.masquerade import (
    hits_by_verdict,
    top_spoofers,
    verification_summary,
)
from seo_log_auditor.ui_state import require_state

st.set_page_config(page_title="Bot Verification", layout="wide")
state = require_state()

st.title("6. User-Agent Masquerade Check")
st.caption(
    "Real Googlebot vs. anyone claiming to be Googlebot. Verification combines "
    "Google's published IP-range list with optional forward-confirmed reverse "
    "DNS (toggle in the sidebar)."
)

df = state.log_df  # use the full DF here, not Googlebot-only

summary = verification_summary(df)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Claimed Googlebot hits", f"{summary['claimed']:,}")
c2.metric("Verified", f"{summary['verified']:,}")
c3.metric("Spoofed", f"{summary['spoofed']:,}")
c4.metric("Verified share", f"{summary['verified_share']:.0%}")

if not state.verification_enabled:
    st.info(
        "Reverse-DNS verification is **off**. We're using only Google's published "
        "IP-range list. Toggle it on in the sidebar for the strictest check (slower)."
    )

st.subheader("Verdict mix")
verdicts = hits_by_verdict(df)
if not verdicts.empty:
    fig = px.bar(verdicts, x="verdict", y="hits", text="hits")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Top spoofers")
spoofers = top_spoofers(df, top_n=100)
if spoofers.empty:
    st.success("No spoofed Googlebot hits detected.")
else:
    st.dataframe(spoofers, use_container_width=True, hide_index=True)
    st.download_button(
        "Download spoofer IP list",
        data=spoofers.to_csv(index=False).encode(),
        file_name="spoofers.csv",
        mime="text/csv",
    )
