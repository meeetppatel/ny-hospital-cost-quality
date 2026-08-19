# Data Quality Findings — NY Hospital Cost & Quality Project

**Author:** Meet Patel
**Date:** 2026-08-19
**Stage:** Raw ingest complete (12 tables in BigQuery `raw` dataset); pre-transformation.
**Purpose:** Catalog every data quality issue found in the raw sources *before* any
cleaning or typing, so that downstream transformation (dbt staging) is a deliberate,
documented response to known problems rather than silent guesswork. Each finding below
notes the evidence, the impact on analysis, and the planned handling.

---

## Sources profiled

| Source | BigQuery table(s) | Rows | Provider ID scheme |
|---|---|---|---|
| CMS Hospital Readmissions Reduction Program | `hospital_readmissions` | 18,330 | CCN (as `facility_id`) |
| CMS Complications & Deaths | `hospital_complications` | 95,840 | CCN (as `facility_id`) |
| CMS HCAHPS patient survey | `hospital_hcahps` | 325,856 | CCN (as `facility_id`) |
| CMS Medicare Inpatient Utilization & Payment | `medicare_inpatient_utilization` | 145,879 | CCN (as `Rndrng_Prvdr_CCN`) |
| Hospital price transparency (8 NY hospitals) | `price_tx_*` (8 tables) | ~4.26M combined | EIN (in filename); CCN not present |

All sources loaded **raw and untyped** — every column stored as STRING — to preserve
suppression codes, footnotes, and malformed values that type-coercion at load would
have silently dropped or nulled.

---

## Finding 1 — Three different provider identifier schemes across sources

**Severity: High** (this is the central join problem of the project.)

The same real-world hospital is identified three different ways:

- **CMS quality data** (readmissions, complications, HCAHPS) uses **CCN** (CMS
  Certification Number), stored in a field named `facility_id`.
- **CMS cost data** (Medicare inpatient) uses **CCN**, stored in a differently-named
  field, `Rndrng_Prvdr_CCN`.
- **Price transparency files** are named and identified by **EIN** (employer tax ID)
  and/or **Type 2 NPI** — **CCN does not appear in the price files at all**.

**Evidence:** CCN values match in format across the two CMS sources
(e.g. `010001`, 6-digit, zero-padded string in both). But the price transparency files
carry no CCN; they must be linked to CMS data via a hand-built EIN/NPI → CCN crosswalk.

**Impact:** CMS cost and quality data can be joined directly on CCN (good). Price
transparency data cannot — it requires a manual crosswalk for the 8 hospitals in scope.

**Planned handling:** Rename both CMS ID fields to a common `ccn` in dbt staging.
Build an explicit 8-row hospital dimension table mapping each price-transparency hospital
(by EIN/name) to its CCN.

---

## Finding 2 — Field names differ across sources for identical concepts

**Severity: Medium**

Even where values agree, column names do not. `facility_id` (CMS quality) and
`Rndrng_Prvdr_CCN` (CMS cost) hold the same CCN values but under different names.
State is `state` in quality data and `Rndrng_Prvdr_State_Abrvtn` in cost data.

**Impact:** No source can be joined or unioned without first standardizing names.

**Planned handling:** dbt staging models rename every field to a consistent snake_case
convention (`ccn`, `hospital_name`, `state`, etc.).

---

## Finding 3 — Hospital name casing and formatting is inconsistent across sources

**Severity: Medium**

The same hospital appears as `SOUTHEAST HEALTH MEDICAL CENTER` (all-caps) in CMS quality
data and `Southeast Health Medical Center` (title-case) in CMS cost data. Price
transparency files use yet other formats, including pipe-delimited multi-campus names
(e.g. NewYork-Presbyterian lists 7 campuses in a single `hospital_name` field).

**Impact:** Hospital name cannot be used as a join key, and a single canonical display
name must be chosen for dashboards/reports.

**Planned handling:** Join on CCN, never on name. Pick CMS cost data (title-case) as the
canonical source for display names.

---

## Finding 4 — Suppressed values dominate the quality metrics

**Severity: High** (naive aggregation would produce a wrong headline number.)

Large fractions of the quality data carry non-numeric suppression placeholders in
otherwise-numeric columns:

- **Readmissions:** 6,610 of 18,330 rows (**36%**) have
  `excess_readmission_ratio = 'N/A'`.
- **HCAHPS:** of 325,856 rows, **282,728 (87%)** are `'Not Applicable'` and another
  14,544 are `'Not Available'` — leaving **under 9%** of rows with a usable star rating.

**Evidence:** Distinct-value counts run directly against the raw tables (see
`profiling queries` in project history).

**Impact:** Any average, correlation, or ranking must first filter to genuinely
populated rows. Treating `'N/A'` / `'Not Applicable'` as 0 — or letting a numeric cast
silently null them — would badly distort results. This is precisely why the raw layer
keeps these columns as STRING.

**Planned handling:** In dbt staging, cast numerics with `SAFE_CAST`, explicitly mapping
known placeholders to NULL, and retain a boolean `is_suppressed` flag so suppression is
analyzable rather than hidden.

---

## Finding 5 — Footnote codes encode suppression reasons in a separate column

**Severity: Medium**

Readmissions data carries CMS footnote codes indicating *why* a value is suppressed or
caveated:

