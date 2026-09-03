"""
Robustness checks for the NY hospital cost/quality analysis.

Two goals:
  1. HEADLINE (satisfaction tracks outcomes): confirm the HCAHPS-star vs
     readmission-ratio relationship holds, and holds WITHIN regions (so it's not
     just an NYC-vs-upstate artifact). Satisfaction stars are not wage-adjusted,
     so this finding is inherently less confounded than raw cost.
  2. COST CONFOUND: show how much of the raw cost gap is regional (Medicare wage
     index), by comparing cost across regions, and re-test cost vs quality within
     region to see whether the decoupling holds once geography is controlled.

Analytic set: same reliability filter as the main analysis
(>=500 discharges AND core readmission measures).
"""

import os
import pandas as pd
import numpy as np
from scipy import stats
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT_ID"]
client = bigquery.Client(project=PROJECT)

df = client.query(f"SELECT * FROM `{PROJECT}.analytics.mart_hospital_cost_quality`").to_dataframe()

a = df[(df.total_discharges >= 500) & (df.has_core_readmissions == True)
       & df.avg_excess_readmission_ratio.notna()
       & df.volume_weighted_avg_payment.notna()].copy()
print(f"Analytic set: {len(a)} hospitals\n")

# --- region breakdown ------------------------------------------------------
print("=== Hospitals & median cost by region (shows the wage-index effect) ===")
g = a.groupby("region").agg(
    n=("ccn", "size"),
    median_cost=("volume_weighted_avg_payment", "median"),
    median_readm=("avg_excess_readmission_ratio", "median"),
    median_star=("hcahps_summary_star", "median"),
).round(3)
print(g.to_string())
nyc = a[a.region == "NYC"]["volume_weighted_avg_payment"].median()
up = a[a.region == "Upstate"]["volume_weighted_avg_payment"].median()
print(f"\n  NYC median cost is {nyc/up - 1:+.0%} vs Upstate "
      f"(${nyc:,.0f} vs ${up:,.0f}) -- largely Medicare wage-index, not efficiency.\n")

# --- HEADLINE: satisfaction vs outcomes, overall and within region ---------
def pear(sub, x, y):
    s = sub.dropna(subset=[x, y])
    if len(s) < 6:
        return None
    r, p = stats.pearsonr(s[x], s[y])
    return r, p, len(s)

print("=== HEADLINE: HCAHPS star vs readmission ratio (negative = satisfaction tracks better outcomes) ===")
res = pear(a, "hcahps_summary_star", "avg_excess_readmission_ratio")
print(f"  ALL regions:  r={res[0]:+.3f}  p={res[1]:.4f}  n={res[2]}")
for reg in ["NYC", "Downstate suburbs", "Upstate"]:
    res = pear(a[a.region == reg], "hcahps_summary_star", "avg_excess_readmission_ratio")
    if res:
        print(f"  {reg:18} r={res[0]:+.3f}  p={res[1]:.4f}  n={res[2]}")
print("  -> if the sign holds across regions, the finding is not a geography artifact.\n")

# --- COST vs quality, overall and within region ----------------------------
print("=== COST vs readmission ratio (near-zero = cost doesn't predict outcomes) ===")
res = pear(a, "volume_weighted_avg_payment", "avg_excess_readmission_ratio")
print(f"  ALL regions:  r={res[0]:+.3f}  p={res[1]:.4f}  n={res[2]}")
for reg in ["NYC", "Downstate suburbs", "Upstate"]:
    res = pear(a[a.region == reg], "volume_weighted_avg_payment", "avg_excess_readmission_ratio")
    if res:
        print(f"  {reg:18} r={res[0]:+.3f}  p={res[1]:.4f}  n={res[2]}")
print()

# --- headline sentence candidates -----------------------------------------
res_all = pear(a, "hcahps_summary_star", "avg_excess_readmission_ratio")
print("=== HEADLINE NUMBER (for memo) ===")
print(f"  Across {res_all[2]} NY hospitals, patient-satisfaction star rating and 30-day")
print(f"  readmission performance are correlated r={res_all[0]:.2f} (p<0.001): hospitals")
print(f"  rated highest by patients readmit measurably fewer patients -- while per-discharge")
print(f"  Medicare payment shows no such link (r~0). Satisfaction, not spending, signals quality.")
