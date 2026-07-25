from __future__ import annotations

import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "data" / "metadata" / "xlsform_catalog.json"
XLSFORM_DIR = ROOT / "XLS_Forms"
PUBLIC_GOOGLE_SHEET_ID = "1yARHlwlttMV8aH3Gji9mLaqbyBDQijKJ6oTA_l0upK4"


def normalize_google_sheet_id(value: object) -> str:
    """Accept a bare spreadsheet ID or a standard Google Sheets URL."""
    text = str(value or "").strip()
    if not text:
        return ""
    url_match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", text)
    if url_match:
        return url_match.group(1)
    return text if re.fullmatch(r"[A-Za-z0-9_-]{20,}", text) else ""


GOOGLE_SHEET_ID = (
    normalize_google_sheet_id(os.getenv("GOOGLE_SHEET_ID"))
    or PUBLIC_GOOGLE_SHEET_ID
)

FORM_TITLES = {
    "C1": "Business formalization, legal compliance & tax readiness",
    "C2": "Digital marketing, social media & branding readiness",
    "C3": "FinTech, digital payments & HesabPay readiness",
    "C4": "Access to finance & loan readiness",
    "C5": "UNGM, procurement, proposal & quotation readiness",
    "C6": "Afghan Women Business Directory & e-commerce readiness",
    "C7": "Peer mentorship & ToT readiness",
    "F01": "WOB registration & business profile",
    "F02": "Training session monitoring & attendance",
    "F03": "Practical skills observation & verification",
    "F04": "Specialized business advisory follow-up",
    "F05": "Success story & outcome documentation",
    "F06": "Supervisor QA, back-check & evidence audit",
}

TRACKED_FORMS = ["F01", "F03", "C1", "C2", "C3", "C4", "C5", "C6", "C7"]
CAPACITY_FORMS = [f"C{i}" for i in range(1, 8)]
WOB_COLUMNS = [
    "Unique WOB ID",
    "Unique WOB Application ID",
    "Unique WOB Apllication ID",
    "WOB_ID",
]
