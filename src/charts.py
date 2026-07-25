from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st


LIGHT_PALETTE = {
    "purple": "#6558D9",
    "cyan": "#168FB4",
    "green": "#16805D",
    "pink": "#C84B71",
    "amber": "#B97711",
    "blue": "#2764D8",
    "rose": "#D83B52",
    "muted": "#667085",
    "ink": "#0A0D14",
}
DARK_PALETTE = {
    "purple": "#B4A7FF",
    "cyan": "#5AD8F2",
    "green": "#59D9A5",
    "pink": "#FF7FAD",
    "amber": "#FFD166",
    "blue": "#75A7FF",
    "rose": "#FF7F9E",
    "muted": "#AAB2C2",
    "ink": "#F8FAFF",
}


def chart_palette() -> dict[str, str]:
    """Return accessible chart colors for Streamlit's active native theme."""
    try:
        is_dark = st.context.theme.type == "dark"
    except Exception:
        is_dark = False
    return DARK_PALETTE if is_dark else LIGHT_PALETTE


def liquid_colors() -> list[str]:
    palette = chart_palette()
    return [
        palette["purple"],
        palette["cyan"],
        palette["green"],
        palette["pink"],
        palette["amber"],
        palette["blue"],
        palette["rose"],
    ]


def liquid_chart(chart: alt.Chart) -> alt.Chart:
    """Give Altair charts a transparent, spacious surface in both themes."""
    return (
        chart.properties(background="transparent")
        .configure_view(fill="transparent", strokeOpacity=0)
        .configure_axis(
            labelFontSize=12,
            titleFontSize=12,
            labelPadding=8,
            titlePadding=12,
            gridOpacity=0.14,
            ticks=False,
            domain=False,
        )
        .configure_legend(
            labelFontSize=12,
            titleFontSize=12,
            labelLimit=240,
            padding=8,
            symbolType="circle",
        )
    )


def categorical_bar(
    frame: pd.DataFrame,
    category: str,
    value: str,
    *,
    title: str | None = None,
    horizontal: bool = False,
    color: str | None = None,
    height: int = 320,
    value_format: str = ",",
) -> alt.Chart:
    color = color or chart_palette()["purple"]
    tooltip = [
        alt.Tooltip(f"{category}:N", title=category),
        alt.Tooltip(f"{value}:Q", title=value, format=value_format),
    ]
    if horizontal:
        encoding = {
            "y": alt.Y(
                f"{category}:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=285),
            ),
            "x": alt.X(f"{value}:Q", title=None),
        }
    else:
        encoding = {
            "x": alt.X(f"{category}:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-25)),
            "y": alt.Y(f"{value}:Q", title=None),
        }
    chart = alt.Chart(frame)
    if title:
        chart = chart.properties(title=title)
    return liquid_chart(
        chart
        .mark_bar(color=color, cornerRadiusEnd=7)
        .encode(**encoding, tooltip=tooltip)
        .properties(height=height)
    )


def stacked_status_bar(
    frame: pd.DataFrame,
    category: str,
    status: str,
    value: str,
    *,
    height: int = 320,
) -> alt.Chart:
    palette = chart_palette()
    chart_data = frame.copy()
    totals = chart_data.groupby(category, observed=True)[value].transform("sum")
    chart_data["Share"] = chart_data[value] / totals.clip(lower=1)
    scale = alt.Scale(
        domain=["Complete", "Missing", "Unexpected", "Not assigned"],
        range=[
            palette["green"],
            palette["rose"],
            palette["amber"],
            palette["muted"],
        ],
    )
    return liquid_chart(
        alt.Chart(chart_data)
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            y=alt.Y(f"{category}:N", title=None, sort=None),
            x=alt.X(
                f"{value}:Q",
                title="Share of assignments",
                stack="normalize",
                axis=alt.Axis(format="%"),
            ),
            color=alt.Color(f"{status}:N", title=None, scale=scale),
            tooltip=[
                alt.Tooltip(f"{category}:N", title="Form"),
                alt.Tooltip(f"{status}:N", title="Status"),
                alt.Tooltip(f"{value}:Q", title="Count"),
                alt.Tooltip("Share:Q", title="Share", format=".1%"),
            ],
        )
        .properties(height=height)
    )


def donut_chart(
    frame: pd.DataFrame,
    category: str,
    value: str,
    *,
    height: int = 320,
) -> alt.Chart:
    palette = chart_palette()
    total = float(pd.to_numeric(frame[value], errors="coerce").fillna(0).sum())
    arc = (
        alt.Chart(frame)
        .mark_arc(
            innerRadius=66,
            outerRadius=112,
            cornerRadius=7,
            padAngle=0.018,
            strokeWidth=0,
        )
        .encode(
            theta=alt.Theta(f"{value}:Q", stack=True),
            color=alt.Color(
                f"{category}:N",
                title=None,
                scale=alt.Scale(range=liquid_colors()),
            ),
            tooltip=[
                alt.Tooltip(f"{category}:N", title=category),
                alt.Tooltip(f"{value}:Q", title=value, format=","),
            ],
        )
    )
    center = (
        alt.Chart(pd.DataFrame({"label": [f"{total:,.0f}"], "sub": ["records"]}))
        .mark_text(fontSize=24, fontWeight=700, color=palette["ink"])
        .encode(text="label:N")
    )
    subtitle = (
        alt.Chart(pd.DataFrame({"label": [f"{total:,.0f}"], "sub": ["records"]}))
        .mark_text(fontSize=11, dy=22, opacity=0.72, color=palette["muted"])
        .encode(text="sub:N")
    )
    return liquid_chart((arc + center + subtitle).properties(height=height))


