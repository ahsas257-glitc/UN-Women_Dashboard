from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_WORKBOOK = ROOT / "data" / "raw" / "UN_Women_Live_Data.xlsx"
CATALOG_PATH = ROOT / "data" / "metadata" / "xlsform_catalog.json"
XLSFORM_DIR = ROOT / "XLS_Forms"
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_EXPORT_URL = (
    f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx"
    if GOOGLE_SHEET_ID
    else ""
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
