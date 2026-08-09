"""
Ingest CMS Medicare Inpatient Hospitals — by Provider and Service (utilization
& payment data) into BigQuery, RAW and UNTOUCHED.

This is the COST side of the cost/quality analysis. The join key is the CCN
(CMS Certification Number) — here called Rndrng_Prvdr_CCN. The quality
datasets ingested separately use a differently-named field (facility_id) for
the same concept. That naming mismatch is intentional to leave alone here —
it's exactly the kind of cross-source inconsistency this project's data
quality findings doc is meant to catch and document, not silently fix.

CMS doesn't publish a stable, unchanging download URL for this CSV — the file
lives under a UUID path that rotates with each release. So this script first
resolves the CURRENT download URL from CMS's own dataset metadata (data.json),
then downloads and loads whatever that points to. Don't hardcode the CSV URL.

Usage:
    python ingest_medicare_inpatient.py

Requires:
    GOOGLE_APPLICATION_CREDENTIALS and GCP_PROJECT_ID env vars set
    (same as ingest_cms_api.py).
"""

import io
import os
import sys
import requests
import pandas as pd
from google.cloud import bigquery

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET = "raw"
TABLE_NAME = "medicare_inpatient_utilization"

# Verified dataset UUID for "Medicare Inpatient Hospitals - by Provider and Service"
DATASET_UUID = "690ddc6c-2767-4618-b277-420ffb2bf27c"

# CMS's own catalog metadata API — this tells us the CURRENT csv download URL
# rather than us hardcoding a path that will go stale next release.
METADATA_URL = f"https://data.cms.gov/data-api/v1/dataset/{DATASET_UUID}"
CATALOG_URL = "https://data.cms.gov/data.json"


def resolve_current_csv_url() -> str:
    """Find the current bulk CSV download URL for this dataset from CMS's
    own DCAT catalog, since the file path/UUID changes every release."""
    print("Resolving current CSV download URL from CMS catalog...")
    resp = requests.get(CATALOG_URL, timeout=60)
    resp.raise_for_status()
    catalog = resp.json()

    for entry in catalog.get("dataset", []):
        # match on the known dataset identifier appearing in landing page / identifier
        identifier = entry.get("identifier", "")
        if DATASET_UUID in identifier:
            for dist in entry.get("distribution", []):
                url = dist.get("downloadURL", "")
                if url.lower().endswith(".csv"):
                    print(f"  Found: {url}")
                    return url

    raise RuntimeError(
        "Could not resolve current CSV URL from CMS catalog. "
        "The dataset UUID may have changed — check "
        "https://data.cms.gov/provider-summary-by-type-of-service/"
        "medicare-inpatient-hospitals/medicare-inpatient-hospitals-by-provider-and-service "
        "manually and hardcode the URL as a fallback."
    )


def download_csv(url: str) -> pd.DataFrame:
    print(f"Downloading CSV (this file is large, may take a minute)...")
    resp = requests.get(url, timeout=300, stream=True)
    resp.raise_for_status()

    # Read directly into pandas from the response bytes.
    # dtype=str: same reasoning as the API ingest script — keep everything as
    # text at raw load time, don't let pandas/BigQuery silently coerce types.
    df = pd.read_csv(io.BytesIO(resp.content), dtype=str, low_memory=False)
    print(f"  Downloaded {len(df)} rows, {len(df.columns)} columns.")
    return df


def load_to_bigquery(df: pd.DataFrame, client: bigquery.Client):
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{TABLE_NAME}"

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        autodetect=True,
        source_format=bigquery.SourceFormat.PARQUET,
    )

    print(f"Loading into {table_id}...")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()

    table = client.get_table(table_id)
    print(f"  Loaded {table.num_rows} rows into {table_id}")


def main():
    if not GCP_PROJECT_ID:
        print("ERROR: GCP_PROJECT_ID env var not set.")
        sys.exit(1)

    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.exists(cred_path):
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set or file not found.")
        sys.exit(1)

    client = bigquery.Client(project=GCP_PROJECT_ID)
    dataset_ref = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BQ_DATASET}")
    dataset_ref.location = "US"
    client.create_dataset(dataset_ref, exists_ok=True)

    csv_url = resolve_current_csv_url()
    df = download_csv(csv_url)
    load_to_bigquery(df, client)

    print("\nDone. Medicare inpatient utilization data landed raw in BigQuery.")


if __name__ == "__main__":
    main()
