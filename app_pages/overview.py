from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from src.charts import (
    chart_palette,
    heatmap,
    item_gap_bar,
    liquid_chart,
    module_score_bar,
    stacked_status_bar,
)
from src.config import FORM_TITLES
from src.ui import dataframe_download, empty_state, glass_section, metric_row, page_header


data = st.session_state["app_data"]

page_header(
    "Programme overview",
    "A compact decision view of participation, delivery and capacity joined by Unique WOB ID.",
    "space_dashboard",
    data=data,
)

expected = data.coverage[data.coverage["Expected"]]
completed = int(expected["Submitted"].sum())
completion_rate = completed / len(expected) if len(expected) else 0
average_score = data.score_long["Score"].mean() if not data.score_long.empty else float("nan")
submission_count = sum(len(frame) for frame in data.forms.values())

metric_row(
    [
        {
            "label": "Beneficiaries",
            "value": len(data.sample),
            "help": "Unique records from Sample_Track after active filters.",
        },
        {
            "label": "Submissions",
            "value": submission_count,
        },
        {
            "label": "Completion",
            "value": completion_rate,
            "format": "percent",
            "delta": f"{completed:,} of {len(expected):,}",
            "delta_color": "off",
            "delta_arrow": "off",
        },
        {
            "label": "Average score",
            "value": None if pd.isna(average_score) else f"{average_score:.2f} / 2",
        },
    ]
)

lens = st.segmented_control(
    "Analysis lens",
    ["Executive", "Geography", "Cohorts"],
    default="Executive",
    key="overview_lens",
)

if lens == "Executive":
    left, right = st.columns(2, vertical_alignment="top")
    with left:
        section = glass_section(
            "Form completion",
            subtitle="Expected assignments by current status.",
            icon="task_alt",
            key="overview-coverage",
        )
        status = (
            data.coverage.groupby(["Form", "Status"], observed=True)
            .size()
            .reset_index(name="Beneficiaries")
        )
        status["Form"] = pd.Categorical(
            status["Form"],
            categories=[code for code in FORM_TITLES if code in set(status["Form"])],
            ordered=True,
        )
        if status.empty:
            with section:
                empty_state("No coverage records match the active filters.")
        else:
            section.altair_chart(
                stacked_status_bar(
                    status,
                    "Form",
                    "Status",
                    "Beneficiaries",
                    height=280,
                ),
                key="overview_coverage_chart",
            )

    with right:
        section = glass_section(
            "Capacity by module",
            subtitle="Average standardized score from 0 to 2.",
            icon="bar_chart",
            key="overview-module",
        )
        if data.score_long.empty:
            with section:
                empty_state("No scored responses match the active filters.")
        else:
            section.altair_chart(
                module_score_bar(data.score_long, height=280),
                key="overview_module_chart",
            )

    section = glass_section(
        "Priority capacity gaps",
        subtitle="The ten items furthest from the operational target.",
        icon="trending_down",
        key="overview-gaps",
    )
    if data.score_long.empty:
        with section:
            empty_state("No scored items are available.")
    else:
        section.altair_chart(
            item_gap_bar(data.score_long, limit=10, height=350),
            key="overview_gap_chart",
        )

    watchlist = data.coverage[data.coverage["Status"] == "Missing"][
        ["WOB ID", "Beneficiary Name", "Province", "District", "Form"]
    ].sort_values(["Province", "Beneficiary Name", "Form"])
    if not watchlist.empty:
        watchlist_expander = st.expander(
            f"Missing expected forms · {len(watchlist):,}",
            icon=":material/notification_important:",
            on_change="rerun",
        )
        if watchlist_expander.open:
            with watchlist_expander:
                st.dataframe(
                    watchlist,
                    hide_index=True,
                    row_height=40,
                    key="overview_watchlist_table",
                    column_config={
                        "WOB ID": st.column_config.TextColumn(
                            "Unique WOB ID", pinned=True
                        ),
                        "Beneficiary Name": st.column_config.TextColumn(pinned=True),
                    },
                )
                dataframe_download(
                    watchlist,
                    label="Download watchlist",
                    file_name="un_women_missing_forms_watchlist.csv",
                    key="download_overview_watchlist",
                )

