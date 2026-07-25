from __future__ import annotations

from datetime import timezone
from typing import Any

import pandas as pd
import streamlit as st


def _liquid_glass_css() -> str:
    """CSS uses Streamlit's native color-scheme, so menu changes are instant."""
    tokens = {
        "ink": "light-dark(#0A0D14, #F8FAFF)",
        "muted": "light-dark(#606979, #AAB2C2)",
        "surface": "light-dark(rgba(255,255,255,.66), rgba(15,19,28,.64))",
        "surface_strong": "light-dark(rgba(255,255,255,.86), rgba(17,22,32,.82))",
        "control": "light-dark(rgba(255,255,255,.78), rgba(17,22,32,.76))",
        "border": "light-dark(rgba(255,255,255,.82), rgba(255,255,255,.13))",
        "border_soft": "light-dark(rgba(55,66,92,.10), rgba(255,255,255,.075))",
        "highlight": "light-dark(rgba(255,255,255,.94), rgba(255,255,255,.10))",
        "shadow": "light-dark(rgba(44,55,82,.14), rgba(0,0,0,.32))",
        "header": "light-dark(rgba(246,248,252,.66), rgba(7,9,14,.58))",
        "sidebar_top": "light-dark(rgba(250,251,254,.90), rgba(12,16,24,.90))",
        "sidebar_bottom": "light-dark(rgba(242,245,250,.92), rgba(7,9,14,.94))",
        "bg": (
            "radial-gradient(900px 620px at -8% -12%, "
            "light-dark(rgba(127,104,255,.20), rgba(120,101,255,.24)), transparent 64%),"
            "radial-gradient(760px 560px at 108% 8%, "
            "light-dark(rgba(44,196,220,.16), rgba(37,190,220,.15)), transparent 62%),"
            "radial-gradient(880px 620px at 52% 116%, "
            "light-dark(rgba(236,113,156,.12), rgba(218,79,136,.10)), transparent 64%),"
            "linear-gradient(145deg, "
            "light-dark(#F8F9FC, #05070B) 0%, "
            "light-dark(#EEF2F8, #090D14) 48%, "
            "light-dark(#F7F8FB, #06080D) 100%)"
        ),
        "orb_a": "light-dark(rgba(121,98,255,.16), rgba(138,121,255,.18))",
        "orb_b": "light-dark(rgba(30,185,210,.13), rgba(47,197,219,.12))",
    }
    return f"""
<style>
:root {{
  --lg-ink: {tokens["ink"]};
  --lg-muted: {tokens["muted"]};
  --lg-surface: {tokens["surface"]};
  --lg-surface-strong: {tokens["surface_strong"]};
  --lg-control: {tokens["control"]};
  --lg-border: {tokens["border"]};
  --lg-border-soft: {tokens["border_soft"]};
  --lg-highlight: {tokens["highlight"]};
  --lg-shadow: {tokens["shadow"]};
}}

.stApp {{
  color: var(--lg-ink);
  background: {tokens["bg"]};
  background-attachment: fixed;
}}

.stApp::before,
.stApp::after {{
  content: "";
  position: fixed;
  z-index: 0;
  width: min(34vw, 520px);
  aspect-ratio: 1;
  border-radius: 50%;
  filter: blur(78px);
  pointer-events: none;
  opacity: .72;
  will-change: transform;
}}

.stApp::before {{
  left: -15vw;
  top: 18vh;
  background: {tokens["orb_a"]};
  animation: lg-drift-a 18s ease-in-out infinite alternate;
}}

.stApp::after {{
  right: -16vw;
  bottom: 4vh;
  background: {tokens["orb_b"]};
  animation: lg-drift-b 22s ease-in-out infinite alternate;
}}

[data-testid="stMainBlockContainer"] {{
  position: relative;
  z-index: 1;
  max-width: 1680px;
  padding-bottom: 2.4rem;
  padding-inline: clamp(.9rem, 2.4vw, 2.4rem);
}}

.stApp p,
.stApp label,
.stApp [data-testid="stMarkdownContainer"] {{
  line-height: 1.52;
  letter-spacing: 0;
}}

.stApp h1,
.stApp h2,
.stApp h3,
.stApp h4 {{
  line-height: 1.18;
  text-wrap: balance;
}}

[data-testid="stHeader"] {{
  background: {tokens["header"]};
  backdrop-filter: blur(30px) saturate(165%);
  -webkit-backdrop-filter: blur(30px) saturate(165%);
  border-bottom: 1px solid var(--lg-border-soft);
}}

[data-testid="stSidebar"] > div:first-child {{
  background: linear-gradient(180deg, {tokens["sidebar_top"]}, {tokens["sidebar_bottom"]});
  backdrop-filter: blur(34px) saturate(165%);
  -webkit-backdrop-filter: blur(34px) saturate(165%);
  border-right: 1px solid var(--lg-border-soft);
}}

.st-key-hero {{
  position: relative;
  overflow: hidden;
  padding: 1rem 1.2rem .92rem;
  margin: 0 0 .9rem;
  border: 1px solid var(--lg-border);
  border-radius: 22px;
  background:
    linear-gradient(125deg, rgba(137, 113, 255, .16), rgba(52, 190, 214, .055) 58%, rgba(231, 92, 149, .065)),
    var(--lg-surface);
  box-shadow:
    0 18px 50px var(--lg-shadow),
    inset 0 1px 0 var(--lg-highlight);
  backdrop-filter: blur(32px) saturate(175%);
  -webkit-backdrop-filter: blur(32px) saturate(175%);
  animation: lg-enter .42s cubic-bezier(.2,.7,.2,1) both;
}}

.st-key-hero::after {{
  content: "";
  position: absolute;
  width: 180px;
  height: 180px;
  right: -78px;
  top: -98px;
  border-radius: 50%;
  background: linear-gradient(145deg, rgba(255,255,255,.18), rgba(255,255,255,.015));
  pointer-events: none;
}}

.st-key-hero h1 {{
  letter-spacing: -.025em;
  margin-bottom: .16rem;
}}

.st-key-hero p {{
  color: var(--lg-muted);
  max-width: 1040px;
  margin-bottom: .18rem;
  line-height: 1.5;
}}

[class*="st-key-glass-"] {{
  position: relative;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  border: 1px solid var(--lg-border);
  border-radius: 20px;
  background:
    linear-gradient(145deg, rgba(255,255,255,.055), rgba(255,255,255,.008)),
    var(--lg-surface);
  box-shadow:
    0 14px 38px var(--lg-shadow),
    inset 0 1px 0 var(--lg-highlight);
  backdrop-filter: blur(28px) saturate(165%);
  -webkit-backdrop-filter: blur(28px) saturate(165%);
  transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
  animation: lg-enter .38s cubic-bezier(.2,.7,.2,1) both;
  padding: 1rem 1.05rem 1.05rem;
  margin-block: .1rem .55rem;
}}

[class*="st-key-glass-"] [data-testid="stVerticalBlock"] {{
  min-width: 0;
}}

[class*="st-key-glass-"] h3 {{
  margin-bottom: .18rem;
}}

[class*="st-key-glass-"] [data-testid="stCaptionContainer"] {{
  margin-bottom: .22rem;
}}

@media (hover: hover) and (pointer: fine) {{
  [class*="st-key-glass-"]:hover {{
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--lg-border) 74%, #9E91FF 26%);
    box-shadow: 0 20px 48px var(--lg-shadow), inset 0 1px 0 var(--lg-highlight);
  }}
}}

[data-testid="stMetric"] {{
  min-width: 142px;
  min-height: 108px;
  padding: .92rem 1rem .86rem;
  border: 1px solid var(--lg-border) !important;
  border-radius: 18px !important;
  background:
    linear-gradient(145deg, rgba(255,255,255,.065), rgba(255,255,255,.012)),
    var(--lg-surface);
  box-shadow: 0 11px 30px var(--lg-shadow), inset 0 1px 0 var(--lg-highlight);
  backdrop-filter: blur(24px) saturate(165%);
  -webkit-backdrop-filter: blur(24px) saturate(165%);
  transition: transform .2s ease, box-shadow .2s ease;
}}

@media (hover: hover) and (pointer: fine) {{
  [data-testid="stMetric"]:hover {{
    transform: translateY(-2px) scale(1.006);
    box-shadow: 0 17px 38px var(--lg-shadow), inset 0 1px 0 var(--lg-highlight);
  }}
}}

[data-testid="stMetricLabel"] {{
  color: var(--lg-muted);
  font-size: .86rem;
  line-height: 1.35;
}}

[data-testid="stMetricValue"] {{
  color: var(--lg-ink);
  letter-spacing: -.025em;
  font-size: 1.62rem;
  line-height: 1.12;
  margin-top: .18rem;
  font-variant-numeric: tabular-nums;
}}

[data-testid="stMetricDelta"] {{
  font-size: .76rem;
  line-height: 1.35;
  margin-top: .18rem;
}}

[data-baseweb="select"] > div,
[data-testid="stTextInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stMultiSelect"] > div > div {{
  background: var(--lg-control);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}}

[data-testid="stDataFrame"],
[data-testid="stTable"],
[data-testid="stVegaLiteChart"] {{
  border-radius: 17px;
  overflow: hidden;
  background: var(--lg-surface);
  border: 1px solid var(--lg-border-soft);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  margin-block: .22rem .3rem;
}}

[data-testid="stDataFrame"] {{
  box-shadow: inset 0 1px 0 var(--lg-highlight);
}}

[data-testid="stVegaLiteChart"] {{
  padding: .35rem .45rem .28rem;
}}

[class*="st-key-glass-"] [data-testid="stVegaLiteChart"] {{
  background: transparent;
  border: 0;
  box-shadow: none;
  padding: .25rem 0 0;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}}

.st-key-metric-row {{
  width: 100%;
  align-items: stretch;
}}

.st-key-metric-row [data-testid="stMetric"] {{
  flex: 1 1 180px;
  min-width: 0;
}}

[data-testid="stCaptionContainer"] {{
  color: var(--lg-muted);
  font-size: .82rem;
  line-height: 1.45;
}}

.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {{
  box-shadow: inset 0 1px 0 rgba(255,255,255,.16), 0 8px 22px var(--lg-shadow);
  transition: transform .18s ease, box-shadow .18s ease;
}}

@media (hover: hover) and (pointer: fine) {{
  .stButton > button:hover,
  .stDownloadButton > button:hover,
  [data-testid="stFormSubmitButton"] > button:hover {{
    transform: translateY(-1px);
    box-shadow: inset 0 1px 0 rgba(255,255,255,.18), 0 12px 28px var(--lg-shadow);
  }}
}}

[data-testid="stExpander"],
[data-testid="stPopoverBody"],
[role="dialog"] {{
  border-color: var(--lg-border) !important;
  background: var(--lg-surface-strong);
  backdrop-filter: blur(30px) saturate(165%);
  -webkit-backdrop-filter: blur(30px) saturate(165%);
}}

[data-baseweb="tab-list"],
[data-testid="stSegmentedControl"] > div {{
  background: var(--lg-surface);
  border: 1px solid var(--lg-border);
  border-radius: 999px;
  padding: .2rem;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}}

@keyframes lg-enter {{
  from {{ opacity: 0; transform: translateY(7px) scale(.995); }}
  to {{ opacity: 1; transform: translateY(0) scale(1); }}
}}

@keyframes lg-drift-a {{
  from {{ transform: translate3d(0, -2vh, 0) scale(.96); }}
  to {{ transform: translate3d(18vw, 8vh, 0) scale(1.08); }}
}}

@keyframes lg-drift-b {{
  from {{ transform: translate3d(0, 0, 0) scale(1.06); }}
  to {{ transform: translate3d(-16vw, -9vh, 0) scale(.94); }}
}}

@media (max-width: 1024px) {{
  [data-testid="stMainBlockContainer"] {{
    padding-inline: 1rem;
    padding-bottom: 2rem;
  }}
  .st-key-hero {{ border-radius: 19px; }}
  [class*="st-key-glass-"] {{ padding: .9rem .92rem .95rem; }}
}}

@media (max-width: 720px) {{
  .stApp {{
    background-attachment: scroll;
  }}
  .stApp::before,
  .stApp::after {{
    animation: none;
    filter: blur(54px);
    opacity: .45;
  }}
  [data-testid="stMainBlockContainer"] {{
    padding-inline: .68rem;
    padding-bottom: 1.6rem;
  }}
  .st-key-hero {{ padding: .82rem .88rem .76rem; border-radius: 17px; }}
  .st-key-hero::after {{ width: 135px; height: 135px; }}
  [data-testid="stMetric"] {{
    min-height: 96px;
    padding: .72rem .78rem .7rem;
  }}
  [data-testid="stMetricValue"] {{ font-size: 1.38rem; }}
  [class*="st-key-glass-"] {{
    border-radius: 17px;
    padding: .82rem .78rem .88rem;
    margin-bottom: .65rem;
  }}
  [data-testid="stVegaLiteChart"] {{ padding: .2rem .18rem .18rem; }}
}}

@media (max-width: 520px) {{
  .st-key-metric-row [data-testid="stMetric"] {{
    flex-basis: 100%;
  }}
}}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
    transition-duration: .01ms !important;
  }}
}}
</style>
"""


