from __future__ import annotations

import re

import altair as alt
import pandas as pd
import streamlit as st

from src.catalog import analytic_questions, load_catalog, normalize_label, score_questions
from src.charts import (
    categorical_bar,
    chart_palette,
    liquid_chart,
    liquid_colors,
)
from src.config import FORM_TITLES
from src.ui import dataframe_download, empty_state, glass_section, page_header


data = st.session_state["app_data"]
catalog = load_catalog()

page_header(
    "Questionnaire analysis",
    "Select a questionnaire and inspect every analytical question with cohort comparisons.",
    "analytics",
    data=data,
)

selector_left, selector_right = st.columns([0.38, 0.62], vertical_alignment="bottom")
with selector_left:
    form_code = st.selectbox(
        "Questionnaire",
        options=list(FORM_TITLES),
        format_func=lambda code: f"{code} · {FORM_TITLES[code]}",
        key="analysis_form",
    )

frame = data.forms.get(form_code, pd.DataFrame())
normalized_columns = {normalize_label(column): column for column in frame.columns}
score_labels = {
    question["name"]: question.get("_score_label")
    for question in score_questions(form_code)
}


def response_column(question: dict) -> str | None:
    for candidate in (question.get("_display_label"), question.get("name")):
        match = normalized_columns.get(normalize_label(candidate))
        if match:
            return match
    return None


def question_choice_labels(question: dict) -> dict[str, str]:
    type_parts = str(question.get("type") or "").split(maxsplit=1)
    if len(type_parts) < 2:
        return {}
    choices = catalog.get(form_code, {}).get("choices_by_list", {}).get(
        type_parts[1].strip(),
        [],
    )
    labels: dict[str, str] = {}
    for choice in choices:
        name = str(choice.get("name") or "").strip()
        if not name:
            continue
        label = (
            choice.get("label::English (en)")
            or choice.get("label::English")
            or choice.get("label")
            or name
        )
        labels[name] = str(label)
        labels[name.casefold()] = str(label)
    return labels


def display_choice(value: object, labels: dict[str, str]) -> str:
    text = str(value).strip()
    return labels.get(text, labels.get(text.casefold(), text))


questions = []
for source_question in analytic_questions(form_code):
    item = dict(source_question)
    item["_analysis_label"] = (
        score_labels.get(source_question.get("name"))
        or source_question["_display_label"]
    )
    item["_response_column"] = response_column(source_question)
    questions.append(item)

if not questions:
    empty_state("No non-text analytical questions were found in this XLSForm.")
    st.stop()

with selector_right:
    question_index = st.selectbox(
        "Question",
        options=list(range(len(questions))),
        format_func=lambda index: (
            f"{index + 1:02d} / {len(questions):02d} · "
            f"{questions[index]['_analysis_label']}"
        ),
        key=f"analysis_question_selector_{form_code}",
    )

question = questions[question_index]
column = question["_response_column"]
question_type = question["_base_type"]
round_column = next(
    (
        candidate
        for candidate in frame.columns
        if normalize_label(candidate) == "assessment round"
    ),
    None,
)
dimension_columns = {
    "Overall": None,
    "Province": "_sample_province",
    "District": "_sample_district",
    "Assigned to": "_sample_assigned_to",
}
if round_column:
    dimension_columns["Assessment round"] = round_column

breakdown = "Overall"
display_mode = "Share"
top_n = 12
with st.popover(
    "Analysis settings",
    icon=":material/tune:",
):
    breakdown = st.selectbox(
        "Compare by",
        list(dimension_columns),
        key=f"analysis_breakdown_{form_code}",
    )
    display_mode = st.segmented_control(
        "Measure",
        ["Share", "Count"],
        default="Share",
        key=f"analysis_measure_{form_code}",
    )
    top_n = st.slider(
        "Maximum responses",
        min_value=5,
        max_value=25,
        value=12,
        key=f"analysis_top_n_{form_code}",
    )

st.caption(f"Question {question_index + 1} of {len(questions)}")
st.subheader(question["_analysis_label"])

series = (
    frame[column].mask(frame[column].astype("string").str.strip().eq(""))
    if column
    else pd.Series(pd.NA, index=frame.index)
)
multi_prefixes = (
    f"{question['_display_label']}/",
    f"{question.get('name')}/",
)
binary_columns = [
    candidate
    for candidate in frame.columns
    if any(str(candidate).startswith(prefix) for prefix in multi_prefixes)
]
answered_mask = series.notna()
if question_type == "select_multiple" and binary_columns:
    binary_answered = pd.Series(False, index=frame.index)
    for candidate in binary_columns:
        values = frame[candidate]
        binary_answered |= (
            pd.to_numeric(values, errors="coerce").fillna(0).gt(0)
            | values.astype("string").str.casefold().isin(
                {"yes", "true", "selected"}
            )
        )
    answered_mask |= binary_answered
