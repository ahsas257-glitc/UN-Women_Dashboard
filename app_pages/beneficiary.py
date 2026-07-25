from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import categorical_bar
from src.config import FORM_TITLES, TRACKED_FORMS
from src.ui import dataframe_download, empty_state, glass_section, metric_row, page_header


filtered = st.session_state["app_data"]
full_data = st.session_state["full_app_data"]

page_header(
    "Beneficiary 360",
    "One authoritative participant profile joined across questionnaires by Unique WOB ID.",
    "person_search",
    data=filtered,
)

source_sample = filtered.sample if not filtered.sample.empty else full_data.sample
options = list(source_sample["_wob_key"])
labels = {
    row["_wob_key"]: f"{row['WOB ID']} · {row['Beneficiary Name']}"
    for _, row in source_sample.iterrows()
}
global_keys = st.session_state.get("global_wob_keys", [])
default_index = (
    options.index(global_keys[0])
    if global_keys and global_keys[0] in options
    else 0
)

if not options:
    empty_state("No beneficiary matches the active filters.", icon="person_off")
    st.stop()

wob_key = st.selectbox(
    "Select beneficiary",
    options,
    index=default_index,
    format_func=lambda value: labels[value],
    key="beneficiary_360_selector",
)
person = full_data.sample[full_data.sample["_wob_key"] == wob_key].iloc[0]
coverage = full_data.coverage[full_data.coverage["_wob_key"] == wob_key].copy()
scores = full_data.score_long[full_data.score_long["_wob_key"] == wob_key].copy()

metric_row(
    [
        {"label": "Unique WOB ID", "value": str(person["WOB ID"])},
        {
            "label": "Location",
            "value": f"{person['Province']} · {person['District']}",
        },
        {"label": "Assigned to", "value": str(person["Assigned_to"])},
        {
            "label": "Expected complete",
            "value": (
                f"{coverage.loc[coverage['Expected'], 'Submitted'].sum():.0f} / "
                f"{coverage['Expected'].sum():.0f}"
            ),
        },
    ]
)

identity = st.expander(
    "Sample_Track identity",
    icon=":material/badge:",
    on_change="rerun",
)
if identity.open:
    with identity:
        details = pd.DataFrame(
            {
                "Field": [
                    "Beneficiary name",
                    "Unique WOB ID",
                    "Province",
                    "District",
                    "Assigned to",
                    "Remark",
                ],
                "Value": [
                    person["Beneficiary Name"],
                    person["WOB ID"],
                    person["Province"],
                    person["District"],
                    person["Assigned_to"],
                    person.get("Remark"),
                ],
            }
        )
        st.dataframe(
            details,
            hide_index=True,
            row_height=40,
            key="beneficiary_identity_table",
        )

view = st.segmented_control(
    "Beneficiary view",
    ["Journey", "Readiness", "Submissions"],
    default="Journey",
    key="beneficiary_view",
)

if view == "Journey":
    section = glass_section(
        "Form journey",
        subtitle="Expected assignment compared with observed submission.",
        icon="route",
        key="beneficiary-journey",
    )
    journey_table = coverage[["Form", "Expected", "Submitted", "Status"]].copy()
    journey_table["Form title"] = journey_table["Form"].map(FORM_TITLES)
    section.dataframe(
        journey_table,
        hide_index=True,
        row_height=40,
        key="beneficiary_journey_table",
        column_config={
            "Expected": st.column_config.CheckboxColumn(),
            "Submitted": st.column_config.CheckboxColumn(),
            "Status": st.column_config.TextColumn(pinned=True),
            "Form title": st.column_config.TextColumn(width="large"),
        },
    )

elif view == "Readiness":
    left, right = st.columns([0.9, 1.1], vertical_alignment="top")
    with left:
        section = glass_section(
            "Module readiness",
            subtitle="Mean scored items by questionnaire module.",
            icon="speed",
            key="beneficiary-readiness",
        )
        if scores.empty:
            with section:
                empty_state("No capacity scores are available.")
        else:
            module = (
                scores.groupby("Form", observed=True)["Score"]
                .mean()
                .reset_index(name="Average score")
            )
            module["Form"] = pd.Categorical(
                module["Form"], TRACKED_FORMS, ordered=True
            )
            section.altair_chart(
                categorical_bar(
                    module.sort_values("Form"),
                    "Form",
                    "Average score",
                    horizontal=True,
                    height=345,
                ),
                key="beneficiary_readiness_chart",
            )

    with right:
        section = glass_section(
            "Priority learning needs",
            subtitle="Lowest-scoring analytical items across completed capacity forms.",
            icon="priority_high",
            key="beneficiary-priority",
        )
        if scores.empty:
            with section:
                empty_state("No scored learning needs are available.")
        else:
            priority = (
                scores.groupby(["Form", "Question"], observed=True)["Score"]
                .mean()
                .reset_index()
                .sort_values("Score")
                .head(12)
            )
            priority["Question"] = priority["Question"].str.slice(0, 120)
            section.dataframe(
                priority,
                hide_index=True,
                height=345,
                row_height=42,
                key="beneficiary_priority_table",
                column_config={
                    "Question": st.column_config.TextColumn(width="large"),
                    "Score": st.column_config.ProgressColumn(
                        min_value=0,
                        max_value=2,
                        format="%.2f / 2",
                    ),
                },
            )

else:
    section = glass_section(
        "Cross-form submissions",
        subtitle="Submission-level lineage for the selected Unique WOB ID.",
        icon="dataset",
        key="beneficiary-submissions",
    )
    submission_rows = []
    for code, frame in full_data.forms.items():
        subset = frame[frame["_wob_key"] == wob_key]
        round_column = next(
            (
                column
                for column in frame.columns
                if str(column).casefold() == "assessment round"
            ),
            None,
        )
        for _, row in subset.iterrows():
            submission_rows.append(
                {
                    "Form": code,
                    "Form title": FORM_TITLES[code],
                    "Assessment round": (
                        row.get(round_column) if round_column else None
                    ),
                    "Submission time": row.get("_submission_time"),
                    "Submission UUID": (
                        row.get("_uuid") or row.get("submission_uuid")
                    ),
                }
            )
    submissions = pd.DataFrame(submission_rows)
    with section:
        if submissions.empty:
            empty_state("No form submissions were found for this Unique WOB ID.")
        else:
            st.dataframe(
                submissions.sort_values(["Form", "Submission time"]),
                hide_index=True,
                row_height=40,
                key="beneficiary_submissions_table",
                column_config={
                    "Form title": st.column_config.TextColumn(width="large"),
                    "Submission time": st.column_config.DatetimeColumn(
                        format="DD MMM YYYY, HH:mm"
                    ),
                    "Submission UUID": st.column_config.TextColumn(width="large"),
                },
            )
            dataframe_download(
                submissions,
                label="Download submission index",
                file_name=f"{person['WOB ID']}_submission_index.csv",
                key="download_beneficiary_index",
            )