| footnote | rows | meaning (CMS data dictionary) |
|---|---|---|
| (blank) | 11,343 | no caveat |
| 5 | 3,255 | results not available / too few cases |
| 1 | 3,150 | too few cases/measures to report |
| 29 | 377 | (measure-specific caveat) |
| 7 | 205 | (measure-specific caveat) |

**Impact:** Footnotes explain the suppression seen in Finding 4 and must be preserved to
justify why rows were excluded from analysis.

**Planned handling:** Carry footnote codes through staging as-is; reference them in the
methodology section of the final memo when explaining excluded rows.

---

## Finding 6 — NY hospital coverage differs by source

**Severity: Medium** (constrains the analyzable universe.)

Distinct NY hospitals present, by source:

| Source | Distinct NY hospitals (CCN) |
|---|---|
| Complications & Deaths | 162 |
| HCAHPS | 162 |
| Readmissions | 129 |
| Medicare Inpatient (cost) | 125 |

**Impact:** A cost-vs-quality join keeps only hospitals present in *both* the cost source
and the relevant quality source, so the analyzable set is smaller than any single source
(≈125 or fewer, before further quality-suppression filtering). This must be stated as a
limitation in the memo.

**Planned handling:** Report the final joined-and-populated hospital count explicitly;
do not imply coverage of all NY hospitals.

---

## Finding 7 — Price transparency files use fundamentally different schemas

**Severity: High** (blocks any single-schema load; drives the one-table-per-hospital design.)

The 8 hospitals publish the same CMS-mandated data in incompatible shapes:

- **Tall layout** (one row per payer/plan): Rochester General (27 cols), Montefiore
  (24 cols, 3.5M rows), Brooklyn Hospital Center.
- **Wide layout** (one *column* per payer-plan combination): NYU Langone
  (**3,733 columns**), Albany Medical Center (355 cols), Flushing Hospital (944 cols).
- **JSON, deeply nested**: NewYork-Presbyterian and Mount Sinai (landed as a single
  raw-JSON row each; flattening deferred to dbt).

**Impact:** These cannot be unioned into one table without reshaping. Forcing a shared
schema at load would mean silently reshaping data before inspection.

**Planned handling:** One raw table per hospital (done). dbt staging normalizes each into
a common long format: `(ccn, code, code_type, payer, plan, negotiated_rate, ...)`.

---

## Finding 8 — Raw CSV headers contain characters illegal in BigQuery column names

**Severity: Medium** (blocked load until handled.)

Several hospitals encode payer/plan metadata directly into pipe-delimited column names,
e.g. `standard_charge|Cigna|CIGNA MANAGED CARE/POS 1046|negotiated_dollar`. BigQuery
permits only letters, digits, and underscores in column names.

**Evidence:** Columns requiring sanitization at load — NYU Langone: 3,727; Albany: 348;
Flushing: 937; Brooklyn: 307; Montefiore: 14; Rochester: 16.

**Impact:** Load fails outright until column names are sanitized.

**Planned handling:** Sanitize at load (`|`, `/`, spaces, parens → `_`), logging every
rename so the original payer/plan encoding is recoverable. Because the payer/plan info
lives *in the column name*, the dbt un-pivot must parse it back out of the sanitized name.

---

## Finding 9 — Character-encoding inconsistencies across files

**Severity: Low–Medium**

- **NYU Langone CSV** failed strict UTF-8 decoding and required a Latin-1 fallback,
  indicating a non-UTF-8 source encoding.
- **Montefiore CSV** contains a mangled em-dash (`â€“`) in its hospital name field — a
  classic double-encoding artifact — left uncorrected in the raw layer by design.
- **Mount Sinai JSON** ships with a UTF-8 byte-order-mark (BOM). Notably, Python's plain
  `utf-8` decoder does *not* error on a BOM (it decodes it as an invisible U+FEFF
  character), so the failure did not surface at read time — it surfaced two steps later
  at `json.loads()`. Fixed by reading with `utf-8-sig`. **Lesson: an error can surface
  far from its actual cause.**

**Impact:** Silent data corruption or load failure if not handled per-file.

**Planned handling:** Read JSON with `utf-8-sig`; fall back to Latin-1 for CSVs that fail
strict UTF-8. Flag the Montefiore mojibake for cleanup in dbt (not silently in ingest).

---

## Finding 10 — Price-transparency hospital identity is separated from the charge rows

**Severity: Medium**

In the tall CSV files (e.g. Rochester General), the hospital identity fields
(`hospital_name`, `license_number`, `type_2_npi`, attestation) occupy a two-row metadata
preamble *above* the real column header. After skipping the preamble to read the charge
records, those identity fields are no longer present as queryable columns — the charge
table has `description`, `code_1`, `payer_name`, `standard_charge_gross`, etc., but not
the hospital's own name.

**Impact:** Each price row cannot be attributed to its hospital from the table alone.

**Planned handling:** Attach hospital identity (CCN, name) via the hospital dimension
table keyed on the known source file, rather than relying on in-table identity.

---

## Summary of planned handling (feeds dbt staging design)

1. Rename all IDs to `ccn`; standardize field names to snake_case.
2. Build an 8-row hospital dimension mapping EIN/name → CCN, with canonical display names.
3. `SAFE_CAST` numerics; map suppression placeholders to NULL; keep `is_suppressed` flags.
4. Preserve footnote codes for methodology justification.
5. Normalize all 8 price files (tall, wide, JSON) into one common long schema.
6. Parse payer/plan back out of sanitized wide-format column names.
7. Report the true joined-and-populated NY hospital count; state coverage limits honestly.
