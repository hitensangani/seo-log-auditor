from __future__ import annotations

import plotly.express as px
import streamlit as st

from seo_log_auditor.analysis.status_waste import (
    four_oh_four_forensics,
    status_class_breakdown,
    waste_by_page_type,
    waste_overview,
    worst_offenders,
)
from seo_log_auditor.ui_state import filter_to_googlebot, require_state

st.set_page_config(page_title="Status Waste", layout="wide")
state = require_state()

st.title("3. Status Code Waste")
st.caption(
    "How much of Googlebot's effort goes to redirects, missing pages, or "
    "errors. Waste ratio = non-200 hits / total hits."
)

only_verified = st.session_state.get("only_verified_default", False)
bot_df = filter_to_googlebot(state.log_df, only_verified=only_verified)

overview = waste_overview(bot_df)
c1, c2, c3 = st.columns(3)
c1.metric("Total bot hits", f"{overview['total']:,}")
c2.metric("Non-200 hits", f"{overview['non_200']:,}")
c3.metric("Waste ratio", f"{overview['waste_ratio']:.1%}")

st.subheader("Status class breakdown")
classes = status_class_breakdown(bot_df)
if not classes.empty:
    fig = px.bar(classes, x="status_class", y="hits", text="hits")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Waste ratio per page type")
by_type = waste_by_page_type(bot_df)
if not by_type.empty:
    st.dataframe(
        by_type.style.format({"waste_ratio": "{:.1%}"}),
        use_container_width=True,
        hide_index=True,
    )
    fig = px.bar(by_type, x="page_type", y="waste_ratio", text="non_200")
    fig.update_yaxes(tickformat=".0%")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=20, b=0))
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Worst offenders")
top_n = st.slider("Show top N URLs", min_value=20, max_value=500, value=100, step=20)
selected_classes = st.multiselect(
    "Status classes",
    options=["3xx", "4xx", "5xx"],
    default=["3xx", "4xx", "5xx"],
)
offenders = worst_offenders(bot_df, status_classes=tuple(selected_classes), top_n=top_n)
st.dataframe(offenders, use_container_width=True, hide_index=True)

st.divider()
st.subheader("404 forensics: where did Google find these?")
st.caption(
    "For every 404 URL hit by Googlebot, we surface (a) the most common "
    "`Referer` header that came in with the request -- direct evidence of "
    "where the link lives -- and (b) whether the URL is in your sitemap. "
    "Googlebot rarely sends a Referer (it crawls from its own queue), so most "
    "rows will show a blank referer; **`in_sitemap = True` is the strongest "
    "actionable signal there.**"
)

scope = st.radio(
    "Audience",
    options=["Googlebot only", "All hits (incl. real users)"],
    horizontal=True,
    help="Real users almost always send a Referer header -- switch to 'All hits' to see broken inbound links discovered by humans.",
)
forensics_df = bot_df if scope == "Googlebot only" else state.log_df

forensics_classes = st.multiselect(
    "Status classes for forensics",
    options=["3xx", "4xx", "5xx"],
    default=["4xx"],
    help="Most useful for 4xx; sometimes worth checking 3xx redirect chains and 5xx.",
)
forensics = four_oh_four_forensics(
    forensics_df,
    sitemap_paths=state.sitemap_paths or None,
    status_classes=tuple(forensics_classes) or ("4xx",),
    top_n=200,
)
if forensics.empty:
    st.success("No URLs in the selected status classes.")
else:
    in_sitemap_count = int(forensics["in_sitemap"].sum())
    with_referer = int((forensics["referer_hits"] > 0).sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Broken URLs surfaced", f"{len(forensics):,}")
    c2.metric("In your sitemap", f"{in_sitemap_count:,}",
              help="Fix or remove these from the sitemap -- it's directly telling Google to fetch dead URLs.")
    c3.metric("With Referer header", f"{with_referer:,}")
    st.dataframe(forensics, use_container_width=True, hide_index=True)
    st.download_button(
        "Download 404 forensics as CSV",
        data=forensics.to_csv(index=False).encode(),
        file_name="404_forensics.csv",
        mime="text/csv",
    )
