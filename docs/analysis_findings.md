# Analysis Findings — NY Hospital Cost & Quality

**Author:** Meet Patel · **Data version:** November 2026 CMS refresh (via the weekly
automated pipeline). Figures update as CMS republishes; see note at the end.
**Analytic set:** 90 NY hospitals (>=500 reported Medicare discharges AND the 3 core
readmission measures present), filtered from 125 NY hospitals with Medicare cost data.
Reliability filter excludes 35 low-volume / incomplete-quality hospitals.

## Headline finding

**Patient experience, not spending, is the signal of clinical quality.**

Across 90 NY hospitals, HCAHPS patient-satisfaction star rating predicts 30-day
excess readmission performance at **r = -0.40 (p < 0.001)** — hospitals patients
rate highest readmit measurably fewer patients. Medicare per-discharge payment
shows **no such link (r = -0.06, not significant)**: higher spending does not buy
better outcomes.

## Robustness — the satisfaction→outcomes link holds where there is variance to detect it

Broken out by region, the negative correlation is strong and significant in the
two higher-variance regions, and flat upstate:

| Region | r (star vs readmission) | p | n |
|---|---|---|---|
| All NY | -0.40 | <0.001 | 90 |
| NYC | -0.61 | 0.001 | 25 |
| Downstate suburbs | -0.50 | 0.008 | 27 |
| Upstate | -0.07 | 0.68 (ns) | 38 |

Significant and negative in NYC and the downstate suburbs. Upstate the association
is essentially flat (r = -0.07, not significant): upstate hospitals cluster tightly
on both satisfaction and readmissions, so there is little variance left to detect a
relationship. The link is not a pure geography artifact — it reproduces independently
in the two regions that have spread — but it is reported honestly that upstate does
not show it. (At earlier refreshes upstate was weakly directional at r = -0.29; it
has since flattened, which is the kind of drift a live pipeline exposes.)

## Cost vs quality is decoupled — with a geographic caveat

Cost vs readmissions is near-zero overall (r = -0.06, ns) and stays weak/non-
significant within each region (NYC r=-0.36 p=0.08; suburbs r=+0.09 ns; upstate
r=-0.28 p=0.09). Spending is not a quality signal.

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

## Note on data versioning (this is a live pipeline)

These figures come from a weekly automated refresh (GitHub Actions → re-ingest CMS
data → dbt build + tests → re-export). When CMS republishes source data, the exact
coefficients move: earlier snapshots showed the headline at r = -0.44, then r = -0.52,
and the November 2026 refresh puts it at r = -0.40. The **finding is stable and
directional** — satisfaction predicts quality, cost does not — even as the point
estimate updates. Deliverables cite the current value with its data date rather than
a frozen number.
