from __future__ import annotations

import pandas as pd
import streamlit as st

from src.catalog import NON_ANALYTIC_TYPES, is_analytic_question, load_catalog
from src.config import FORM_TITLES
from src.ui import dataframe_download, glass_section, metric_row, page_header


data = st.session_state["app_data"]
full_data = st.session_state["full_app_data"]
catalog = load_catalog()

page_header(
    "Questionnaire catalog",
    "A searchable English data dictionary generated directly from XLS_Forms.",
    "library_books",
    data=data,
)

catalog_rows = []
for code, title in FORM_TITLES.items():
    form = catalog.get(code, {})
    questions = form.get("questions", [])
    catalog_rows.append(
        {
            "Form": code,
            "Form title": title,
            "Data sheet": code in full_data.forms,
            "Questionnaire fields": len(questions),
            "Analytical fields": sum(
                is_analytic_question(question) for question in questions
            ),
            "Text fields ignored": sum(
                question.get("_base_type") == "text" for question in questions
            ),
            "Relevance rules": sum(
                bool(question.get("relevant")) for question in questions
            ),
            "Constraints": sum(
                bool(question.get("constraint")) for question in questions
            ),
        }
    )
form_catalog = pd.DataFrame(catalog_rows)

metric_row(
    [
        {"label": "Questionnaires", "value": len(form_catalog)},
        {
            "label": "Data sheets",
            "value": int(form_catalog["Data sheet"].sum()),
        },
        {
            "label": "Analytical fields",
            "value": int(form_catalog["Analytical fields"].sum()),
        },
        {
            "label": "Logic rules",
            "value": int(
                form_catalog["Relevance rules"].sum()
                + form_catalog["Constraints"].sum()
            ),
            "help": "Relevance expressions plus constraints.",
        },
    ]
)

view = st.segmented_control(
    "Catalog view",
    ["Inventory", "Data dictionary"],
    default="Inventory",
    key="catalog_view",
)

if view == "Inventory":
    section = glass_section(
        "Form inventory",
        subtitle="Documented questionnaires and live response-sheet availability.",
        icon="inventory_2",
        key="catalog-inventory",
    )
    section.dataframe(
        form_catalog,
        hide_index=True,
        row_height=38,
        key="catalog_inventory_table",
        column_config={
            "Data sheet": st.column_config.CheckboxColumn(),
            "Form": st.column_config.TextColumn(pinned=True),
            "Form title": st.column_config.TextColumn(width="large"),
        },
    )

else:
    form_code = st.selectbox(
        "Inspect questionnaire",
        list(FORM_TITLES),
        format_func=lambda code: f"{code} · {FORM_TITLES[code]}",
        key="catalog_form",
    )
    form = catalog[form_code]
    type_options = sorted({q["_base_type"] for q in form["questions"]})

    show_text = False
    selected_types = [
        q_type for q_type in type_options if q_type not in NON_ANALYTIC_TYPES
    ]
    with st.popover("Dictionary filters", icon=":material/tune:"):
        show_text = st.toggle(
            "Include text-field metadata",
            value=False,
            help="Text responses remain excluded from dashboard analytics.",
            key="catalog_show_text",
        )
        default_types = [
            q_type
            for q_type in type_options
            if q_type not in NON_ANALYTIC_TYPES
            or (show_text and q_type == "text")
        ]
        selected_types = st.multiselect(
            "Question types",
            options=type_options,
            default=default_types,
            key=f"catalog_types_{form_code}_{show_text}",
        )

    dictionary_rows = []
    for question in form["questions"]:
        if question["_base_type"] not in selected_types:
            continue
        if question["_base_type"] == "text" and not show_text:
            continue
        dictionary_rows.append(
            {
                "English label": question["_display_label"],
                "Kobo name": question.get("name"),
                "Type": question.get("type"),
                "Required": question.get("required"),
                "Relevant": question.get("relevant"),
                "Constraint": question.get("constraint"),
                "Constraint message": question.get(
                    "constraint_message::English (en)"
                ),
                "Dashboard use": (
                    "Ignored (text)"
                    if question["_base_type"] == "text"
                    else (
                        "Metadata only"
                        if question["_base_type"] in NON_ANALYTIC_TYPES
                        else "Analytical"
                    )
                ),
            }
        )
    dictionary = pd.DataFrame(dictionary_rows)

    section = glass_section(
        f"{form_code} data dictionary",
        subtitle=f"{FORM_TITLES[form_code]} · {len(dictionary):,} visible fields.",
        icon="dictionary",
        key="catalog-dictionary",
    )
    with section:
        st.dataframe(
            dictionary,
            hide_index=True,
            width="stretch",
            row_height=44,
            height=560,
            key="catalog_dictionary_table",
            column_order=[
                "English label",
                "Kobo name",
                "Type",
                "Dashboard use",
            ],
            column_config={
                "English label": st.column_config.TextColumn(
                    width="medium"
                ),
                "Kobo name": st.column_config.TextColumn(width="medium"),
                "Type": st.column_config.TextColumn(width="small"),
                "Dashboard use": st.column_config.TextColumn(width="small"),
            },
        )
        logic_details = st.expander(
            "Logic details",
            icon=":material/rule:",
            on_change="rerun",
        )
        if logic_details.open:
            with logic_details:
                st.dataframe(
                    dictionary[
                        [
                            "English label",
                            "Required",
                            "Relevant",
                            "Constraint",
                            "Constraint message",
                        ]
                    ],
                    hide_index=True,
                    width="stretch",
                    row_height=44,
                    height=420,
                    key="catalog_logic_table",
                    column_config={
                        "English label": st.column_config.TextColumn(
                            width="medium"
                        ),
                        "Relevant": st.column_config.TextColumn(width="large"),
                        "Constraint": st.column_config.TextColumn(width="large"),
                        "Constraint message": st.column_config.TextColumn(
                            width="large"
                        ),
                    },
                )
        dataframe_download(
            dictionary,
            label="Download data dictionary",
            file_name=f"{form_code}_questionnaire_data_dictionary.csv",
            key="download_catalog_dictionary",
        )
