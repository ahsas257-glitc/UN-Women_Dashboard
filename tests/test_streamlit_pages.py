from __future__ import annotations

import unittest

from streamlit.testing.v1 import AppTest


class StreamlitPageTests(unittest.TestCase):
    def test_all_pages_render_and_analysis_builds_charts(self):
        app = AppTest.from_file("streamlit_app.py", default_timeout=120).run()
        self.assertFalse(app.exception)
        self.assertGreaterEqual(len(app.get("vega_lite_chart")), 3)
        self.assertIn(
            ("Average score", "1.48 / 2"),
            [(metric.label, metric.value) for metric in app.metric],
        )

        app.switch_page("app_pages/beneficiary.py").run()
        self.assertFalse(app.exception)

        app.switch_page("app_pages/quality.py").run()
        self.assertFalse(app.exception)

        # Reproduce Cloud sessions that retained a form which has no response sheet.
        app.session_state["global_forms"] = ["F03"]
        app.session_state["analysis_form"] = "F06"
        app.switch_page("app_pages/explorer.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["analysis_form"], "C1")
        self.assertEqual(len(app.selectbox[0].options), 9)
        self.assertGreaterEqual(len(app.get("vega_lite_chart")), 1)

        # Reproduce the reported Catalog KeyError with an invalid persisted value.
        app.session_state["catalog_view"] = "Data dictionary"
        app.session_state["catalog_form"] = "STALE"
        app.switch_page("app_pages/catalog_page.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["catalog_form"], "C1")
        self.assertEqual(len(app.selectbox[0].options), 13)


if __name__ == "__main__":
    unittest.main()
