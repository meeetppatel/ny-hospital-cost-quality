
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
