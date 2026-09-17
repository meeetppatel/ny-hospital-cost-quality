"""
Export the cost/quality mart to a CSV for Tableau Public.

Tableau Public cannot hold a live BigQuery connection, so it reads a static
file. This exports all 125 NY hospitals with cost + quality measures, plus
reliability flags (is_analytic, discharge volume, region) so the dashboard can
filter to the reliable set OR show what was excluded and why.

Re-run this after any pipeline refresh to update the file, then refresh the
extract in Tableau. Output: tableau/hospital_cost_quality.csv

Run: python export_for_tableau.py
"""
import os
from google.cloud import bigquery

P = os.environ["GCP_PROJECT_ID"]
c = bigquery.Client(project=P)

OUT_DIR = "tableau"
os.makedirs(OUT_DIR, exist_ok=True)

# All 125 hospitals, cleaned column names, with a reliability flag matching the
# analysis filter (>=500 discharges AND core readmission measures present).
df = c.query(f"""
    SELECT
        ccn,
        hospital_name,
        city,
        region,
        total_discharges,
        volume_weighted_avg_payment          AS avg_payment_per_discharge,
        avg_excess_readmission_ratio         AS readmission_ratio,
        hcahps_summary_star                  AS patient_satisfaction_star,
        patient_safety_psi90,
        mortality_30_pneumonia,
        has_core_readmissions,
        (total_discharges >= 500 AND has_core_readmissions) AS is_analytic
    FROM `{P}.analytics.mart_hospital_cost_quality`
    ORDER BY avg_payment_per_discharge DESC
""").to_dataframe()

path = os.path.join(OUT_DIR, "hospital_cost_quality.csv")
df.to_csv(path, index=False)
print(f"Wrote {len(df)} hospitals to {path}")
print(f"  analytic (reliable) hospitals: {int(df.is_analytic.sum())}")
print(f"  columns: {list(df.columns)}")
