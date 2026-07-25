from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.catalog import load_catalog, normalize_label, score_questions
from src.config import (
    CAPACITY_FORMS,
    FORM_TITLES,
    GOOGLE_SHEET_ID,
    PUBLIC_GOOGLE_SHEET_ID,
    TRACKED_FORMS,
    WOB_COLUMNS,
    normalize_google_sheet_id,
)


class DataSourceError(RuntimeError):
    """Raised when neither the configured live workbook nor local fallback is available."""


@dataclass
class AppData:
    tables: dict[str, pd.DataFrame]
    forms: dict[str, pd.DataFrame]
    sample: pd.DataFrame
    qa: pd.DataFrame
    correction_log: pd.DataFrame
    corrections: pd.DataFrame
    score_long: pd.DataFrame
    coverage: pd.DataFrame
    source_mode: str
    loaded_at: datetime
    correction_stats: dict[str, int]


def normalize_wob(value: Any) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value)).upper()


def form_code_from_text(value: Any) -> str | None:
    match = re.search(r"\b(C[1-7]|F0[1-6])\b", str(value or ""), flags=re.I)
    return match.group(1).upper() if match else None


def find_wob_column(df: pd.DataFrame) -> str | None:
    normalized = {normalize_label(column): column for column in df.columns}
    for candidate in WOB_COLUMNS:
        if normalize_label(candidate) in normalized:
            return normalized[normalize_label(candidate)]
    for column in df.columns:
        label = normalize_label(column)
        if "unique wob" in label or label == "wob id":
            return column
    return None


def configured_google_sheet_id() -> str:
    """Resolve Cloud secrets safely while retaining the project's public live source."""
    secret_value = ""
    try:
        secret_value = st.secrets.get("GOOGLE_SHEET_ID", "")
    except (FileNotFoundError, KeyError):
        pass
    return (
        normalize_google_sheet_id(secret_value)
        or GOOGLE_SHEET_ID
        or PUBLIC_GOOGLE_SHEET_ID
    )


