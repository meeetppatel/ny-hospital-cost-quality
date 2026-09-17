"""
LLM test-failure triage for the NY hospital dbt pipeline.

WHAT IT DOES
On a dbt test run with store_failures enabled, every test writes a table into
the `<schema>_dbt_test__audit` dataset -- but only FAILED tests' tables contain
rows. This script finds those non-empty audit tables (= the failures), samples a
few failing rows from each, and asks an LLM (Claude) to:
   1. classify the failure type (e.g. threshold-too-strict test-config issue vs
      genuine data corruption vs upstream source change), and
   2. write a short plain-English root-cause summary + suggested next action.
Results are appended to docs/llm_triage_log.md with a timestamp.

DESIGN PRINCIPLE (important, and a deliberate choice):
The LLM is used ONLY to classify and explain failures. It never computes,
adjusts, or invents any metric value. Keeping AI out of the numbers -- and being
able to say why -- signals more analytical judgment than the integration itself.

SETUP
    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...        # from console.anthropic.com
    # optional: export ANTHROPIC_MODEL=claude-3-5-haiku-latest  (override default)

USAGE
    python llm_triage.py
"""

import os
import sys
import json
import datetime
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT_ID"]
AUDIT_DATASET = "analytics_dbt_test__audit"
LOG_PATH = "docs/llm_triage_log.md"
SAMPLE_ROWS = 15
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

client = bigquery.Client(project=PROJECT)


def find_failed_tests():
    """Return [(test_name, row_count, sample_rows[])] for non-empty audit tables."""
    failures = []
    try:
        tables = list(client.list_tables(AUDIT_DATASET))
    except Exception:
        print(f"No audit dataset '{AUDIT_DATASET}' found. Run `dbt test` with "
              f"store_failures enabled first.")
        return failures

    for t in tables:
        full = f"{PROJECT}.{AUDIT_DATASET}.{t.table_id}"
        n = list(client.query(f"SELECT COUNT(*) c FROM `{full}`").result())[0].c
        if n > 0:
            rows = [dict(r) for r in
                    client.query(f"SELECT * FROM `{full}` LIMIT {SAMPLE_ROWS}").result()]
            failures.append((t.table_id, n, rows))
    return failures


def load_run_metadata():
    """Pull each failed test's human message (e.g. 'Got 68 results') from dbt's
    run_results.json, keyed by a normalized name for enrichment. Best-effort."""
    meta = {}
    path = "target/run_results.json"
    if not os.path.exists(path):
        return meta
    with open(path) as f:
        rr = json.load(f)
    for res in rr.get("results", []):
        if res.get("status") == "fail":
            uid = res.get("unique_id", "")
            name = uid.split(".")[2] if len(uid.split(".")) > 2 else uid
            meta[name] = res.get("message", "")
    return meta


def triage_with_llm(test_name, row_count, sample_rows, message):
    try:
        import anthropic
    except ImportError:
        print("ERROR: `pip install anthropic` first.")
        sys.exit(1)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: set ANTHROPIC_API_KEY (from console.anthropic.com).")
        sys.exit(1)

    ac = anthropic.Anthropic()
    prompt = f"""You are a data quality triage assistant for a dbt analytics pipeline
on NY hospital cost/quality data. A dbt test FAILED. Classify it and explain it.

Do NOT recompute, correct, or invent any metric values. Only classify and explain.

Test (audit table): {test_name}
dbt message: {message or "(not available)"}
Total failing rows: {row_count}
Sample of failing rows (JSON):
{json.dumps(sample_rows, indent=2, default=str)}

Respond in this exact structure:
FAILURE_TYPE: <one of: test-config-too-strict | genuine-data-issue | upstream-source-change | unclear>
ROOT_CAUSE: <2-3 sentences, plain English, for a non-technical reviewer>
SUGGESTED_ACTION: <1-2 sentences>
CONFIDENCE: <high | medium | low>"""

    resp = ac.messages.create(
        model=MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def main():
    failures = find_failed_tests()
    if not failures:
        print("No test failures found (no non-empty audit tables). Nothing to triage.")
        return

    meta = load_run_metadata()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    entries = []
    for test_name, n, rows in failures:
        # enrich with run_results message by loose prefix match
        msg = next((m for k, m in meta.items() if test_name[:30] in k or k[:30] in test_name), "")
        print(f"Triaging {test_name} ({n} failing rows)...")
        verdict = triage_with_llm(test_name, n, rows, msg)
        entries.append(f"### {test_name}\n\n"
                       f"- Failing rows: {n}\n"
                       f"- Triaged: {ts}\n\n"
                       f"```\n{verdict}\n```\n")

    with open(LOG_PATH, "a") as f:
        f.write(f"\n## Triage run {ts}\n\n" + "\n".join(entries))

    print(f"\nWrote {len(entries)} triage ent(ies) to {LOG_PATH}")
    for e in entries:
        print("\n" + e)


if __name__ == "__main__":
    main()