def score_distribution(frame: pd.DataFrame, *, height: int = 300) -> alt.Chart:
    palette = chart_palette()
    data = frame.copy()
    data["Score label"] = data["Score"].map(
        {0.0: "0 · Limited", 1.0: "1 · Developing", 2.0: "2 · Operational"}
    ).fillna(data["Score"].astype(str))
    counts = data.groupby(["Form", "Score label"], observed=True).size().reset_index(name="Responses")
    return liquid_chart(
        alt.Chart(counts)
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            y=alt.Y("Form:N", title=None, sort=None),
            x=alt.X("Responses:Q", title="Scored responses", stack="normalize", axis=alt.Axis(format="%")),
            color=alt.Color(
                "Score label:N",
                title=None,
                scale=alt.Scale(
                    domain=["0 · Limited", "1 · Developing", "2 · Operational"],
                    range=[
                        palette["rose"],
                        palette["amber"],
                        palette["green"],
                    ],
                ),
            ),
            tooltip=["Form:N", "Score label:N", "Responses:Q"],
        )
        .properties(height=height)
    )


def module_score_bar(frame: pd.DataFrame, *, height: int = 310) -> alt.Chart:
    palette = chart_palette()
    module = frame.groupby(["Form", "Module"], observed=True)["Score"].mean().reset_index()
    module["Gap to target"] = 2 - module["Score"]
    return liquid_chart(
        alt.Chart(module)
        .mark_bar(cornerRadiusEnd=8)
        .encode(
            y=alt.Y("Form:N", title=None, sort="-x"),
            x=alt.X("Score:Q", title="Average score (0–2)", scale=alt.Scale(domain=[0, 2])),
            color=alt.Color(
                "Score:Q",
                legend=None,
                scale=alt.Scale(
                    domain=[0, 1, 2],
                    range=[palette["rose"], palette["amber"], palette["green"]],
                ),
            ),
            tooltip=[
                "Form:N",
                alt.Tooltip("Module:N", title="Module"),
                alt.Tooltip("Score:Q", title="Average", format=".2f"),
                alt.Tooltip("Gap to target:Q", format=".2f"),
            ],
        )
        .properties(height=height)
    )


def item_gap_bar(frame: pd.DataFrame, *, limit: int = 12, height: int = 420) -> alt.Chart:
    palette = chart_palette()
    gaps = (
        frame.groupby(["Form", "Question"], observed=True)["Score"]
        .mean()
        .reset_index()
    )
    gaps["Gap"] = 2 - gaps["Score"]
    gaps["Item"] = gaps["Form"] + " · " + gaps["Question"].str.slice(0, 82)
    gaps = gaps.nlargest(limit, "Gap").sort_values("Gap")
    base = alt.Chart(gaps).encode(
        y=alt.Y(
            "Item:N",
            title=None,
            sort=None,
            axis=alt.Axis(labelLimit=360),
        ),
        x=alt.X(
            "Gap:Q",
            title="Gap to operational target",
            scale=alt.Scale(domain=[0, 2]),
        ),
        tooltip=[
            "Form:N",
            alt.Tooltip("Question:N", title="Question"),
            alt.Tooltip("Score:Q", title="Average score", format=".2f"),
            alt.Tooltip("Gap:Q", format=".2f"),
        ],
    )
    stems = base.mark_bar(size=3, color=palette["purple"], opacity=0.48)
    points = base.mark_circle(size=115).encode(
        color=alt.Color(
            "Gap:Q",
            title="Gap",
            scale=alt.Scale(
                domain=[0, 1, 2],
                range=[palette["cyan"], palette["purple"], palette["rose"]],
            ),
        )
    )
    return liquid_chart((stems + points).properties(height=height))


def heatmap(
    frame: pd.DataFrame,
    x: str,
    y: str,
    value: str,
    *,
    height: int = 360,
) -> alt.Chart:
    palette = chart_palette()
    return liquid_chart(
        alt.Chart(frame)
        .mark_rect(cornerRadius=4)
        .encode(
            x=alt.X(f"{x}:N", title=None),
            y=alt.Y(f"{y}:N", title=None),
            color=alt.Color(
                f"{value}:Q",
                title=value,
                scale=alt.Scale(
                    domain=[0, 1, 2],
                    range=[
                        palette["rose"],
                        palette["amber"],
                        palette["green"],
                    ],
                ),
            ),
            tooltip=[
                alt.Tooltip(f"{x}:N"),
                alt.Tooltip(f"{y}:N"),
                alt.Tooltip(f"{value}:Q", format=".2f"),
            ],
        )
        .properties(height=height)
    )
