"""
Core cost vs quality analysis for NY hospitals.

Reads mart_hospital_cost_quality from BigQuery and answers the project's
central question: where does cost diverge from quality across NY hospitals?

Steps:
  1. Justify the volume threshold from the discharge distribution.
  2. Apply the reliability filter (>=500 discharges AND core readmission set).
  3. Headline relationship: does higher cost buy better quality? Correlate
     volume-weighted payment vs excess readmission ratio (higher ratio = worse).
  4. Quadrant analysis: median-split cost x quality -> name the hospitals in the
     "high cost / poor quality" and "low cost / good quality" corners.
  5. Sub-question: does patient satisfaction (HCAHPS star) track clinical
     outcomes (readmission ratio)?

Outputs numbers to the console; these feed the findings memo and dashboard.
Requires: pandas, numpy, scipy, pandas-gbq (pip install scipy if missing).
"""

import os
import pandas as pd
import numpy as np
from scipy import stats
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT_ID"]
client = bigquery.Client(project=PROJECT)

df = client.query(f"""
    SELECT * FROM `{PROJECT}.analytics.mart_hospital_cost_quality`
""").to_dataframe()

print(f"Loaded {len(df)} NY hospitals from mart.\n")

# --- 1. Discharge distribution (justify the threshold) --------------------
print("=== Discharge distribution (reported DRG discharges per hospital) ===")
print(df["total_discharges"].describe().round(0).to_string())
for thr in [100, 250, 500, 1000]:
    print(f"  hospitals with >= {thr} discharges: {(df.total_discharges >= thr).sum()}")
print()

# --- 2. Reliability filter -------------------------------------------------
MIN_DISCHARGES = 500
analytic = df[
    (df.total_discharges >= MIN_DISCHARGES)
    & (df.has_core_readmissions == True)
    & (df.avg_excess_readmission_ratio.notna())
    & (df.volume_weighted_avg_payment.notna())
].copy()
print(f"=== Analytic set: {len(analytic)} hospitals "
      f"(>= {MIN_DISCHARGES} discharges AND core readmission measures) ===")
print(f"    excluded {len(df) - len(analytic)} of {len(df)} for low volume / missing quality\n")

# --- 3. Headline relationship: cost vs quality ----------------------------
cost = analytic["volume_weighted_avg_payment"]
readm = analytic["avg_excess_readmission_ratio"]   # higher = worse quality

r, p = stats.pearsonr(cost, readm)
print("=== HEADLINE: does higher cost buy better quality? ===")
print(f"    Pearson r (cost vs excess readmission ratio) = {r:.3f}  (p = {p:.4f})")
print(f"    Interpretation: {'positive' if r>0 else 'negative or ~zero'} -- "
      f"{'higher cost associates with WORSE readmissions' if r>0.1 else 'little/no linear link between cost and readmissions'}")
print()

# --- 4. Quadrant analysis (median split) ----------------------------------
cost_med = cost.median()
readm_med = readm.median()
analytic["cost_tier"] = np.where(cost >= cost_med, "high_cost", "low_cost")
analytic["qual_tier"] = np.where(readm >= readm_med, "poor_quality", "good_quality")
analytic["quadrant"] = analytic["cost_tier"] + " / " + analytic["qual_tier"]

print(f"=== Quadrants (median cost=${cost_med:,.0f}, median readm ratio={readm_med:.3f}) ===")
print(analytic["quadrant"].value_counts().to_string())
print()

def show(quad, label):
    sub = analytic[analytic.quadrant == quad].sort_values("volume_weighted_avg_payment")
    print(f"--- {label} ({quad}): {len(sub)} hospitals ---")
    for _, r_ in sub.iterrows():
        print(f"    {r_.hospital_name[:44]:46} ${r_.volume_weighted_avg_payment:>9,.0f}  "
              f"readm={r_.avg_excess_readmission_ratio:.3f}  star={r_.hcahps_summary_star}")
    print()

show("low_cost / good_quality", "BEST VALUE (low cost, better-than-expected outcomes)")
show("high_cost / poor_quality", "WORST VALUE (high cost, worse-than-expected outcomes)")

# --- 5. Sub-question: does satisfaction track clinical outcomes? ----------
sat = analytic.dropna(subset=["hcahps_summary_star"])
if len(sat) > 5:
    r2, p2 = stats.pearsonr(sat["hcahps_summary_star"], sat["avg_excess_readmission_ratio"])
    print("=== SUB-QUESTION: does HCAHPS satisfaction track clinical outcomes? ===")
    print(f"    Pearson r (star rating vs readmission ratio) = {r2:.3f}  (p = {p2:.4f})  n={len(sat)}")
    print(f"    (negative r = higher satisfaction associates with fewer readmissions)")
print()

# --- headline number candidates -------------------------------------------
best = analytic[analytic.quadrant == "low_cost / good_quality"]
worst = analytic[analytic.quadrant == "high_cost / poor_quality"]
if len(best) and len(worst):
    gap = worst.volume_weighted_avg_payment.mean() - best.volume_weighted_avg_payment.mean()
    pct = gap / best.volume_weighted_avg_payment.mean() * 100
    print("=== CANDIDATE HEADLINE NUMBERS ===")
    print(f"    Worst-value hospitals cost on average ${worst.volume_weighted_avg_payment.mean():,.0f}/discharge; "
          f"best-value ${best.volume_weighted_avg_payment.mean():,.0f}.")
    print(f"    -> {pct:.0f}% more spending for WORSE outcomes ({len(worst)} vs {len(best)} hospitals).")
