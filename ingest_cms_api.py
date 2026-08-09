"""
Ingest CMS Provider Data Catalog datasets (Hospital Readmissions, Complications
& Deaths, HCAHPS patient satisfaction) into BigQuery, RAW and UNTOUCHED.

Why raw: the project's data-quality narrative depends on mess (footnote codes,
suppressed values, inconsistent facility naming) entering the warehouse and
being caught downstream in dbt staging models — not being silently cleaned
here at ingest.

Usage:
    python ingest_cms_api.py

Requires:
    GOOGLE_APPLICATION_CREDENTIALS env var pointing at your service account
    JSON key (see keys/gcp-key.json), and GCP_PROJECT_ID set below or via env.
"""

import os
import sys
import time
import requests
import pandas as pd
from google.cloud import bigquery

# ---- Config ---------------------------------------------------------------

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "ny-hospital-cost-quality")
BQ_DATASET = "raw"  # raw dataset in BigQuery — all tables land here untouched

# CMS Provider Data Catalog datastore API (verified live, no API key needed)
CMS_DATASTORE_BASE = "https://data.cms.gov/provider-data/api/1/datastore/query"

DATASETS = {
    "hospital_readmissions": "9n3s-kdb3",   # Hospital Readmissions Reduction Program
    "hospital_complications": "ynj2-r877",  # Complications and Deaths - Hospital
    "hospital_hcahps": "dgck-syfz",         # Patient survey (HCAHPS) - Hospital
}

PAGE_SIZE = 500  # conservative; provider-data datastore page-size ceiling is unconfirmed


# ---- Fetch ------------------------------------------------------------------

def fetch_dataset(dataset_id: str) -> pd.DataFrame:
    """Pull every row of a CMS provider-data dataset via paginated GET requests."""
    all_rows = []
    offset = 0

    while True:
        url = f"{CMS_DATASTORE_BASE}/{dataset_id}/0"
        params = {"limit": PAGE_SIZE, "offset": offset}
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        payload = resp.json()

        rows = payload.get("results", [])
        if not rows:
            break

        all_rows.extend(rows)
        print(f"    fetched {len(all_rows)} rows so far (offset={offset})")

        if len(rows) < PAGE_SIZE:
            break  # last page

        offset += PAGE_SIZE
        time.sleep(0.2)  # be polite to the API

    return pd.DataFrame(all_rows)


# ---- Load to BigQuery -------------------------------------------------------

def load_to_bigquery(df: pd.DataFrame, table_name: str, client: bigquery.Client):
    """Land a DataFrame into BigQuery raw dataset, replacing prior contents.

    Every column is loaded as STRING. This is intentional: CMS source data
    mixes numbers with text codes ("N/A", "Too Few To Report", footnote
    markers) in numeric-looking columns. Casting at ingest would silently
    coerce or drop that mess. Typing happens later, deliberately, in dbt
    staging models — where it's visible and testable.
    """
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}"

    # Force every column to string to avoid BigQuery's autodetect guessing
    # wrong types and silently dropping "bad" values.
    df = df.astype(str)

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        autodetect=True,
        source_format=bigquery.SourceFormat.PARQUET,
    )

    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # wait for completion

    table = client.get_table(table_id)
    print(f"    loaded {table.num_rows} rows into {table_id}")


# ---- Main --------------------------------------------------------------------

def main():
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.exists(cred_path):
        print(
            "ERROR: GOOGLE_APPLICATION_CREDENTIALS is not set or file not found.\n"
            "Run: export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/keys/gcp-key.json"
        )
        sys.exit(1)

    client = bigquery.Client(project=GCP_PROJECT_ID)

    # Ensure the raw dataset exists
    dataset_ref = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BQ_DATASET}")
    dataset_ref.location = "US"
    client.create_dataset(dataset_ref, exists_ok=True)
    print(f"Confirmed dataset {GCP_PROJECT_ID}.{BQ_DATASET} exists.\n")

    for table_name, dataset_id in DATASETS.items():
        print(f"Fetching {table_name} (CMS dataset {dataset_id})...")
        df = fetch_dataset(dataset_id)
        print(f"  Total rows fetched: {len(df)}")

        if df.empty:
            print(f"  WARNING: no rows returned for {table_name}, skipping load.\n")
            continue

        load_to_bigquery(df, table_name, client)
        print()

    print("Done. All CMS API datasets landed raw in BigQuery.")


if __name__ == "__main__":
    main()