@st.cache_data(ttl="2m", max_entries=2, show_spinner=False)
def fetch_workbook_bytes() -> tuple[bytes, str]:
    sheet_id = configured_google_sheet_id()
    export_url = (
        "https://docs.google.com/spreadsheets/d/"
        f"{sheet_id}/export?format=xlsx"
    )
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods={"GET"},
    )
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        try:
            response = session.get(
                export_url,
                headers={
                    "Accept": (
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                    "User-Agent": "UN-Women-WOB-Dashboard/1.0",
                },
                timeout=(10, 60),
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise DataSourceError(
                "The live Google Sheet could not be reached. "
                "Confirm that link sharing permits workbook export, then refresh."
            ) from exc

    payload = response.content
    if len(payload) < 50_000 or not payload.startswith(b"PK"):
        raise DataSourceError(
            "Google returned a sign-in or incomplete response instead of an XLSX workbook. "
            "Set the sheet to link-viewable and refresh the app."
        )
    return payload, "Live Google Sheet"


@st.cache_data(ttl="5m", max_entries=2, show_spinner=False)
def read_workbook_tables(payload: bytes) -> dict[str, pd.DataFrame]:
    try:
        raw = pd.read_excel(io.BytesIO(payload), sheet_name=None, engine="openpyxl")
    except (OSError, ValueError) as exc:
        raise DataSourceError(
            "The Google Sheet export is not a readable XLSX workbook."
        ) from exc
    tables = {
        name: frame.dropna(how="all").reset_index(drop=True)
        for name, frame in raw.items()
    }
    if "Sample_Track" not in tables:
        raise DataSourceError(
            "The live Google Sheet is missing the required Sample_Track sheet."
        )
    if not _form_tables(tables):
        raise DataSourceError(
            "The live Google Sheet does not contain any recognized questionnaire sheets."
        )
    return tables


def _form_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    result = {}
    for sheet_name, frame in tables.items():
        code = form_code_from_text(sheet_name)
        if code and code in FORM_TITLES:
            result[code] = frame.copy()
    return result


def _target_column(
    form_code: str,
    label: Any,
    columns: list[str],
    normalized_columns: dict[str, str] | None = None,
) -> str | None:
    label_text = str(label or "").strip()
    if not label_text:
        return None
    if label_text in columns:
        return label_text
    normalized_columns = normalized_columns or {
        normalize_label(column): column for column in columns
    }
    if normalize_label(label_text) in normalized_columns:
        return normalized_columns[normalize_label(label_text)]
    catalog = load_catalog().get(form_code, {})
    question = catalog.get("by_name", {}).get(normalize_label(label_text))
    if not question:
        question = catalog.get("by_label", {}).get(normalize_label(label_text))
    if not question:
        return None
    for candidate in (question.get("name"), question.get("_display_label")):
        key = normalize_label(candidate)
        if key in normalized_columns:
            return normalized_columns[key]
    return None


def _key_indexes(frame: pd.DataFrame) -> dict[str, list[int]]:
    candidates = [
        "_uuid",
        "submission_uuid",
        "meta/rootUuid",
        "_id",
        "KEY",
    ]
    mapping: dict[str, list[int]] = {}
    for column in candidates:
        if column not in frame.columns:
            continue
        for index, value in frame[column].items():
            if pd.isna(value):
                continue
            mapping.setdefault(str(value).strip(), []).append(index)
    return mapping


def apply_corrections(
    forms: dict[str, pd.DataFrame],
    correction_tables: list[pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    corrected = {code: frame.copy() for code, frame in forms.items()}
    key_maps = {code: _key_indexes(frame) for code, frame in corrected.items()}
    column_maps = {
        code: {normalize_label(column): column for column in frame.columns}
        for code, frame in corrected.items()
    }
    stats = {"applied": 0, "unmatched_key": 0, "unmatched_field": 0, "skipped": 0}

    for corrections in correction_tables:
        if corrections.empty:
            continue
        actionable = corrections
        if "New Value" in corrections:
            actionable = corrections[corrections["New Value"].notna()]
            stats["skipped"] += len(corrections) - len(actionable)
        for row in actionable.to_dict("records"):
            code = form_code_from_text(row.get("Form Name"))
            new_value = row.get("New Value")
            if not code or code not in corrected or pd.isna(new_value):
                stats["skipped"] += 1
                continue
            key = str(row.get("KEY") or "").strip()
            indices = key_maps[code].get(key, [])
            if not indices:
                stats["unmatched_key"] += 1
                continue
            column = _target_column(
                code,
                row.get("Label"),
                list(corrected[code].columns),
                column_maps[code],
            )
            if not column:
                stats["unmatched_field"] += 1
                continue
            for index in indices:
                corrected[code].at[index, column] = new_value
                stats["applied"] += 1
    return corrected, stats


def prepare_sample(frame: pd.DataFrame) -> pd.DataFrame:
    sample = frame.copy()
    required = ["Name", "Province", "District", "WOB_ID", "Assigned_to"]
    for column in required:
        if column not in sample:
            sample[column] = pd.NA
    sample["_wob_key"] = sample["WOB_ID"].map(normalize_wob)
    sample = sample[sample["_wob_key"] != ""].copy()
    sample["Beneficiary Name"] = sample["Name"].fillna("Name not recorded")
    sample["WOB ID"] = sample["WOB_ID"].astype("string")
    return sample.drop_duplicates("_wob_key", keep="last").reset_index(drop=True)


def enrich_forms(
    forms: dict[str, pd.DataFrame], sample: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    sample_lookup = sample.set_index("_wob_key")[
        ["WOB ID", "Beneficiary Name", "Province", "District", "Assigned_to"]
    ].rename(
        columns={
            "Province": "_sample_province",
            "District": "_sample_district",
            "Assigned_to": "_sample_assigned_to",
        }
    )
    enriched = {}
    for code, frame in forms.items():
        df = frame.copy()
        wob_column = find_wob_column(df)
        df["_wob_key"] = df[wob_column].map(normalize_wob) if wob_column else ""
        df["_form_code"] = code
        df["_form_title"] = FORM_TITLES[code]
        df = df.join(sample_lookup, on="_wob_key")
        df["Beneficiary Name"] = df["Beneficiary Name"].fillna("Not in Sample Track")
        df["WOB ID"] = df["WOB ID"].fillna(
            df[wob_column].astype("string") if wob_column else pd.Series(pd.NA, index=df.index)
        )
        for date_column in ("today", "_submission_time", "start", "end"):
            if date_column in df:
                df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
        enriched[code] = df
    return enriched


def _parse_score(value: Any) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        score = float(value)
    else:
        match = re.match(r"\s*([0-2](?:\.\d+)?)", str(value))
        if not match:
            return None
        score = float(match.group(1))
    return score if 0 <= score <= 2 else None


def _is_score_column(column: Any) -> bool:
    """Recognize exported Kobo score fields without relying only on XLSForm metadata."""
    name = normalize_label(column)
    if not re.search(r"(?:^|[_\s])score(?:$|[_\s])", name):
        return False
    return not any(
        re.search(rf"(?:^|[_\s]){token}(?:$|[_\s])", name)
        for token in (
            "guide",
            "target",
            "avg",
            "average",
            "mean",
            "gap",
            "change",
            "percent",
            "count",
            "sum",
            "total",
        )
    )


def _score_field_specs(
    form_code: str,
    frame: pd.DataFrame,
) -> list[tuple[str, str, str]]:
    """Resolve score fields from the catalog, then safely fall back to Kobo names."""
    normalized_columns = {normalize_label(column): column for column in frame.columns}
    specs: list[tuple[str, str, str]] = []
    used_columns: set[str] = set()

    for question in score_questions(form_code):
        column = next(
            (
                normalized_columns[normalize_label(candidate)]
                for candidate in (
                    question.get("name"),
                    question.get("_display_label"),
                )
                if normalize_label(candidate) in normalized_columns
            ),
            None,
        )
        if column is None or column in used_columns:
            continue
        specs.append(
            (
                str(column),
                str(question.get("name") or column),
                str(question.get("_score_label") or question.get("_display_label") or column),
            )
        )
        used_columns.add(str(column))

    # Keep Cloud analytics available if workbook columns and cached questionnaire
    # metadata briefly come from different revisions. Kobo's *_score names are
    # unambiguous after aggregate/guide fields are excluded.
    for column in frame.columns:
        column_text = str(column)
        if column_text in used_columns or not _is_score_column(column_text):
            continue
        numeric = pd.to_numeric(frame[column], errors="coerce")
        if not numeric.between(0, 2, inclusive="both").any():
            numeric = frame[column].map(_parse_score)
        if numeric.between(0, 2, inclusive="both").any():
            specs.append((column_text, column_text, column_text))
            used_columns.add(column_text)

    return specs


def build_score_long(forms: dict[str, pd.DataFrame]) -> pd.DataFrame:
    chunks: list[pd.DataFrame] = []
    for code in [*CAPACITY_FORMS, "F03"]:
        if code not in forms:
            continue
        frame = forms[code]
        round_column = next(
            (column for column in frame.columns if normalize_label(column) == "assessment round"),
            None,
        )
        for column, item_name, question_label in _score_field_specs(code, frame):
            raw_score = frame[column]
            numeric_score = pd.to_numeric(raw_score, errors="coerce")
            if numeric_score.notna().mean() < 0.8:
                numeric_score = pd.to_numeric(
                    raw_score.astype("string").str.extract(
                        r"^\s*([0-2](?:\.\d+)?)", expand=False
                    ),
                    errors="coerce",
                )
            valid = numeric_score.between(0, 2, inclusive="both")
            if not valid.any():
                continue
            selected = frame.loc[valid]
            chunk = pd.DataFrame(
                {
                    "Form": code,
                    "Module": FORM_TITLES[code],
                    "_wob_key": selected["_wob_key"],
                    "WOB ID": selected["WOB ID"],
                    "Beneficiary Name": selected["Beneficiary Name"],
                    "Province": selected["_sample_province"],
                    "District": selected["_sample_district"],
                    "Assigned to": selected["_sample_assigned_to"],
                    "Assessment Round": (
                        selected[round_column]
                        if round_column
                        else pd.Series(pd.NA, index=selected.index)
                    ),
                    "Item": item_name,
                    "Question": question_label,
                    "Score": numeric_score.loc[valid].astype(float),
                    "Submission time": selected.get(
                        "_submission_time",
                        pd.Series(pd.NaT, index=selected.index),
                    ),
                }
            )
            chunks.append(chunk.reset_index(drop=True))
    if not chunks:
        return pd.DataFrame(
            columns=[
                "Form",
                "Module",
                "_wob_key",
                "WOB ID",
                "Beneficiary Name",
                "Province",
                "District",
                "Assigned to",
                "Assessment Round",
                "Item",
                "Question",
                "Score",
                "Submission time",
            ]
        )
    return pd.concat(chunks, ignore_index=True)


def build_coverage(sample: pd.DataFrame, forms: dict[str, pd.DataFrame]) -> pd.DataFrame:
    records = []
    actual_sets = {
        code: set(frame.loc[frame["_wob_key"] != "", "_wob_key"])
        for code, frame in forms.items()
    }
    for _, beneficiary in sample.iterrows():
        for code in TRACKED_FORMS:
            expected = bool(pd.to_numeric(beneficiary.get(code), errors="coerce") == 1)
            actual = beneficiary["_wob_key"] in actual_sets.get(code, set())
            if expected and actual:
                status = "Complete"
            elif expected and not actual:
                status = "Missing"
            elif not expected and actual:
                status = "Unexpected"
            else:
                status = "Not assigned"
            records.append(
                {
                    "_wob_key": beneficiary["_wob_key"],
                    "WOB ID": beneficiary["WOB ID"],
                    "Beneficiary Name": beneficiary["Beneficiary Name"],
                    "Province": beneficiary["Province"],
                    "District": beneficiary["District"],
                    "Assigned to": beneficiary["Assigned_to"],
                    "Form": code,
                    "Expected": expected,
                    "Submitted": actual,
                    "Status": status,
                }
            )
    return pd.DataFrame.from_records(records)


def prepare_qa(frame: pd.DataFrame, sample: pd.DataFrame) -> pd.DataFrame:
    qa = frame.copy()
    wob_column = find_wob_column(qa)
    qa["_wob_key"] = qa[wob_column].map(normalize_wob) if wob_column else ""
    names = sample.set_index("_wob_key")["Beneficiary Name"]
    qa["Beneficiary Name"] = qa["_wob_key"].map(names).fillna("Not in Sample Track")
    qa["WOB ID"] = qa["_wob_key"].map(sample.set_index("_wob_key")["WOB ID"])
    for column in ("Survey Date", "QA'd Date", "DA_Date"):
        if column in qa:
            qa[column] = pd.to_datetime(qa[column], errors="coerce")
    return qa


@st.cache_data(ttl="2m", max_entries=2, show_spinner=False)
def load_app_data() -> AppData:
    payload, source_mode = fetch_workbook_bytes()
    tables = read_workbook_tables(payload)
    sample = prepare_sample(tables.get("Sample_Track", pd.DataFrame()))
    raw_forms = _form_tables(tables)
    correction_log = tables.get("Correction_Log", pd.DataFrame()).copy()
    corrections = tables.get("Corrections", pd.DataFrame()).copy()
    corrected_forms, correction_stats = apply_corrections(
        raw_forms, [correction_log, corrections]
    )
    forms = enrich_forms(corrected_forms, sample)
    score_long = build_score_long(forms)
    coverage = build_coverage(sample, forms)
    qa = prepare_qa(tables.get("QA_Log", pd.DataFrame()), sample)
    return AppData(
        tables=tables,
        forms=forms,
        sample=sample,
        qa=qa,
        correction_log=correction_log,
        corrections=corrections,
        score_long=score_long,
        coverage=coverage,
        source_mode=source_mode,
        loaded_at=datetime.now(timezone.utc),
        correction_stats=correction_stats,
    )


def filter_data(data: AppData, filters: dict[str, Any]) -> AppData:
    provinces = set(filters.get("provinces") or [])
    districts = set(filters.get("districts") or [])
    assignees = set(filters.get("assignees") or [])
    wob_keys = set(filters.get("wob_keys") or [])
    selected_forms = set(filters.get("forms") or data.forms.keys())
    rounds = set(filters.get("rounds") or [])
    coverage_statuses = set(filters.get("coverage_statuses") or [])
    date_range = filters.get("date_range")
    date_start = date_end = None
    if date_range and len(date_range) == 2:
        date_start = pd.Timestamp(date_range[0])
        date_end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)

    def mask_sample(frame: pd.DataFrame) -> pd.Series:
        mask = pd.Series(True, index=frame.index)
        if provinces:
            mask &= frame["Province"].isin(provinces)
        if districts:
            mask &= frame["District"].isin(districts)
        if assignees:
            mask &= frame["Assigned_to"].isin(assignees)
        if wob_keys:
            mask &= frame["_wob_key"].isin(wob_keys)
        return mask

    sample = data.sample.loc[mask_sample(data.sample)].copy()
    permitted_keys = set(sample["_wob_key"])
    forms = {}
    for code, frame in data.forms.items():
        if code not in selected_forms:
            continue
        filtered = frame[frame["_wob_key"].isin(permitted_keys)].copy()
        if rounds:
            round_column = next(
                (
                    column
                    for column in filtered.columns
                    if normalize_label(column) == "assessment round"
                ),
                None,
            )
            if round_column:
                filtered = filtered[filtered[round_column].isin(rounds)]
        if date_start is not None and "_submission_time" in filtered:
            submitted = pd.to_datetime(filtered["_submission_time"], errors="coerce")
            filtered = filtered[
                submitted.ge(date_start) & submitted.lt(date_end)
            ]
        forms[code] = filtered

    if date_start is not None:
        dated_keys = {
            key
            for frame in forms.values()
            for key in frame["_wob_key"].dropna().astype(str)
            if key
        }
        permitted_keys &= dated_keys

    coverage = data.coverage[
        data.coverage["_wob_key"].isin(permitted_keys)
        & data.coverage["Form"].isin(selected_forms)
    ].copy()
    if coverage_statuses:
        matching_keys = set(
            coverage.loc[
                coverage["Status"].isin(coverage_statuses), "_wob_key"
            ]
        )
        permitted_keys &= matching_keys
        coverage = coverage[
            coverage["_wob_key"].isin(permitted_keys)
            & coverage["Status"].isin(coverage_statuses)
        ]

    sample = sample[sample["_wob_key"].isin(permitted_keys)].copy()
    forms = {
        code: frame[frame["_wob_key"].isin(permitted_keys)].copy()
        for code, frame in forms.items()
    }
    score_long = data.score_long[
        data.score_long["_wob_key"].isin(permitted_keys)
        & data.score_long["Form"].isin(selected_forms)
    ].copy()
    if rounds:
        score_long = score_long[score_long["Assessment Round"].isin(rounds)]
    if date_start is not None and "Submission time" in score_long:
        submitted = pd.to_datetime(score_long["Submission time"], errors="coerce")
        score_long = score_long[
            submitted.ge(date_start) & submitted.lt(date_end)
        ]
    qa = data.qa[data.qa["_wob_key"].isin(permitted_keys)].copy()
    return AppData(
        tables=data.tables,
        forms=forms,
        sample=sample,
        qa=qa,
        correction_log=data.correction_log,
        corrections=data.corrections,
        score_long=score_long,
        coverage=coverage,
        source_mode=data.source_mode,
        loaded_at=data.loaded_at,
        correction_stats=data.correction_stats,
    )


def all_rounds(data: AppData) -> list[str]:
    values = set()
    for frame in data.forms.values():
        for column in frame.columns:
            if normalize_label(column) == "assessment round":
                values.update(frame[column].dropna().astype(str))
    return sorted(values)


def submission_date_bounds(data: AppData) -> tuple[Any, Any] | None:
    dates = []
    for frame in data.forms.values():
        if "_submission_time" not in frame:
            continue
        series = pd.to_datetime(frame["_submission_time"], errors="coerce").dropna()
        if not series.empty:
            dates.extend([series.min().date(), series.max().date()])
    if not dates:
        return None
    return min(dates), max(dates)
