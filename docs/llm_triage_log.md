# LLM test-failure triage log

On a failed `dbt build`, `llm_triage.py` samples the failing rows from each
test's `store_failures` audit table and asks an LLM to (1) classify the failure
type and (2) draft a plain-English root-cause summary for review. The LLM only
classifies and explains — it never computes, adjusts, or invents a metric value,
and every entry is reviewed by a human before any action is taken.

A healthy pipeline produces no new entries here. The entry below is from a
**deliberately introduced test failure**, kept as a worked example of the full
test → store_failures → triage → human-review loop.

---

## Triage run 2026-09-17 10:57  (deliberate validation break)

### dbt_utils_accepted_range_mart__9f8c2193a8cc048af186bd727b2672c7

- Failing rows: 68
- Triaged: 2026-09-17 10:57



**Human review (required step).** This failure was introduced on purpose — an
`accepted_range` bound on the mart was tightened to confirm the tests, the
`store_failures` capture, and this triage loop all fire correctly. The LLM's
high-level classification (a test-threshold issue, not corrupt data) was correct.
Its guess at the *specific* column is an inference from the sampled rows, not
ground truth, so it was verified against the actual test definition before acting —
which is exactly why the LLM is scoped to classification only and never to the
numbers. The bound was reverted and the test passed on the next run.

> Housekeeping note: for a stretch, weekly builds re-surfaced this same audit
> table after an unrelated infrastructure issue — the raw price-transparency
> tables expired on BigQuery sandbox's mandatory 60-day clock, which made
> `dbt build` fail and re-ran triage against the leftover audit table. Fixed by
> making the price models opt-in, and `llm_triage.py` now ignores audit tables
> not written by the current run, so a stale table can't be re-triaged.
