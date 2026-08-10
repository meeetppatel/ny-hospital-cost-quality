"""
Load 8 NY hospital price transparency machine-readable files (already
downloaded locally to price_transparency_raw/) into BigQuery, ONE TABLE PER
HOSPITAL, raw and untouched.

Why one table per hospital, not one unified table: these files use genuinely
different schemas per hospital (tall vs wide CSV layout, JSON vs CSV, some
with a leading blank preamble row before the real header). Forcing them into
one schema at load time would mean silently cleaning/reshaping data before
it's even visible — exactly what this project's raw-landing-zone philosophy
avoids. Unification happens deliberately and visibly later, in dbt staging
models, where the transformation is testable and documented.

Known per-file quirks this script has to handle (found by manually peeking
at each file before writing this script):
  - Rochester General, Brooklyn Hospital Center, Albany Medical Center:
    real CSV header is on row 3, not row 1 (rows 1-2 are hospital metadata
    preamble: hospital_name/last_updated_on/... then an attestation blob).
  - Montefiore: same 3-row preamble structure, plus a raw UTF-8 encoding
    bug in the hospital name field (mangled em-dash). We load as latin-1
    fallback if utf-8 strict decoding fails, rather than silently fixing it.
  - NewYork-Presbyterian, Mount Sinai: JSON, deeply nested
    (standard_charge_information array of objects per hospital). We land
    the raw JSON as a single-column BigQuery table (one row = whole file)
    rather than guessing a flattening — flattening is dbt's job.
  - Flushing Hospital, NewYork-Presbyterian: delivered as .zip, must
    extract first.
  - NYU Langone, Albany: very wide (hundreds of payer-specific columns).
    Loaded as-is per project decision — no pre-melting to long format.

Usage:
    python load_price_transparency.py

Requires:
    GOOGLE_APPLICATION_CREDENTIALS and GCP_PROJECT_ID env vars set.
    Run from the repo root; expects ./price_transparency_raw/ to exist
    with the 8 downloaded files.
"""

import io
import os
import re
import sys
import json
import zipfile
import pandas as pd
from google.cloud import bigquery

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BQ_DATASET = "raw"
LOCAL_DIR = "price_transparency_raw"

# Each entry: table_name -> (filename, file_type, header_row_index or None)
# header_row_index: 0 = header on first line (standard), 2 = header on 3rd
# line (0-indexed) because rows 0-1 are hospital metadata preamble.
FILES = {
    "price_tx_newyork_presbyterian": {
        "filename": "330101_newyork-presbyterian_standardcharges.json.zip",
        "type": "json_zip",
    },
    "price_tx_mount_sinai": {
        "filename": "330024_mount-sinai-hospital_standardcharges.json",
        "type": "json",
    },
    "price_tx_nyu_langone": {
        "filename": "330214_nyu-langone-tisch_standardcharges.csv",
        "type": "csv",
        "header_row": 2,
    },
    "price_tx_montefiore": {
        "filename": "330059_montefiore-medical-center_standardcharges.csv",
        "type": "csv",
        "header_row": 2,
    },
    "price_tx_brooklyn_hospital": {
        "filename": "330056_brooklyn-hospital-center_standardcharges.csv",
        "type": "csv",
        "header_row": 2,
    },
    "price_tx_flushing_hospital": {
        "filename": "330193_flushing-hospital_standardcharges.zip",
        "type": "csv_zip",
        "header_row": 2,
    },
    "price_tx_rochester_general": {
        "filename": "330125_rochester-general_standardcharges.csv",
        "type": "csv",
        "header_row": 2,
    },
    "price_tx_albany_medical": {
        "filename": "330013_albany-medical-center_standardcharges.csv",
        "type": "csv",
        "header_row": 2,
    },
}


def load_csv_file(path, header_row):
    """Read a CSV that may have a metadata preamble before the real header.
    Try utf-8 first; some files (Montefiore) have encoding issues -- fall
    back to latin-1 rather than crash, and note it plainly. We do NOT fix
    the mangled characters -- that's a data quality finding, not our job
    to silently correct at ingest.
    """
    try:
        df = pd.read_csv(path, header=header_row, dtype=str, low_memory=False,
                          encoding="utf-8")
    except UnicodeDecodeError:
        print(f"    WARNING: utf-8 decode failed for {path}, falling back to latin-1. "
              f"This encoding issue should be logged in data_quality_findings.md.")
        df = pd.read_csv(path, header=header_row, dtype=str, low_memory=False,
                          encoding="latin-1")
    return df


def load_csv_from_zip(zip_path, header_row):
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if len(names) != 1:
            print(f"    WARNING: expected 1 file in {zip_path}, found {len(names)}: {names}")
        inner_name = names[0]
        with z.open(inner_name) as f:
            raw_bytes = f.read()
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes), header=header_row, dtype=str,
                          low_memory=False, encoding="utf-8")
    except UnicodeDecodeError:
        print(f"    WARNING: utf-8 decode failed for {zip_path}, falling back to latin-1.")
        df = pd.read_csv(io.BytesIO(raw_bytes), header=header_row, dtype=str,
                          low_memory=False, encoding="latin-1")
    return df


