from __future__ import annotations

import pandas as pd
import streamlit as st

from src.charts import donut_chart, stacked_status_bar
from src.ui import dataframe_download, empty_state, glass_section, metric_row, page_header


data = st.session_state["app_data"]
full_data = st.session_state["full_app_data"]

page_header(
    "Data quality",
    "Identifier integrity, QA, correction traceability and coverage exceptions.",
    "fact_check",
    data=data,
)

all_form_rows = (
    pd.concat(full_data.forms.values(), ignore_index=True)
    if full_data.forms
    else pd.DataFrame()
)
missing_wob = (
    int((all_form_rows["_wob_key"] == "").sum())
    if not all_form_rows.empty
    else 0
)
orphans = (
    int((~all_form_rows["_wob_key"].isin(set(full_data.sample["_wob_key"]))).sum())
    if not all_form_rows.empty
    else 0
)
duplicate_sample = int(full_data.sample["_wob_key"].duplicated().sum())
duplicate_submissions = (
    int(
        all_form_rows.duplicated(
            ["_form_code", "_wob_key"], keep=False
        ).sum()
    )
    if not all_form_rows.empty
    else 0
)
missing_expected = int((full_data.coverage["Status"] == "Missing").sum())

metric_row(
    [
        {
            "label": "Invalid identifiers",
            "value": missing_wob + orphans,
            "help": "Missing IDs plus IDs outside Sample_Track.",
        },
        {
            "label": "Duplicate records",
            "value": duplicate_sample + duplicate_submissions,
        },
        {"label": "Coverage gaps", "value": missing_expected},
        {
            "label": "Corrections applied",
            "value": full_data.correction_stats["applied"],
            "help": "Cells resolved by form, key and field.",
        },
    ]
)

view = st.segmented_control(
    "Quality view",
    ["Integrity", "Corrections", "Coverage"],
    default="Integrity",
    key="quality_view",
)

if view == "Integrity":
    left, right = st.columns([1.15, 0.85], vertical_alignment="top")
    with left:
        section = glass_section(
            "QA status",
            subtitle="Latest QA_Log status for beneficiaries matching active filters.",
            icon="verified",
            key="quality-qa",
        )
        if "QA Status" not in data.qa or data.qa.empty:
            with section:
                empty_state("No QA records match the active filters.")
        else:
            qa_status = (
                data.qa["QA Status"]
                .fillna("Not reviewed")
                .astype(str)
                .value_counts()
                .rename_axis("QA status")
                .reset_index(name="Records")
            )
            section.altair_chart(
                donut_chart(
                    qa_status,
                    "QA status",
                    "Records",
                    height=325,
                ),
                key="quality_qa_chart",
            )

    with right:
        section = glass_section(
            "Integrity checks",
            subtitle="Deterministic validation across source tables.",
            icon="shield",
            key="quality-integrity-checks",
        )
        checks = pd.DataFrame(
            {
                "Check": [
                    "Missing WOB ID",
                    "Outside Sample_Track",
                    "Duplicate Sample_Track ID",
                    "Duplicate form + WOB",
                ],
                "Records": [
                    missing_wob,
                    orphans,
                    duplicate_sample,
                    duplicate_submissions,
                ],
            }
        )
        section.dataframe(
            checks,
            hide_index=True,
            height=325,
            row_height=40,
            key="quality_integrity_table",
            column_config={
                "Check": st.column_config.TextColumn(width="large"),
                "Records": st.column_config.NumberColumn(format="%,d"),
            },
        )

elif view == "Corrections":
    logs = []
    for source_name, frame in (
        ("Correction_Log", full_data.correction_log),
        ("Corrections", full_data.corrections),
    ):
        if frame.empty:
            continue
        item = frame.copy()
        item["Source"] = source_name
        logs.append(item)
    correction_audit = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame()
    if not correction_audit.empty:
        correction_audit = correction_audit[
            correction_audit["New Value"].notna()
        ].copy()

    left, right = st.columns([1.25, 0.75], vertical_alignment="top")
    with left:
        section = glass_section(
            "Correction audit trail",
            subtitle="Actionable entries from both correction sources.",
            icon="history",
            key="quality-corrections",
        )
        with section:
            if correction_audit.empty:
                empty_state("No actionable correction entries were found.")
            else:
                st.dataframe(
                    correction_audit,
                    hide_index=True,
                    height=390,
                    row_height=40,
                    key="quality_correction_table",
                    column_config={
                        "KEY": st.column_config.TextColumn(width="large"),
                        "Old Value": st.column_config.TextColumn(width="large"),
                        "New Value": st.column_config.TextColumn(width="large"),
                    },
                )
                dataframe_download(
                    correction_audit,
                    label="Download correction audit",
                    file_name="un_women_correction_audit.csv",
                    key="download_correction_audit",
                )

    with right:
        section = glass_section(
            "Resolution",
            subtitle="Matching outcomes at field level.",
            icon="find_replace",
            key="quality-correction-stats",
        )
        resolution = pd.DataFrame(
            {
                "Outcome": [
                    "Applied cells",
                    "Unmatched keys",
                    "Unmatched fields",
                    "Blank / unavailable",
                ],
                "Count": [
                    full_data.correction_stats["applied"],
                    full_data.correction_stats["unmatched_key"],
                    full_data.correction_stats["unmatched_field"],
                    full_data.correction_stats["skipped"],
                ],
            }
        )
        section.dataframe(
            resolution,
            hide_index=True,
            height=390,
            row_height=40,
            key="quality_correction_stats",
        )

else:
    exceptions = full_data.coverage[
        full_data.coverage["Status"].isin(["Missing", "Unexpected"])
    ]
    exception_counts = (
        exceptions.groupby(["Form", "Status"], observed=True)
        .size()
        .reset_index(name="Beneficiaries")
    )
    section = glass_section(
        "Coverage exceptions",
        subtitle="Missing or unexpected beneficiary-form combinations.",
        icon="rule_folder",
        key="quality-coverage",
    )
    if exception_counts.empty:
        with section:
            st.success("No coverage exceptions.", icon=":material/check_circle:")
    else:
        section.altair_chart(
            stacked_status_bar(
                exception_counts,
                "Form",
                "Status",
                "Beneficiaries",
                height=300,
            ),
            key="quality_coverage_chart",
        )

    register = exceptions[
        ["WOB ID", "Beneficiary Name", "Province", "District", "Form", "Status"]
    ].sort_values(["Status", "Province", "Beneficiary Name", "Form"])
    detail = st.expander(
        f"Exception register · {len(register):,}",
        icon=":material/report_problem:",
        on_change="rerun",
    )
    if detail.open:
        with detail:
            st.dataframe(
                register,
                hide_index=True,
                row_height=40,
                key="quality_exception_table",
                column_config={
                    "WOB ID": st.column_config.TextColumn(
                        "Unique WOB ID", pinned=True
                    ),
                    "Beneficiary Name": st.column_config.TextColumn(pinned=True),
                },
            )
            dataframe_download(
                register,
                label="Download exception register",
                file_name="un_women_data_quality_exceptions.csv",
                key="download_quality_exceptions",
            )
