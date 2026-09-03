# Analysis Findings — NY Hospital Cost & Quality

**Author:** Meet Patel · **Date:** 2026-09-02
**Analytic set:** 90 NY hospitals (>=500 reported Medicare discharges AND the 3 core
readmission measures present), filtered from 125 NY hospitals with Medicare cost data.
Reliability filter excludes 35 low-volume / incomplete-quality hospitals.

## Headline finding

**Patient experience, not spending, is the signal of clinical quality.**

Across 90 NY hospitals, HCAHPS patient-satisfaction star rating predicts 30-day
excess readmission performance at **r = -0.44 (p < 0.001)** — hospitals patients
rate highest readmit measurably fewer patients. Medicare per-discharge payment
shows **no such link (r = -0.06, not significant)**: higher spending does not buy
better outcomes.

## Robustness — the satisfaction→outcomes link is not a geography artifact

The negative correlation holds in **every region** (direction consistent):

| Region | r (star vs readmission) | p | n |
|---|---|---|---|
| All NY | -0.44 | <0.001 | 90 |
| NYC | -0.64 | 0.0005 | 25 |
| Downstate suburbs | -0.44 | 0.022 | 27 |
| Upstate | -0.18 | 0.27 (ns) | 38 |

Significant in NYC and the downstate suburbs; directionally consistent but not
significant upstate (upstate hospitals cluster tightly on both measures, leaving
little variance to detect). Reporting the upstate non-significance honestly.

## Cost vs quality is decoupled — with a geographic caveat

Cost vs readmissions is near-zero overall (r = -0.06, ns) and stays weak/non-
significant within each region. Spending is not a quality signal.

**Important confound (stated, not hidden):** raw per-discharge Medicare payment is
adjusted by CMS's geographic wage index. NYC hospitals are paid **+89% more per
discharge than upstate** ($29,531 vs $15,600 median) — largely wage index and
patient complexity, NOT efficiency. Therefore cross-region cost comparisons (and
the tempting "high-cost NYC safety-net hospitals look wasteful" read) are dominated
by geography and case mix. We do NOT claim these hospitals are inefficient; we claim
cost and outcomes are decoupled, which the within-region tests support.

## Method notes

- Cost = volume-weighted average of avg_total_payment across DRGs (weighted by
  discharges), so it reflects real case mix.
- Quality anchor = average excess readmission ratio across a hospital's populated
  condition measures (>1.0 worse than expected, <1.0 better).
- Suppressed CMS values (N/A, "Too Few To Report") mapped to NULL and excluded, not
  treated as zero. ~36% of raw readmission rows and ~87% of HCAHPS rows are
  structurally suppressed (see docs/data_quality_findings.md).
- Correlations via scipy.stats.pearsonr. See analysis_cost_quality.py and
  analysis_robustness.py.
