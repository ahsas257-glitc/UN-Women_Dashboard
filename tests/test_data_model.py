from __future__ import annotations

import unittest
import tomllib
from pathlib import Path

import pandas as pd

from src.catalog import analytic_questions, load_catalog
from src.config import (
    FORM_TITLES,
    PUBLIC_GOOGLE_SHEET_ID,
    TRACKED_FORMS,
    normalize_google_sheet_id,
)
from src.data import (
    _score_field_specs,
    configured_google_sheet_id,
    filter_data,
    load_app_data,
)


class DataModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_app_data()

    def test_catalog_contains_all_forms(self):
        self.assertEqual(set(load_catalog()), set(FORM_TITLES))
        self.assertTrue(
            all(
                Path(form["source_file"]).parent.name == "XLS_Forms"
                for form in load_catalog().values()
            )
        )

    def test_catalog_metadata_paths_are_portable(self):
        for form in load_catalog().values():
            source = str(form["source_file"]).replace("\\", "/")
            self.assertTrue(source.startswith("XLS_Forms/"))
            self.assertNotIn("C:/Users/", source)

    def test_sample_track_is_unique(self):
        self.assertFalse(self.data.sample["_wob_key"].duplicated().any())
        self.assertTrue((self.data.sample["_wob_key"] != "").all())

    def test_beneficiary_names_are_sample_track_names(self):
        names = self.data.sample.set_index("_wob_key")["Beneficiary Name"]
        for frame in self.data.forms.values():
            joined = frame[frame["_wob_key"].isin(names.index)]
            expected = joined["_wob_key"].map(names)
            self.assertTrue((joined["Beneficiary Name"] == expected).all())

    def test_coverage_has_one_row_per_tracked_form(self):
        expected = len(self.data.sample) * len(TRACKED_FORMS)
        self.assertEqual(len(self.data.coverage), expected)

    def test_scores_are_standardized(self):
        self.assertFalse(self.data.score_long.empty)
        self.assertTrue(self.data.score_long["Score"].between(0, 2).all())
        self.assertIn("Assigned to", self.data.score_long)

    def test_kobo_score_columns_have_metadata_fallback(self):
        frame = pd.DataFrame(
            {
                "c1_custom_score": [0, 1, 2, None],
                "c1_score_sum": [0, 1, 3, 4],
                "Scoring guide": ["text"] * 4,
            }
        )
        specs = _score_field_specs("C1", frame)
        self.assertIn(
            ("c1_custom_score", "c1_custom_score", "c1_custom_score"),
            specs,
        )
        self.assertFalse(any(column == "c1_score_sum" for column, _, _ in specs))

    def test_google_sheet_id_accepts_id_and_full_url(self):
        url = (
            "https://docs.google.com/spreadsheets/d/"
            f"{PUBLIC_GOOGLE_SHEET_ID}/edit?gid=1519603637#gid=1519603637"
        )
        self.assertEqual(normalize_google_sheet_id(url), PUBLIC_GOOGLE_SHEET_ID)
        self.assertEqual(
            normalize_google_sheet_id(PUBLIC_GOOGLE_SHEET_ID),
            PUBLIC_GOOGLE_SHEET_ID,
        )
        self.assertEqual(configured_google_sheet_id(), PUBLIC_GOOGLE_SHEET_ID)

    def test_advanced_filters_preserve_identity_rules(self):
        assignee = self.data.sample["Assigned_to"].dropna().astype(str).iloc[0]
        filtered = filter_data(
            self.data,
            {
                "assignees": [assignee],
                "coverage_statuses": ["Complete"],
            },
        )
        self.assertTrue(
            filtered.sample["Assigned_to"].astype(str).eq(assignee).all()
        )
        self.assertTrue(filtered.coverage["Status"].eq("Complete").all())

    def test_light_and_dark_themes_are_configured(self):
        config_path = Path(__file__).parents[1] / ".streamlit" / "config.toml"
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["theme"]["light"]["textColor"], "#0A0D14")
        self.assertEqual(config["theme"]["dark"]["textColor"], "#F8FAFF")

    def test_text_questions_are_not_analytic(self):
        for code in FORM_TITLES:
            self.assertTrue(
                all(question["_base_type"] != "text" for question in analytic_questions(code))
            )

    def test_sensitive_local_files_are_excluded_from_git(self):
        root = Path(__file__).parents[1]
        ignore = (root / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(".streamlit/secrets.toml", ignore)
        self.assertIn("data/raw/*.xlsx", ignore)
        config_source = (root / "src" / "config.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("GOOGLE_SHEET_ID"', config_source)
        self.assertIn("PUBLIC_GOOGLE_SHEET_ID", config_source)


if __name__ == "__main__":
    unittest.main()