def inject_liquid_glass() -> None:
    """Apply theme-aware glass effects on top of Streamlit's native theme."""
    st.html(_liquid_glass_css())


def page_header(
    title: str,
    subtitle: str,
    icon: str,
    *,
    data: Any | None = None,
) -> None:
    with st.container(key="hero", gap="xxsmall"):
        st.title(f":material/{icon}: {title}")
        st.write(subtitle)
        if data is not None:
            with st.container(horizontal=True, vertical_alignment="center", gap="xsmall"):
                source_color = "green" if data.source_mode.startswith("Live") else "orange"
                st.badge(
                    data.source_mode,
                    icon=":material/cloud_done:" if source_color == "green" else ":material/cloud_off:",
                    color=source_color,
                )
                loaded = data.loaded_at.astimezone(timezone.utc).strftime("%d %b %Y · %H:%M UTC")
                st.caption(f"Refreshed {loaded}")


def metric_row(metrics: list[dict[str, Any]]) -> None:
    with st.container(horizontal=True, gap="small", key="metric-row"):
        for metric in metrics:
            st.metric(
                metric["label"],
                metric["value"],
                metric.get("delta"),
                delta_color=metric.get("delta_color", "normal"),
                delta_arrow=metric.get("delta_arrow", "auto"),
                help=metric.get("help"),
                format=metric.get("format"),
                border=True,
                chart_data=metric.get("chart_data"),
                chart_type=metric.get("chart_type", "line"),
            )


def glass_section(
    title: str,
    *,
    subtitle: str | None = None,
    icon: str = "analytics",
    key: str,
    height: int | str = "content",
):
    container = st.container(
        border=False,
        key=f"glass-{key}",
        height=height,
        gap="small",
    )
    container.subheader(f":material/{icon}: {title}")
    if subtitle:
        container.caption(subtitle)
    return container


def dataframe_download(
    frame: pd.DataFrame,
    *,
    label: str,
    file_name: str,
    key: str,
) -> None:
    st.download_button(
        label,
        frame.to_csv(index=False).encode("utf-8-sig"),
        file_name=file_name,
        mime="text/csv",
        icon=":material/download:",
        key=key,
        type="tertiary",
    )


def empty_state(message: str, *, icon: str = "inbox") -> None:
    st.info(message, icon=f":material/{icon}:")
