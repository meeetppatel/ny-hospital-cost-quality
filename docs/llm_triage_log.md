
## Triage run 2026-09-17 10:57

### dbt_utils_accepted_range_mart__9f8c2193a8cc048af186bd727b2672c7

- Failing rows: 68
- Triaged: 2026-09-17 10:57

```
FAILURE_TYPE: test-config-too-strict

ROOT_CAUSE: The `accepted_range` test is flagging 68 hospitals with `hcahps_summary_star` values of 1 or 2, which appear to be legitimate data from CMS Hospital Compare (star ratings legitimately range from 1-5). The test's upper or lower bounds are likely misconfigured and rejecting valid quality ratings that fall outside an overly narrow range.

SUGGESTED_ACTION: Review the dbt test configuration for `hcahps_summary_star` to confirm the acceptable range aligns with CMS's official 1-5 star rating scale. Adjust the test bounds if they are incorrectly excluding valid star ratings.

CONFIDENCE: high
```

## Triage run 2026-10-12 14:09

### dbt_utils_accepted_range_mart__9f8c2193a8cc048af186bd727b2672c7

- Failing rows: 68
- Triaged: 2026-10-12 14:09

```
FAILURE_TYPE: test-config-too-strict

ROOT_CAUSE: The dbt_utils_accepted_range test is failing because 68 hospitals have `hcahps_summary_star` values of 1 or 2, which fall outside the expected range configured in the test. These are legitimate quality star ratings from CMS data (valid values are 1-5 stars), indicating the test's acceptable range bounds are incorrectly defined—likely set to exclude values below 3 or above a certain threshold.

SUGGESTED_ACTION: Review and adjust the `accepted_range` configuration for the `hcahps_summary_star` column to include the full valid CMS rating scale (1-5 stars), or confirm with stakeholders whether hospitals with 1-2 star ratings should legitimately be in this mart.

CONFIDENCE: high
```
