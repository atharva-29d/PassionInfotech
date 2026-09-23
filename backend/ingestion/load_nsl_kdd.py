"""
load_nsl_kdd.py

Batch-loads the NSL-KDD dataset (KDDTrain+.txt / KDDTest+.txt) into the
`network_event` table in Postgres.

Usage:
    python load_nsl_kdd.py --file data/KDDTrain+.txt

Expects Postgres connection details via environment variables:
    DB_HOST (default: localhost)
    DB_PORT (default: 5432)
    DB_NAME (default: threat_hunting)
    DB_USER (default: postgres)
    DB_PASSWORD

Download the dataset from the official NSL-KDD source and place the file
under backend/ingestion/data/ (gitignored — do not commit raw data files).
"""

import argparse
import logging
import os
import uuid

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Official NSL-KDD column order (41 features + label + difficulty).
# The dataset files have no header row, so we define it ourselves.
COLUMN_NAMES = [
    "duration", "protocol_type", "service", "flag", "src_bytes", "dst_bytes",
    "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in",
    "num_compromised", "root_shell", "su_attempted", "num_root",
    "num_file_creations", "num_shells", "num_access_files", "num_outbound_cmds",
    "is_host_login", "is_guest_login", "count", "srv_count", "serror_rate",
    "srv_serror_rate", "rerror_rate", "srv_rerror_rate", "same_srv_rate",
    "diff_srv_rate", "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
    "dst_host_same_srv_rate", "dst_host_diff_srv_rate",
    "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate",
    "dst_host_serror_rate", "dst_host_srv_serror_rate", "dst_host_rerror_rate",
    "dst_host_srv_rerror_rate", "label", "difficulty",
]

# Columns promoted to real table columns; everything else goes into raw_features JSONB
PROMOTED_COLUMNS = ["protocol_type", "service", "flag", "src_bytes", "dst_bytes", "duration"]


def get_engine():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return create_engine(url)


def load_dataframe(filepath: str) -> pd.DataFrame:
    logger.info(f"Reading {filepath}")
    df = pd.read_csv(filepath, names=COLUMN_NAMES, header=None)
    logger.info(f"Loaded {len(df)} rows")
    return df


def transform(df: pd.DataFrame, split_name: str = "train") -> pd.DataFrame:
    df = df.copy()
    df["event_id"] = [str(uuid.uuid4()) for _ in range(len(df))]
    df["is_attack"] = df["label"] != "normal"
    df["source_row_id"] = df.index
    df["split"] = split_name

    feature_cols = [c for c in COLUMN_NAMES if c not in PROMOTED_COLUMNS + ["label", "difficulty"]]
    df["raw_features"] = df[feature_cols].apply(lambda row: row.to_dict(), axis=1)

    keep_cols = ["event_id"] + PROMOTED_COLUMNS + ["label", "is_attack", "difficulty", "raw_features", "source_row_id", "split"]
    return df[keep_cols]


def load_to_db(df: pd.DataFrame, engine, batch_size: int = 5000):
    import json

    insert_sql = text("""
        INSERT INTO network_event
            (event_id, protocol_type, service, flag, src_bytes, dst_bytes,
             duration, label, is_attack, difficulty, raw_features, source_row_id, split)
        VALUES
            (:event_id, :protocol_type, :service, :flag, :src_bytes, :dst_bytes,
             :duration, :label, :is_attack, :difficulty, :raw_features, :source_row_id, :split)
    """)

    records = df.to_dict(orient="records")
    for r in records:
        r["raw_features"] = json.dumps(r["raw_features"])

    with engine.begin() as conn:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            conn.execute(insert_sql, batch)
            logger.info(f"Inserted rows {i} to {i + len(batch)}")

    logger.info(f"Done. Inserted {len(records)} total rows.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, help="Path to KDDTrain+.txt or KDDTest+.txt")
    parser.add_argument("--split", default="train", choices=["train", "test"], help="Dataset split ('train' or 'test')")
    args = parser.parse_args()

    engine = get_engine()
    df = load_dataframe(args.file)
    df = transform(df, split_name=args.split)
    load_to_db(df, engine)


if __name__ == "__main__":
    main()
