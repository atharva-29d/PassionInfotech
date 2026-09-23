"""
train.py

Trains an IsolationForest model for anomaly detection using pre-processed features.
Saves the trained model and logs results to the PostgreSQL database.
"""

import os
import uuid
import joblib
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sqlalchemy import create_engine, text

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "ingestion", ".env")
DATA_DIR = os.path.join(BASE_DIR, "features", "data", "processed")
ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "artifacts")

load_dotenv(ENV_PATH)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def get_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")

def main():
    print("Loading datasets...")
    train_data = np.load(os.path.join(DATA_DIR, "train.npz"), allow_pickle=True)
    test_data = np.load(os.path.join(DATA_DIR, "test.npz"), allow_pickle=True)

    X_train = train_data["X"]
    X_test = test_data["X"]
    y_test = test_data["y"] # 1 for attack, 0 for normal
    test_event_ids = test_data["event_ids"]

    print(f"X_train shape: {X_train.shape}")
    print(f"X_test shape: {X_test.shape}")

    # Initialize and train Isolation Forest
    print("Training Isolation Forest...")
    # contamination=0.1 as a baseline unsupervised assumption
    model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42, n_jobs=-1)
    model.fit(X_train)

    print("Evaluating on test set...")
    # predict returns 1 for inliers (normal), -1 for outliers (anomaly)
    preds = model.predict(X_test)
    scores = model.decision_function(X_test)

    # Convert predictions to binary: 1 for anomaly, 0 for normal (matching y_test)
    y_pred = (preds == -1).astype(int)

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    print("\n--- Evaluation Metrics ---")
    print(f"Accuracy:  {acc:.4f}")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print("--------------------------\n")

    # Save model artifact
    model_path = os.path.join(ARTIFACTS_DIR, "isolation_forest.pkl")
    joblib.dump(model, model_path)
    print(f"Saved model artifact to {model_path}")

    # Log to Database
    print("Logging model and predictions to database...")
    engine = get_engine()
    model_id = str(uuid.uuid4())

    with engine.begin() as conn:
        # Register Model
        conn.execute(
            text("""
            INSERT INTO ai_model_master 
                (model_id, model_name, model_type, algorithm, version, training_date)
            VALUES 
                (:model_id, :model_name, :model_type, :algorithm, :version, :training_date)
            """),
            {
                "model_id": model_id,
                "model_name": "Network Anomaly Detector",
                "model_type": "Anomaly Detection",
                "algorithm": "IsolationForest",
                "version": "v1.0",
                "training_date": datetime.now()
            }
        )

        # Batch Insert Predictions
        # Map back to string predictions for DB
        pred_labels = ["anomaly" if p == -1 else "normal" for p in preds]
        
        results = [
            {
                "detection_id": str(uuid.uuid4()),
                "event_id": str(eid),
                "model_id": model_id,
                "anomaly_score": float(score),
                "prediction": label,
                "detection_time": datetime.now()
            }
            for eid, score, label in zip(test_event_ids, scores, pred_labels)
        ]

        batch_size = 5000
        for i in range(0, len(results), batch_size):
            batch = results[i:i+batch_size]
            conn.execute(
                text("""
                INSERT INTO anomaly_detection_result
                    (detection_id, event_id, model_id, anomaly_score, prediction, detection_time)
                VALUES
                    (:detection_id, :event_id, :model_id, :anomaly_score, :prediction, :detection_time)
                """),
                batch
            )
            print(f"Inserted predictions {i} to {i + len(batch)}")

    print("Completed successfully!")

if __name__ == "__main__":
    main()
