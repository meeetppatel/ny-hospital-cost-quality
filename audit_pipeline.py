"""
End-to-end pipeline audit for the NY hospital cost/quality project.
Verifies every layer from raw through the headline finding, so nothing is
silently wrong before Week 3 deliverables are built on top.
Run: python audit_pipeline.py
"""
import os
import pandas as pd
from scipy import stats
from google.cloud import bigquery

P = os.environ["GCP_PROJECT_ID"]
c = bigquery.Client(project=P)
def q(s): return list(c.query(s).result())

print("=== 1. Tables/views present ===")
for ds in ["raw", "analytics"]:
    names = [t.table_id for t in c.list_tables(ds)]
    print(f"  {ds}: {len(names)} objects")

print("\n=== 2. Raw -> staging row preservation (CMS) ===")
for raw, stg in [("hospital_readmissions", "stg_hospital_readmissions"),
                 ("hospital_complications", "stg_hospital_complications"),
                 ("hospital_hcahps", "stg_hospital_hcahps"),
                 ("medicare_inpatient_utilization", "stg_medicare_inpatient")]:
    r = q(f"SELECT COUNT(*) n FROM `{P}.raw.{raw}`")[0].n
    s = q(f"SELECT COUNT(*) n FROM `{P}.analytics.{stg}`")[0].n
    print(f"  {stg}: {'OK' if r == s else 'MISMATCH'} ({r:,} vs {s:,})")

print("\n=== 3. Mart integrity ===")
r = q(f"""SELECT COUNT(*) total, COUNT(DISTINCT ccn) dccn,
  COUNTIF(ccn IS NULL) null_ccn, COUNTIF(volume_weighted_avg_payment IS NULL) null_cost
FROM `{P}.analytics.mart_hospital_cost_quality`""")[0]
print(f"  rows={r.total} distinct_ccn={r.dccn} null_ccn={r.null_ccn} null_cost={r.null_cost}")
print(f"  ccn unique? {'YES' if r.total == r.dccn else 'NO - DUPLICATES'}")

print("\n=== 4. Headline finding reproduces ===")
df = c.query(f"SELECT * FROM `{P}.analytics.mart_hospital_cost_quality`").to_dataframe()
a = df[(df.total_discharges >= 500) & (df.has_core_readmissions == True)
       & df.avg_excess_readmission_ratio.notna() & df.volume_weighted_avg_payment.notna()]
sat = a.dropna(subset=["hcahps_summary_star"])
r1, p1 = stats.pearsonr(sat.hcahps_summary_star, sat.avg_excess_readmission_ratio)
r2, p2 = stats.pearsonr(a.volume_weighted_avg_payment, a.avg_excess_readmission_ratio)
print(f"  analytic n={len(a)}")
print(f"  satisfaction vs readmission: r={r1:.3f} p={p1:.5f}  (expect ~-0.44, p<0.001)")
print(f"  cost vs readmission:         r={r2:.3f} p={p2:.4f}  (expect ~-0.06, ns)")

print("\n=== 5. Unified price transparency table ===")
r = q(f"""SELECT COUNT(*) rows_n, COUNT(DISTINCT ccn) hospitals
FROM `{P}.analytics.stg_price_transparency_all`""")[0]
print(f"  rows={r.rows_n:,} hospitals={r.hospitals}  (expect ~11.86M, 8)")

print("\nAudit complete.")
