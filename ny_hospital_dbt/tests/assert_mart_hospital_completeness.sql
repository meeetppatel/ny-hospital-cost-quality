-- Singular test: business-rule assertion on the mart.
-- A singular test PASSES when it returns ZERO rows; any returned row = a failure.
--
-- Rule: every hospital in the analytic-quality set (has core readmissions) must
-- also have a cost figure -- otherwise it can't appear in a cost/quality analysis.
-- This is a real integrity rule for the mart, and also serves as the project's
-- "deliberately break, catch, fix" demonstration (see docs/data_quality_findings.md
-- and the caught-defect screenshot in the README).

select
    ccn,
    hospital_name,
    has_core_readmissions,
    volume_weighted_avg_payment
from {{ ref('mart_hospital_cost_quality') }}
where has_core_readmissions = true
  and volume_weighted_avg_payment is null