def load_json_file(path):
    """Land raw JSON as a single-row table: one column holding the entire
    JSON blob as a string, plus a loaded_at-style marker. Flattening the
    nested standard_charge_information array happens in dbt, deliberately.

    Some files (Mount Sinai) are saved with a UTF-8 byte-order-mark (BOM)
    prefix. Note this is itself a minor data quality finding, worth a
    one-line mention in the findings doc -- worth calling out: plain
    'utf-8' decoding does NOT raise an error on a BOM (it silently decodes
    it as a real character, U+FEFF), so a try/except UnicodeDecodeError
    approach never catches this -- the failure only surfaces later, at
    json.loads(), which is a good example of an error showing up far from
    its actual cause. We use utf-8-sig unconditionally instead: it strips
    a leading BOM if present and is otherwise identical to utf-8.
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        raw_text = f.read()
    if raw_text.startswith("﻿"):
        # Shouldn't happen with utf-8-sig, but guard anyway and log it.
        print(f"    NOTE: {path} still had a BOM after utf-8-sig decode, stripping manually.")
        raw_text = raw_text.lstrip("﻿")
    # Sanity check it's valid JSON before landing it (fail loud, not silent)
    json.loads(raw_text)
    return pd.DataFrame({"raw_json": [raw_text]})


def load_json_from_zip(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        if len(names) != 1:
            print(f"    WARNING: expected 1 file in {zip_path}, found {len(names)}: {names}")
        inner_name = names[0]
        with z.open(inner_name) as f:
            raw_text = f.read().decode("utf-8")
    json.loads(raw_text)
    return pd.DataFrame({"raw_json": [raw_text]})


def sanitize_column_names(df, table_name):
    """BigQuery column names may only contain letters, numbers, and
    underscores, and must be <=300 chars. Several hospital price
    transparency CSVs use pipe-delimited headers like
    'standard_charge|Cigna|CIGNA MANAGED CARE/POS 1046|negotiated_dollar'
    to encode payer/plan info in the column name itself -- this is a real
    data quality finding (raw source violates destination naming rules),
    not something to silently paper over. We sanitize here because BigQuery
    leaves us no choice, but we log every renamed column so the mapping is
    visible and auditable rather than silently lossy.
    """
    rename_map = {}
    seen = set()
    for col in df.columns:
        new_col = re.sub(r"[^0-9a-zA-Z_]", "_", col)
        new_col = re.sub(r"_+", "_", new_col).strip("_")
        if not new_col:
            new_col = "unnamed_column"
        if new_col[0].isdigit():
            new_col = f"col_{new_col}"
        new_col = new_col[:300]
        # de-duplicate collisions (e.g. two different raw names sanitizing to the same thing)
        base = new_col
        i = 1
        while new_col in seen:
            suffix = f"_{i}"
            new_col = f"{base[:300 - len(suffix)]}{suffix}"
            i += 1
        seen.add(new_col)
        if new_col != col:
            rename_map[col] = new_col

    if rename_map:
        print(f"    NOTE: sanitized {len(rename_map)} column names for BigQuery "
              f"compatibility (raw headers used characters like '|' or '/'). "
              f"This is a real data quality finding -- log it in "
              f"data_quality_findings.md. Example: "
              f"{next(iter(rename_map.items()))}")
    df = df.rename(columns=rename_map)
    return df


def load_to_bigquery(df, table_name, client):
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.{table_name}"
    df = sanitize_column_names(df, table_name)
    df = df.astype(str)  # keep everything as text at raw stage, same as other sources

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        autodetect=True,
        source_format=bigquery.SourceFormat.PARQUET,
    )
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()

    table = client.get_table(table_id)
    print(f"    loaded {table.num_rows} rows, {len(table.schema)} columns into {table_id}")


def main():
    if not GCP_PROJECT_ID:
        print("ERROR: GCP_PROJECT_ID env var not set.")
        sys.exit(1)
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path or not os.path.exists(cred_path):
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set or file not found.")
        sys.exit(1)
    if not os.path.isdir(LOCAL_DIR):
        print(f"ERROR: {LOCAL_DIR}/ not found. Run this from the repo root, "
              f"after downloading the 8 price transparency files.")
        sys.exit(1)

    client = bigquery.Client(project=GCP_PROJECT_ID)
    dataset_ref = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BQ_DATASET}")
    dataset_ref.location = "US"
    client.create_dataset(dataset_ref, exists_ok=True)

    for table_name, cfg in FILES.items():
        path = os.path.join(LOCAL_DIR, cfg["filename"])
        print(f"Processing {table_name} <- {cfg['filename']}")

        if not os.path.exists(path):
            print(f"    ERROR: file not found at {path}, skipping.\n")
            continue

        try:
            if cfg["type"] == "csv":
                df = load_csv_file(path, cfg["header_row"])
            elif cfg["type"] == "csv_zip":
                df = load_csv_from_zip(path, cfg["header_row"])
            elif cfg["type"] == "json":
                df = load_json_file(path)
            elif cfg["type"] == "json_zip":
                df = load_json_from_zip(path)
            else:
                print(f"    ERROR: unknown type {cfg['type']}, skipping.\n")
                continue
        except Exception as e:
            print(f"    ERROR processing {path}: {e}\n")
            continue

        print(f"    parsed {len(df)} rows, {len(df.columns)} columns")
        load_to_bigquery(df, table_name, client)
        print()

    print("Done. All price transparency files landed raw in BigQuery (one table per hospital).")


if __name__ == "__main__":
    main()
