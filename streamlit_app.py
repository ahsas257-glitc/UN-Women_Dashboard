from __future__ import annotations

import streamlit as st

from src.config import FORM_TITLES
from src.catalog import load_catalog
from src.data import (
    DataSourceError,
    all_rounds,
    fetch_workbook_bytes,
    filter_data,
    load_app_data,
    read_workbook_tables,
    submission_date_bounds,
)
from src.ui import inject_liquid_glass


st.set_page_config(
    page_title="UN Women · WOB intelligence hub",
    page_icon=":material/insights:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_liquid_glass()


def clear_global_filters() -> None:
    for key in (
        "global_provinces",
        "global_districts",
        "global_assignees",
        "global_wob_keys",
        "global_forms",
        "global_rounds",
        "global_coverage_statuses",
    ):
        st.session_state[key] = []
    st.session_state["global_date_limit"] = False


def refresh_project_data() -> None:
    """Clear all source/model caches before the next Cloud rerun."""
    fetch_workbook_bytes.clear()
    read_workbook_tables.clear()
    load_app_data.clear()
    load_catalog.cache_clear()


pages = [
    st.Page("app_pages/overview.py", title="Overview", icon=":material/space_dashboard:"),
    st.Page("app_pages/beneficiary.py", title="Beneficiary", icon=":material/person_search:"),
    st.Page("app_pages/explorer.py", title="Analysis", icon=":material/analytics:"),
    st.Page("app_pages/quality.py", title="Quality", icon=":material/fact_check:"),
    st.Page("app_pages/catalog_page.py", title="Catalog", icon=":material/library_books:"),
]
navigation = st.navigation(pages, position="top")

with st.sidebar:
    st.subheader(":material/tune: Filters")
    st.caption("Selections are applied together for faster interaction.")

    with st.spinner("Synchronizing project data…", show_time=True):
        try:
            full_data = load_app_data()
        except DataSourceError as exc:
            st.error(str(exc), icon=":material/cloud_off:")
            st.caption(
                "For Streamlit Community Cloud, add GOOGLE_SHEET_ID "
                "under App settings → Secrets."
            )
            st.stop()

    province_options = sorted(
        full_data.sample["Province"].dropna().astype(str).unique()
    )
    district_options = sorted(
        full_data.sample["District"].dropna().astype(str).unique()
    )
    assignee_options = sorted(
        full_data.sample["Assigned_to"].dropna().astype(str).unique()
    )
    beneficiary_options = {
        row["_wob_key"]: f"{row['WOB ID']} · {row['Beneficiary Name']}"
        for _, row in full_data.sample.iterrows()
    }
    date_bounds = submission_date_bounds(full_data)

    with st.form("global_filter_form", border=False):
        provinces = st.multiselect(
            "Province",
            province_options,
            placeholder="All provinces",
            key="global_provinces",
        )
        districts = st.multiselect(
            "District",
            district_options,
            placeholder="All districts",
            key="global_districts",
        )
        assignees = st.multiselect(
            "Assigned to",
            assignee_options,
            placeholder="All teams",
            key="global_assignees",
        )
        wob_keys = st.multiselect(
            "Beneficiary / Unique WOB ID",
            options=list(beneficiary_options),
            format_func=lambda value: beneficiary_options[value],
            placeholder="All beneficiaries",
            key="global_wob_keys",
        )

        with st.expander(
            "Advanced filters",
            icon=":material/filter_alt:",
        ):
            selected_forms = st.multiselect(
                "Questionnaires",
                options=sorted(full_data.forms),
                format_func=lambda code: f"{code} · {FORM_TITLES[code]}",
                placeholder="All available questionnaires",
                key="global_forms",
            )
            rounds = st.multiselect(
                "Assessment round",
                all_rounds(full_data),
                placeholder="All rounds",
                key="global_rounds",
            )
            coverage_statuses = st.multiselect(
                "Coverage status",
                ["Complete", "Missing", "Unexpected", "Not assigned"],
                placeholder="All statuses",
                key="global_coverage_statuses",
            )
            limit_dates = st.toggle(
                "Limit by submission date",
                key="global_date_limit",
            )
            if date_bounds:
                date_range = st.date_input(
                    "Submission date",
                    value=date_bounds,
                    min_value=date_bounds[0],
                    max_value=date_bounds[1],
                    key="global_date_range",
                    disabled=not limit_dates,
                )
            else:
                date_range = None

        st.form_submit_button(
            "Apply filters",
            icon=":material/check:",
            type="primary",
            width="stretch",
        )

    active_filter_count = sum(
        bool(value)
        for value in (
            provinces,
            districts,
            assignees,
            wob_keys,
            selected_forms,
            rounds,
            coverage_statuses,
        )
    ) + int(bool(limit_dates and date_range))

    st.button(
        "Clear",
        icon=":material/filter_alt_off:",
        type="tertiary",
        on_click=clear_global_filters,
    )
    st.button(
        "Refresh data",
        icon=":material/refresh:",
        type="tertiary",
        on_click=refresh_project_data,
        help="Reload Google Sheets data and questionnaire metadata.",
    )

    st.caption(
        f"{active_filter_count} active filters · "
        f"{len(full_data.sample):,} Sample_Track records"
    )
    st.caption(
        f"{len(full_data.tables):,} live sheets · "
        f"{len(full_data.score_long):,} scored responses"
    )
    st.caption("Light / dark appearance follows Streamlit settings")

filters = {
    "provinces": provinces,
    "districts": districts,
    "assignees": assignees,
    "wob_keys": wob_keys,
    "forms": selected_forms,
    "rounds": rounds,
    "coverage_statuses": coverage_statuses,
    "date_range": date_range if limit_dates else None,
}
st.session_state["full_app_data"] = full_data
st.session_state["app_data"] = filter_data(full_data, filters)
st.session_state["global_filters"] = filters

navigation.run()
