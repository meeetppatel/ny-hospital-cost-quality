# NY Hospital Cost & Quality Variance

**Where do hospital cost and quality diverge across New York — and which signal
actually predicts quality?**

> **Finding:** Across 90 NY hospitals, patient-satisfaction ratings predict 30-day
> readmission performance (**r = −0.52, p < 0.001**), while Medicare payment per
> discharge does **not** (r = −0.06, n.s.). *Patient experience, not spending,
> signals clinical quality.* (Sept 2026 data refresh.)

**One-page memo:** [`docs/findings_memo.md`](docs/findings_memo.md) ·
**Interactive dashboard:** [Tableau Public](https://public.tableau.com/app/profile/meet.patel5823/viz/NYHospitalcostquality/Dashboard1) ·
**Refreshable report:** [`excel/NY_Hospital_Cost_Quality.xlsx`](excel/NY_Hospital_Cost_Quality.xlsx)

---

## What this project is

An analyst answering a real question — where cost and quality diverge across NY
hospitals — who happens to have a tested, automated data pipeline underneath the
answer. It combines three messy federal/public datasets, catches and documents
their data-quality problems, models them with dbt, tests them, and refreshes
itself weekly.

## The finding, briefly

- **Satisfaction predicts quality** (r = −0.52, p < 0.001) — and holds within NYC,
  the suburbs, and upstate separately, so it is not a geography artifact.
- **Cost does not** (r = −0.06, not significant). Paying more buys no better outcomes.
- **Honest caveat:** raw cost differences across NY are dominated by Medicare's
  geographic wage index (NYC is paid ~89% more per discharge than upstate), not
  efficiency. Details in [`docs/findings_memo.md`](docs/findings_memo.md) and
  [`docs/analysis_findings.md`](docs/analysis_findings.md).

## Architecture

```
CMS Provider Data API ─┐
CMS Medicare cost CSV ─┼──► Python ingest ──► BigQuery (raw, untouched)
8 hospital price files ┘                              │
                                                      ▼
                                    dbt staging (stg_*) — type, rename,
                                    handle suppression; unify 8 price schemas
                                                      │
                                                      ▼
                                    dbt intermediate (int_*) — aggregate to
                                    one row per hospital
                                                      │
                                                      ▼
                                    dbt mart (mart_hospital_cost_quality)
                                                      │
                    ┌─────────────────────────────────┼──────────────────────────┐
                    ▼                                 ▼                            ▼
             dbt tests (13) +                   Tableau dashboard          Excel + Power Query
             LLM failure triage                 (finding-led)              (refreshable report)
                    │
                    ▼
             GitHub Actions — weekly cron: re-ingest → dbt build → test →
             triage on failure → re-export
```

## Tech stack

Python (requests, pandas, scipy) · **BigQuery** (cloud warehouse) · **dbt**
(dbt-core + dbt-bigquery + dbt_utils) · **GitHub Actions** (weekly CI) ·
**Tableau Public** · **Excel + Power Query** · **Anthropic API** (test-failure triage)

## Data sources (all free, public, no registration)

| Source | Gives | Notes |
|---|---|---|
| CMS Provider Data Catalog (API) | readmissions, complications, HCAHPS | quality |
| CMS Medicare Inpatient Utilization & Payment (CSV) | payment per hospital per DRG | cost |
| Hospital price transparency files (8 NY hospitals) | negotiated rates | 3 incompatible schemas, ~11.9M rows |

## Data quality (a real deliverable)

10 documented findings in
[`docs/data_quality_findings.md`](docs/data_quality_findings.md), each with
evidence: three different provider-ID schemes across sources; 36% of readmission
values and 87% of HCAHPS rows structurally suppressed; three incompatible price
file layouts (tall CSV / 3,700-column wide CSV / nested JSON); encoding bugs and a
UTF-8 BOM that surfaced two steps from its cause.

## Testing + a caught defect

13 dbt tests (`not_null`, `unique`, `accepted_range`, `accepted_values`, plus a
singular integrity test). A defect was deliberately introduced and caught to prove
the tests work — see the caught-failure screenshot in [`docs/`](docs/) and the
LLM triage output in [`docs/llm_triage_log.md`](docs/llm_triage_log.md). On test
failure, an LLM classifies the failure and drafts a plain-English cause summary
**for human review** — deliberately kept out of any metric computation.

## Repo map

```
ingest_*.py / load_price_transparency.py   raw data → BigQuery
generate_wide_unpivot_sql.py               generates dbt SQL for wide price files
ny_hospital_dbt/                           dbt project (staging → intermediate → marts, tests)
analysis_cost_quality.py / _robustness.py  the statistical analysis
llm_triage.py                              LLM test-failure triage
export_for_tableau.py                      mart → CSV for BI tools
audit_pipeline.py                          end-to-end pipeline audit
.github/workflows/weekly_refresh.yml       weekly automation
docs/                                      findings memo, data-quality doc, analysis, triage log
tableau/ · excel/                          dashboard workbook + refreshable report
```

## Reproduce it

```bash
python -m venv venv && source venv/bin/activate
pip install requests pandas scipy google-cloud-bigquery dbt-core dbt-bigquery anthropic
# set GOOGLE_APPLICATION_CREDENTIALS + GCP_PROJECT_ID (BigQuery service account)
python ingest_cms_api.py && python ingest_medicare_inpatient.py
# (price files: download per docs, then load_price_transparency.py)
cd ny_hospital_dbt && dbt deps && dbt build     # builds models + runs 13 tests
```

## Limitations

Public CMS data gives vocabulary and a defensible finding, not clinical causation.
Analysis is scoped to 90 NY hospitals with sufficient Medicare volume. Cross-region
cost comparisons are confounded by the geographic wage index (stated, not hidden).
This is a portfolio project, not production experience.