elif lens == "Geography":
    beneficiary_by_province = (
        data.sample.groupby("Province", dropna=False)
        .size()
        .rename("Beneficiaries")
        .reset_index()
    )
    expected_geo = data.coverage[data.coverage["Expected"]].copy()
    completion_geo = (
        expected_geo.groupby("Province", dropna=False)
        .agg(Expected=("Expected", "size"), Completed=("Submitted", "sum"))
        .reset_index()
    )
    completion_geo["Completion"] = (
        completion_geo["Completed"] / completion_geo["Expected"].clip(lower=1)
    )
    score_geo = (
        data.score_long.groupby("Province", dropna=False)["Score"]
        .mean()
        .rename("Average score")
        .reset_index()
        if not data.score_long.empty
        else pd.DataFrame(columns=["Province", "Average score"])
    )
    province_summary = (
        beneficiary_by_province.merge(completion_geo, on="Province", how="left")
        .merge(score_geo, on="Province", how="left")
        .fillna({"Expected": 0, "Completed": 0, "Completion": 0})
    )

    if province_summary.empty:
        empty_state("No geographic records match the active filters.")
    else:
        palette = chart_palette()
        ranked = province_summary[province_summary["Expected"] > 0].sort_values(
            "Completion", ascending=False
        )
        if not ranked.empty:
            with st.container(horizontal=True, gap="xsmall"):
                st.badge(
                    f"Highest completion · {ranked.iloc[0]['Province']}",
                    icon=":material/trending_up:",
                    color="green",
                )
                st.badge(
                    f"Needs attention · {ranked.iloc[-1]['Province']}",
                    icon=":material/priority_high:",
                    color="orange",
                )

        left, right = st.columns([1.05, 0.95], vertical_alignment="top")
        with left:
            section = glass_section(
                "Completion by province",
                subtitle="Completed expected forms as a share of assignments.",
                icon="location_on",
                key="overview-province-completion",
            )
            completion_chart = (
                alt.Chart(province_summary)
                .mark_bar(cornerRadiusEnd=7)
                .encode(
                    y=alt.Y("Province:N", sort="-x", title=None),
                    x=alt.X(
                        "Completion:Q",
                        title="Completion",
                        axis=alt.Axis(format="%"),
                        scale=alt.Scale(domain=[0, 1]),
                    ),
                    color=alt.Color(
                        "Completion:Q",
                        legend=None,
                        scale=alt.Scale(
                            domain=[0, 0.6, 1],
                            range=[
                                palette["rose"],
                                palette["amber"],
                                palette["green"],
                            ],
                        ),
                    ),
                    tooltip=[
                        "Province:N",
                        alt.Tooltip("Beneficiaries:Q", format=","),
                        alt.Tooltip("Completed:Q", format=","),
                        alt.Tooltip("Expected:Q", format=","),
                        alt.Tooltip("Completion:Q", format=".1%"),
                    ],
                )
                .properties(height=330)
            )
            section.altair_chart(
                liquid_chart(completion_chart),
                key="overview_province_completion_chart",
            )

        with right:
            section = glass_section(
                "Reach and readiness",
                subtitle="Cohort size, completion and average capacity score.",
                icon="bubble_chart",
                key="overview-province-scatter",
            )
            scatter = (
                alt.Chart(province_summary)
                .mark_circle(
                    opacity=0.86,
                    size=190,
                    stroke=palette["ink"],
                    strokeWidth=0.55,
                )
                .encode(
                    x=alt.X("Beneficiaries:Q", title="Beneficiaries"),
                    y=alt.Y(
                        "Completion:Q",
                        title="Completion",
                        axis=alt.Axis(format="%"),
                        scale=alt.Scale(domain=[0, 1]),
                    ),
                    color=alt.Color(
                        "Average score:Q",
                        title="Score",
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
                        "Province:N",
                        alt.Tooltip("Beneficiaries:Q", format=","),
                        alt.Tooltip("Completion:Q", format=".1%"),
                        alt.Tooltip("Average score:Q", format=".2f"),
                    ],
                )
                .properties(height=330)
            )
            section.altair_chart(
                liquid_chart(scatter),
                key="overview_province_scatter_chart",
            )

        detail = st.expander(
            "Province detail",
            icon=":material/table_view:",
            on_change="rerun",
        )
        if detail.open:
            with detail:
                st.dataframe(
                    province_summary.sort_values("Completion", ascending=False),
                    hide_index=True,
                    row_height=40,
                    key="overview_province_table",
                    column_config={
                        "Completion": st.column_config.ProgressColumn(
                            min_value=0,
                            max_value=1,
                            format="percent",
                        ),
                        "Average score": st.column_config.ProgressColumn(
                            min_value=0,
                            max_value=2,
                            format="%.2f / 2",
                        ),
                    },
                )

else:
    dimension = st.segmented_control(
        "Compare cohorts by",
        ["Assigned to", "Assessment Round", "Province"],
        default="Assigned to",
        key="overview_cohort_dimension",
    )
    scored = data.score_long.dropna(subset=[dimension, "Score"]).copy()
    if scored.empty:
        empty_state(f"No scored records are available for {dimension.lower()}.")
    else:
        scored[dimension] = scored[dimension].astype(str)
        cohort_summary = (
            scored.groupby(dimension, observed=True)
            .agg(
                Beneficiaries=("_wob_key", "nunique"),
                Responses=("Score", "size"),
                **{"Average score": ("Score", "mean")},
            )
            .reset_index()
            .sort_values("Average score", ascending=False)
        )
        comparison = (
            scored.groupby([dimension, "Form"], observed=True)["Score"]
            .mean()
            .reset_index(name="Average score")
        )

        left, right = st.columns([1.3, 0.7], vertical_alignment="top")
        with left:
            section = glass_section(
                "Capacity comparison",
                subtitle=f"Average module score by {dimension.lower()}.",
                icon="grid_view",
                key="overview-cohort-heatmap",
            )
            section.altair_chart(
                heatmap(
                    comparison,
                    "Form",
                    dimension,
                    "Average score",
                    height=max(260, min(520, len(cohort_summary) * 34 + 80)),
                ),
                key="overview_cohort_heatmap_chart",
            )

        with right:
            section = glass_section(
                "Cohort summary",
                subtitle="Reach, evidence volume and readiness.",
                icon="groups",
                key="overview-cohort-summary",
            )
            section.dataframe(
                cohort_summary,
                hide_index=True,
                height=max(260, min(520, len(cohort_summary) * 34 + 80)),
                row_height=40,
                key="overview_cohort_summary_table",
                column_config={
                    dimension: st.column_config.TextColumn(pinned=True),
                    "Average score": st.column_config.ProgressColumn(
                        min_value=0,
                        max_value=2,
                        format="%.2f / 2",
                    ),
                },
            )