answered = int(answered_mask.sum())
missing = len(frame) - answered
completion = answered / len(frame) if len(frame) else 0
distinct = int(series.dropna().astype(str).nunique())
rate_label = "raw response rate" if question.get("relevant") else "completion"
with st.container(horizontal=True, gap="xsmall", key="analysis-facts"):
    st.badge(
        question_type.replace("_", " "),
        icon=":material/category:",
        color="violet",
    )
    st.caption(f"{len(frame):,} records")
    st.caption(f"{answered:,} answered")
    st.caption(f"{missing:,} missing")
    st.caption(f"{completion:.0%} {rate_label}")
    st.caption(f"{distinct:,} distinct")
    if breakdown != "Overall":
        st.badge(
            f"By {breakdown.lower()}",
            icon=":material/compare_arrows:",
            color="blue",
        )
    if question.get("relevant"):
        st.badge("Conditional", icon=":material/alt_route:", color="blue")
    if question.get("constraint"):
        st.badge("Constrained", icon=":material/rule:", color="orange")

if form_code not in data.forms:
    st.warning(
        f"The XLSForm is documented, but the current source has no response sheet for {form_code}.",
        icon=":material/database_off:",
    )

if not column or frame.empty:
    empty_state(
        "This question has no response column in the active dataset.",
        icon="database_off",
    )
