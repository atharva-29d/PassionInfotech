import os
import json
import time
import uuid
from datetime import datetime
import pandas as pd
import numpy as np
import torch
import torch.nn.functional as F
import joblib
from kafka import KafkaConsumer
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ingestion.load_nsl_kdd import COLUMN_NAMES, PROMOTED_COLUMNS
from models.gnn.model import GNNThreatClassifier
from graph.geo_reference import GEO_REFERENCE

# List all continents dynamically based on reference data
KAFKA_TOPICS = [f"network-events-{c.lower().replace(' ', '')}" for c in GEO_REFERENCE.keys()]
KAFKA_BROKER = "localhost:9092"
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

load_dotenv(os.path.join(BASE_DIR, "ingestion", ".env"))

def get_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")

def main():
    print(f"Starting consumer, connecting to {KAFKA_BROKER}...")
    
    # NOTE: For this demo-scale system, we run one consumer subscribed to all continent topics.
    # In a real production deployment, you would scale by running separate consumer instances 
    # per continent (e.g., one consumer group for 'network-events-asia', another for 'europe', etc.)
    consumer = KafkaConsumer(
        *KAFKA_TOPICS,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        auto_offset_reset='latest'
    )
    
    engine = get_engine()
    
    # 1. Load Feature Pipeline
    pipeline_path = os.path.join(BASE_DIR, "features", "artifacts", "feature_pipeline.pkl")
    feature_pipeline = joblib.load(pipeline_path)
    
    # Extract feature names needed for pipeline
    cat_cols = ["protocol_type", "service", "flag"]
    num_cols = ["src_bytes", "dst_bytes", "duration", "land", "wrong_fragment", "urgent", "hot", 
                "num_failed_logins", "logged_in", "num_compromised", "root_shell", "su_attempted", 
                "num_root", "num_file_creations", "num_shells", "num_access_files", "num_outbound_cmds", 
                "is_host_login", "is_guest_login", "count", "srv_count", "serror_rate", "srv_serror_rate", 
                "rerror_rate", "srv_rerror_rate", "same_srv_rate", "diff_srv_rate", "srv_diff_host_rate", 
                "dst_host_count", "dst_host_srv_count", "dst_host_same_srv_rate", "dst_host_diff_srv_rate", 
                "dst_host_same_src_port_rate", "dst_host_srv_diff_host_rate", "dst_host_serror_rate", 
                "dst_host_srv_serror_rate", "dst_host_rerror_rate", "dst_host_srv_rerror_rate"]
    
    # 2. Load Models
    if_model_path = os.path.join(BASE_DIR, "models", "anomaly_detector", "artifacts", "isolation_forest.pkl")
    if_model = joblib.load(if_model_path)
    
    device = torch.device('cpu')
    gnn_model = GNNThreatClassifier(hidden_channels=64, out_channels=2).to(device)
    
    # Dummy forward pass to initialize lazy layers
    dummy_x = {
        'event': torch.zeros((1, 59)).to(device), 
        'host': torch.zeros((1, 3)).to(device)
    }
    dummy_edge = {
        ('host', 'communicates_with', 'host'): torch.empty((2, 0), dtype=torch.long).to(device),
        ('host', 'rev_communicates_with', 'host'): torch.empty((2, 0), dtype=torch.long).to(device),
        ('event', 'generated_by', 'host'): torch.tensor([[0], [0]], dtype=torch.long).to(device),
        ('host', 'rev_generated_by', 'event'): torch.tensor([[0], [0]], dtype=torch.long).to(device)
    }
    gnn_model(dummy_x, dummy_edge)
    gnn_model = gnn_model.to(device) # Move lazy-initialized weights to device
    
    gnn_weights_path = os.path.join(BASE_DIR, "models", "gnn", "artifacts", "gnn_model.pt")
    gnn_model.load_state_dict(torch.load(gnn_weights_path, weights_only=False, map_location=device))
    gnn_model.eval()

    with engine.connect() as conn:
        res = conn.execute(text("SELECT model_id FROM ai_model_master LIMIT 1")).fetchone()
        actual_model_id = str(res[0]) if res else str(uuid.uuid4())
        if not res:
            conn.execute(text("INSERT INTO ai_model_master (model_id, model_name, model_type, algorithm, version, training_date) VALUES (:id, 'live', 'live', 'live', 'live', now())"), {"id": actual_model_id})
            conn.commit()
            
    print("Listening for events...")
    events_processed = 0
    start_time = time.time()
    
    for message in consumer:
        event = message.value
        
        # Insert into network_event
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO network_event
                    (event_id, protocol_type, service, flag, src_bytes, dst_bytes,
                     duration, label, is_attack, difficulty, raw_features, source_row_id, split)
                VALUES
                    (:event_id, :protocol_type, :service, :flag, :src_bytes, :dst_bytes,
                     :duration, :label, :is_attack, :difficulty, :raw_features, :source_row_id, :split)
                """),
                {
                    "event_id": event["event_id"],
                    "protocol_type": event["protocol_type"],
                    "service": event["service"],
                    "flag": event["flag"],
                    "src_bytes": event["src_bytes"],
                    "dst_bytes": event["dst_bytes"],
                    "duration": event["duration"],
                    "label": event["label"],
                    "is_attack": event["is_attack"],
                    "difficulty": event["difficulty"],
                    "raw_features": json.dumps(event["raw_features"]),
                    "source_row_id": event["source_row_id"],
                    "split": "live"
                }
            )
            
        # Reconstruct full row for pipeline
        row_dict = {**event, **event["raw_features"]}
        df = pd.DataFrame([row_dict])
        
        # Transform features
        X = feature_pipeline.transform(df[cat_cols + num_cols])
        
        # IsolationForest Inference
        if_pred_raw = if_model.predict(X)[0]
        if_pred_label = "anomaly" if if_pred_raw == -1 else "normal"
        if_score = float(if_model.decision_function(X)[0])
        
        # GNN Inference
        X_tensor = torch.tensor(X, dtype=torch.float32).to(device)
        x_dict = {
            'event': X_tensor,
            'host': torch.zeros((1, 3), dtype=torch.float32).to(device)
        }
        edge_index_dict = {
            ('host', 'communicates_with', 'host'): torch.empty((2, 0), dtype=torch.long).to(device),
            ('host', 'rev_communicates_with', 'host'): torch.empty((2, 0), dtype=torch.long).to(device),
            ('event', 'generated_by', 'host'): torch.tensor([[0], [0]], dtype=torch.long).to(device),
            ('host', 'rev_generated_by', 'event'): torch.tensor([[0], [0]], dtype=torch.long).to(device)
        }
        
        with torch.no_grad():
            out = gnn_model(x_dict, edge_index_dict)
            gnn_prob = F.softmax(out, dim=-1)[0, 1].item()
            gnn_pred_class = "anomaly" if gnn_prob > 0.5 else "normal"
            
        # Write predictions
        with engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO anomaly_detection_result
                    (detection_id, event_id, model_id, anomaly_score, prediction, detection_time)
                VALUES
                    (:detection_id, :event_id, :model_id, :anomaly_score, :prediction, :detection_time)
                """),
                {
                    "detection_id": str(uuid.uuid4()),
                    "event_id": event["event_id"],
                    "model_id": actual_model_id,
                    "anomaly_score": if_score,
                    "prediction": if_pred_label,
                    "detection_time": datetime.now()
                }
            )
            
            conn.execute(
                text("""
                INSERT INTO gnn_detection_result
                    (event_id, predicted_class, confidence, model_version)
                VALUES
                    (:event_id, :predicted_class, :confidence, :model_version)
                """),
                {
                    "event_id": event["event_id"],
                    "predicted_class": gnn_pred_class,
                    "confidence": gnn_prob,
                    "model_version": "gnn_v1.0_live"
                }
            )
            
        events_processed += 1
        elapsed = time.time() - start_time
        print(f"Processed {event['event_id']} | IF: {if_pred_label} | GNN: {gnn_pred_class} ({(events_processed/elapsed):.1f} eps)")

if __name__ == "__main__":
    main()
