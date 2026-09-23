"""
build_features.py

Pulls raw events from Postgres, restores the full 41-feature NSL-KDD schema
(flattening raw_features JSONB back into columns), encodes categoricals,
scales numerics, and saves a train-fitted, test-transformed feature matrix.

Usage:
    # Step 1 — fit on training data
    python build_features.py --split train --fit --output-prefix train

    # Step 2 — transform test data using the SAME fitted encoder/scaler
    python build_features.py --split test --output-prefix test
"""

import argparse
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import create_engine, text

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "ingestion", ".env"))

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "data", "processed")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

CATEGORICAL_COLS = ["protocol_type", "service", "flag"]
PROMOTED_NUMERIC_COLS = ["src_bytes", "dst_bytes", "duration"]


def get_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")


def load_and_flatten(engine, split: str) -> pd.DataFrame:
    query = text("""
        SELECT event_id, protocol_type, service, flag, src_bytes, dst_bytes,
               duration, label, is_attack, raw_features
        FROM network_event
        WHERE split = :split
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"split": split})

    if df.empty:
        raise ValueError(f"No records found in network_event for split='{split}'")

    raw = df["raw_features"].apply(lambda v: v if isinstance(v, dict) else json.loads(v))
    expanded = pd.json_normalize(raw)

    flat = pd.concat(
        [df.drop(columns=["raw_features"]).reset_index(drop=True), expanded.reset_index(drop=True)],
        axis=1,
    )
    return flat


def build_pipeline() -> tuple[ColumnTransformer, list[str]]:
    numeric_cols = PROMOTED_NUMERIC_COLS + [
        "land", "wrong_fragment", "urgent", "hot", "num_failed_logins", "logged_in",
        "num_compromised", "root_shell", "su_attempted", "num_root", "num_file_creations",
        "num_shells", "num_access_files", "num_outbound_cmds", "is_host_login",
        "is_guest_login", "count", "srv_count", "serror_rate", "srv_serror_rate",
        "rerror_rate", "srv_rerror_rate", "same_srv_rate", "diff_srv_rate",
        "srv_diff_host_rate", "dst_host_count", "dst_host_srv_count",
        "dst_host_same_srv_rate", "dst_host_diff_srv_rate", "dst_host_same_src_port_rate",
        "dst_host_srv_diff_host_rate", "dst_host_serror_rate", "dst_host_srv_serror_rate",
        "dst_host_rerror_rate", "dst_host_srv_rerror_rate",
    ]

    pipeline = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=0.01), CATEGORICAL_COLS),
            ("num", StandardScaler(), numeric_cols),
        ]
    )
    return pipeline, numeric_cols


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["train", "test"], help="Dataset split to pull ('train' or 'test')")
    parser.add_argument("--fit", action="store_true", help="Fit a new encoder/scaler (use only for training split)")
    parser.add_argument("--output-prefix", required=True, help="e.g. 'train' or 'test' — controls output filenames")
    args = parser.parse_args()

    split = args.split if args.split else (args.output_prefix if args.output_prefix in ["train", "test"] else "train")

    if args.fit and split == "test":
        print("[WARNING] Passing --fit with --split test causes data leakage! You should only fit on train.", file=sys.stderr)

    engine = get_engine()
    df = load_and_flatten(engine, split=split)
    print(f"Loaded {len(df)} rows for split='{split}', {df.shape[1]} raw columns")

    pipeline, numeric_cols = build_pipeline()
    pipeline_path = os.path.join(ARTIFACTS_DIR, "feature_pipeline.pkl")

    if args.fit:
        X = pipeline.fit_transform(df[CATEGORICAL_COLS + numeric_cols])
        joblib.dump(pipeline, pipeline_path)
        print(f"Fitted new pipeline, saved to {pipeline_path}")

        cat_feature_names = pipeline.named_transformers_["cat"].get_feature_names_out(CATEGORICAL_COLS).tolist()
        all_feature_names = cat_feature_names + numeric_cols
        manifest = {
            "categorical_expanded_columns": cat_feature_names,
            "numeric_columns": numeric_cols,
            "all_feature_names": all_feature_names,
            "total_features": len(all_feature_names),
        }
        with open(os.path.join(os.path.dirname(__file__), "feature_manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"Wrote feature_manifest.json — {manifest['total_features']} total features")
    else:
        if not os.path.exists(pipeline_path):
            raise FileNotFoundError(
                f"No fitted pipeline found at {pipeline_path}. Run once with --fit on training data first."
            )
        pipeline = joblib.load(pipeline_path)
        X = pipeline.transform(df[CATEGORICAL_COLS + numeric_cols])
        print("Transformed using existing fitted pipeline (no refit)")

    y = df["is_attack"].astype(int).to_numpy()
    event_ids = df["event_id"].to_numpy()

    out_path = os.path.join(PROCESSED_DIR, f"{args.output_prefix}.npz")
    np.savez_compressed(out_path, X=X, y=y, event_ids=event_ids)
    print(f"Saved {X.shape[0]} rows x {X.shape[1]} features to {out_path}")

    n_nan = np.isnan(X.astype(float)).sum() if not hasattr(X, "toarray") else np.isnan(X.toarray()).sum()
    attack_ratio = y.mean()
    print(f"NaN count: {n_nan}")
    print(f"Attack ratio: {attack_ratio:.1%}")


if __name__ == "__main__":
    main()