else:
    group_column = dimension_columns[breakdown]
    group_label = breakdown
    chart_column, summary_column = st.columns([1.32, 0.68], vertical_alignment="top")
    palette = chart_palette()
    choice_labels = question_choice_labels(question)

    with chart_column:
        section = glass_section(
            "Response distribution",
            subtitle=(
                "Overall pattern"
                if breakdown == "Overall"
                else f"Normalized comparison by {breakdown.lower()}"
            ),
            icon="query_stats",
            key="analysis-distribution",
        )

        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().mean() < 0.8:
            numeric = pd.to_numeric(
                series.astype("string").str.extract(
                    r"^\s*(-?[0-9]+(?:\.[0-9]+)?)",
                    expand=False,
                ),
                errors="coerce",
            )

        group_values = (
            frame[group_column].fillna("Not recorded").astype(str)
            if group_column
            else pd.Series("Overall", index=frame.index)
        )
        denominators = pd.Series(dtype="int64")

        if question_type == "select_multiple" and binary_columns:
            long_parts = []
            respondent_mask = series.notna().copy()
            for candidate in binary_columns:
                values = frame[candidate]
                selected = (
                    pd.to_numeric(values, errors="coerce").fillna(0).gt(0)
                    | values.astype("string").str.casefold().isin(
                        {"yes", "true", "selected"}
                    )
                )
                respondent_mask |= selected
                response = display_choice(
                    str(candidate).split("/", 1)[-1],
                    choice_labels,
                )
                long_parts.append(
                    pd.DataFrame(
                        {
                            "Group": group_values[selected],
                            "Response": response,
                        }
                    )
                )
            long = (
                pd.concat(long_parts, ignore_index=True)
                if long_parts
                else pd.DataFrame(columns=["Group", "Response"])
            )
            distribution = (
                long.groupby(["Group", "Response"], observed=True)
                .size()
                .reset_index(name="Count")
            )
            denominators = (
                group_values[respondent_mask]
                .value_counts()
                .rename("Denominator")
            )
        elif question_type == "select_multiple":
            answered_source = pd.DataFrame(
                {
                    "Group": group_values[series.notna()],
                    "Raw response": series.dropna().astype(str),
                }
            )
            denominators = (
                answered_source["Group"].value_counts().rename("Denominator")
            )
            long = answered_source.assign(
                Response=answered_source["Raw response"].str.split(r"[,;\s]+")
            ).explode("Response")
            long["Response"] = long["Response"].map(
                lambda value: display_choice(value, choice_labels)
            )
            long = long[long["Response"].astype(str).str.strip().ne("")]
            distribution = (
                long.groupby(["Group", "Response"], observed=True)
                .size()
                .reset_index(name="Count")
            )
        else:
            distribution_source = pd.DataFrame(
                {
                    "Response": series.dropna()
                    .astype(str)
                    .map(lambda value: display_choice(value, choice_labels)),
                    "Group": group_values[series.notna()],
                }
            )
            distribution = (
                distribution_source.groupby(["Group", "Response"], observed=True)
                .size()
                .reset_index(name="Count")
            )
            denominators = (
                distribution.groupby("Group", observed=True)["Count"]
                .sum()
                .rename("Denominator")
            )

        full_distribution = distribution.copy()
        if not full_distribution.empty:
            full_distribution["Share"] = (
                full_distribution["Count"]
                / full_distribution["Group"]
                .map(denominators)
                .fillna(0)
                .clip(lower=1)
            )
        overall_rank = (
            full_distribution.groupby("Response", observed=True)["Count"]
            .sum()
            .nlargest(top_n)
            .index
        )
        distribution = full_distribution[
            full_distribution["Response"].isin(overall_rank)
        ].copy()

        if (
            question_type in {"integer", "decimal", "calculate"}
            and numeric.notna().any()
        ):
            numeric_data = pd.DataFrame(
                {
                    "Value": numeric,
                    "Group": (
                        frame[group_column].fillna("Not recorded").astype(str)
                        if group_column
                        else "Overall"
                    ),
                }
            ).dropna(subset=["Value"])
            if breakdown == "Overall":
                chart = (
                    alt.Chart(numeric_data)
                    .mark_bar(
                        color=palette["purple"],
                        cornerRadiusEnd=6,
                        opacity=0.9,
                    )
                    .encode(
                        x=alt.X(
                            "Value:Q",
                            bin=alt.Bin(maxbins=16),
                            title="Value",
                        ),
                        y=alt.Y("count():Q", title="Responses"),
                        tooltip=[alt.Tooltip("count():Q", title="Responses")],
                    )
                    .properties(height=350)
                )
            else:
                group_sort = alt.SortField(
                    field="Value",
                    op="median",
                    order="descending",
                )
                chart = (
                    alt.Chart(numeric_data)
                    .mark_boxplot(extent=1.5, size=24)
                    .encode(
                        y=alt.Y("Group:N", title=None, sort=group_sort),
                        x=alt.X("Value:Q", title="Value"),
                        color=alt.Color(
                            "Group:N",
                            legend=None,
                            scale=alt.Scale(range=liquid_colors()),
                        ),
                        tooltip=[
                            alt.Tooltip("Group:N", title=group_label),
                            alt.Tooltip("Value:Q", format=".2f"),
                        ],
                    )
                    .properties(height=max(300, min(520, numeric_data["Group"].nunique() * 34 + 80)))
                )
            section.altair_chart(
                liquid_chart(chart),
                key="analysis_numeric_chart",
            )

        elif question_type == "date":
            date_data = pd.DataFrame(
                {
                    "Date": pd.to_datetime(series, errors="coerce"),
                    "Group": (
                        frame[group_column].fillna("Not recorded").astype(str)
                        if group_column
                        else "Overall"
                    ),
                }
            ).dropna(subset=["Date"])
            date_counts = (
                date_data.groupby(["Date", "Group"], observed=True)
                .size()
                .reset_index(name="Responses")
            )
            chart = (
                alt.Chart(date_counts)
                .mark_line(point=True, strokeWidth=2.5)
                .encode(
                    x=alt.X("Date:T", title=None),
                    y=alt.Y("Responses:Q", title="Responses"),
                    color=alt.Color(
                        "Group:N",
                        title=None,
                        scale=alt.Scale(range=liquid_colors()),
                    ),
                    tooltip=[
                        alt.Tooltip("Date:T", format="%d %b %Y"),
                        alt.Tooltip("Group:N", title=group_label),
                        "Responses:Q",
                    ],
                )
                .properties(height=350)
            )
            section.altair_chart(
                liquid_chart(chart),
                key="analysis_date_chart",
            )

        elif breakdown == "Overall":
            measure = "Share" if display_mode == "Share" else "Count"
            chart_data = distribution.sort_values(measure, ascending=False)
            chart = categorical_bar(
                chart_data,
                "Response",
                measure,
                horizontal=True,
                height=350,
                value_format=".1%" if measure == "Share" else ",",
            )
            if measure == "Share":
                chart = chart.encode(
                    x=alt.X(
                        "Share:Q",
                        title="Share of responses",
                        axis=alt.Axis(format="%"),
                    )
                )
            section.altair_chart(chart, key="analysis_category_chart")

        else:
            measure = "Share" if display_mode == "Share" else "Count"
            heat = (
                alt.Chart(distribution)
                .mark_rect(cornerRadius=4)
                .encode(
                    x=alt.X("Response:N", title=None, sort=list(overall_rank)),
                    y=alt.Y("Group:N", title=None),
                    color=alt.Color(
                        f"{measure}:Q",
                        title=measure,
                        scale=(
                            alt.Scale(
                                domain=[0, 1],
                                range=[palette["purple"], palette["cyan"]],
                            )
                            if measure == "Share"
                            else alt.Scale(
                                range=[palette["purple"], palette["cyan"]]
                            )
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("Group:N", title=group_label),
                        "Response:N",
                        alt.Tooltip("Count:Q", format=","),
                        alt.Tooltip("Share:Q", format=".1%"),
                    ],
                )
                .properties(
                    height=max(300, min(520, distribution["Group"].nunique() * 34 + 80))
                )
            )
            section.altair_chart(
                liquid_chart(heat),
                key="analysis_comparison_heatmap",
            )

    with summary_column:
        summary = glass_section(
            "Statistical summary",
            subtitle="Compact evidence for interpretation.",
            icon="summarize",
            key="analysis-summary",
            height="stretch",
        )
        if (
            question_type in {"integer", "decimal", "calculate"}
            and numeric.notna().any()
        ):
            clean_numeric = numeric.dropna()
            stats = pd.DataFrame(
                {
                    "Statistic": [
                        "Mean",
                        "Median",
                        "Minimum",
                        "Maximum",
                        "Std. deviation",
                    ],
                    "Value": [
                        clean_numeric.mean(),
                        clean_numeric.median(),
                        clean_numeric.min(),
                        clean_numeric.max(),
                        clean_numeric.std(),
                    ],
                }
            )
            summary.dataframe(
                stats,
                hide_index=True,
                height=350,
                row_height=40,
                key="analysis_numeric_summary",
                column_config={
                    "Value": st.column_config.NumberColumn(format="%.2f")
                },
            )
        else:
            top_responses = (
                full_distribution.groupby("Response", observed=True)["Count"]
                .sum()
                .sort_values(ascending=False)
                .head(10)
                .rename("Count")
                .reset_index()
            )
            total = (
                int(denominators.sum())
                if question_type == "select_multiple"
                else int(full_distribution["Count"].sum())
            )
            top_responses["Share"] = (
                top_responses["Count"] / total if total else 0
            )
            summary.dataframe(
                top_responses,
                hide_index=True,
                height=350,
                row_height=40,
                key="analysis_top_responses",
                column_config={
                    "Response": st.column_config.TextColumn(width="medium"),
                    "Count": st.column_config.NumberColumn(width="small"),
                    "Share": st.column_config.ProgressColumn(
                        width="medium",
                        min_value=0,
                        max_value=1,
                        format="percent",
                    ),
                },
            )

logic_expander = st.expander(
    "Question logic and definition",
    icon=":material/rule:",
    on_change="rerun",
)
if logic_expander.open:
    with logic_expander:
        logic = pd.DataFrame(
            {
                "Property": [
                    "Kobo name",
                    "Type",
                    "Required",
                    "Relevant",
                    "Constraint",
                ],
                "Definition": [
                    question.get("name"),
                    question.get("type"),
                    question.get("required") or "No / conditional",
                    question.get("relevant") or "No field-level rule",
                    question.get("constraint") or "No explicit constraint",
                ],
            }
        )
        st.dataframe(
            logic,
            hide_index=True,
            row_height=40,
            key="analysis_logic_table",
        )

if column and not frame.empty:
    show_records = st.toggle(
        "Show record-level responses",
        value=False,
        key=f"analysis_show_records_{form_code}_{question_index}",
    )
    if show_records:
        response_table = pd.DataFrame(
            {
                "WOB ID": frame["WOB ID"],
                "Beneficiary Name": frame["Beneficiary Name"],
                "Province": frame["_sample_province"],
                "District": frame["_sample_district"],
                "Assigned to": frame["_sample_assigned_to"],
                "Response": frame[column],
                "Submission time": frame.get("_submission_time"),
            }
        )
        st.dataframe(
            response_table,
            hide_index=True,
            row_height=40,
            key="analysis_response_table",
            column_config={
                "WOB ID": st.column_config.TextColumn(
                    "Unique WOB ID", pinned=True
                ),
                "Beneficiary Name": st.column_config.TextColumn(pinned=True),
                "Response": st.column_config.TextColumn(width="large"),
                "Submission time": st.column_config.DatetimeColumn(
                    format="DD MMM YYYY, HH:mm"
                ),
            },
        )
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(question.get("name")))
        dataframe_download(
            response_table,
            label="Download responses",
            file_name=f"{form_code}_{safe_name}.csv",
            key="download_analysis_responses",
        )
