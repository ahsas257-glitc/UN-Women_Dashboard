# UN Women WOB Intelligence Hub

A responsive, multi-page Streamlit dashboard for UN Women women-owned-business
(WOB) monitoring data.

## Experience

- Native Streamlit **Light** and **Dark** modes are available from the settings menu.
- Theme-aware liquid-glass surfaces, tables and charts adapt immediately without a custom theme toggle.
- Theme-specific, accessible chart palettes keep labels and values readable in both modes.
- The sidebar starts collapsed; global filters are submitted together to avoid unnecessary reruns.
- Layouts adapt across mobile, tablet, laptop and wide-monitor sizes.
- Motion is subtle and automatically disabled when the device requests reduced motion.

## Core data rules

- `Unique WOB ID` is the cross-form analytical key.
- Beneficiary names are resolved **only** from `Sample_Track`.
- Corrections are applied from `Correction_Log` and `Corrections` by form, submission key and field.
- Kobo `text` questions are excluded from analytics.
- XLSForms in `XLS_Forms` are the direct source for English labels, question types, choices, relevance expressions and constraints.
- Every questionnaire remains available in the catalog and analysis selector even when its data sheet is unavailable.
- Missing data-bearing sheets are shown as unavailable, never as zero-valued results.

## Pages

- **Overview** — switch between executive, geography and cohort analysis.
- **Beneficiary 360** — switch between journey, readiness and submission lineage.
- **Questionnaire analysis** — inspect every non-text question and compare it by province, district, assigned team or assessment round.
- **Data quality** — separate integrity, correction and coverage control views.
- **Questionnaire catalog** — XLSForm inventory and English data dictionary.

Global filters include province, district, assigned team, beneficiary, questionnaire, round,
coverage status and optional submission date. Less-used controls stay under **Advanced filters**.

## Performance

- Live workbook data is cached for two minutes as serialized application data.
- Google export parsing, XLSForm metadata and downstream transformations are cached separately.
- Precompiled, portable XLSForm metadata avoids opening all 13 questionnaires at every cold start.
- Correction processing skips non-actionable rows and reuses indexed field mappings.
- Global filters are batched in one form; inexpensive filtering happens after the cached source load.
- Only the selected analysis lens is rendered, so hidden charts are not computed.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run .\streamlit_app.py
```

The app connects directly to the project's public Google Sheet and refreshes its
workbook data every two minutes. There is no secret, environment, or offline data
override in the deployed application.

To rebuild the portable questionnaire catalog after changing an XLSForm:

```powershell
.\.venv\Scripts\python.exe .\tools\build_catalog.py
```

## Deploy on Streamlit Community Cloud

Use these deployment settings:

- Repository: `ahsas257-glitc/UN-Women_Dashboard`
- Branch: `main`
- Main file: `streamlit_app.py`
- Python: `3.12`

No Streamlit secret is required for the configured project workbook.

No `packages.txt`, `Procfile`, or custom health endpoint is required.

Local development and the production app must use the same Python version.
If a Cloud traceback shows a version other than Python 3.12, delete and redeploy
the app with **Advanced settings → Python 3.12**; Community Cloud does not change
an existing app's Python runtime in place. The `Cloud parity` GitHub Actions
workflow additionally verifies every page on Linux with Python 3.12 and 3.14.

## Data protection

The source workbook contains beneficiary-level information. The repository excludes
the raw workbook and local secrets. Restrict workbook access and Streamlit app sharing
to approved team members before production use. Record-level tables and downloads are
intended only for authorized users.
