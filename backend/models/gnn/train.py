import os
import torch
import torch.nn.functional as F
from sqlalchemy import create_engine, text
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
import pandas as pd
from dotenv import load_dotenv
from model import GNNThreatClassifier
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "graph", ".env")
load_dotenv(ENV_PATH)

def get_pg_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")

    artifacts_dir = os.path.join(os.path.dirname(__file__), "artifacts")
    data_path = os.path.join(artifacts_dir, "graph_data.pt")
    eids_path = os.path.join(artifacts_dir, "test_eids.pt")

    print("Loading graph data...")
    data = torch.load(data_path, weights_only=False).to(device)
    test_eids = torch.load(eids_path, weights_only=False)
    
    model = GNNThreatClassifier(hidden_channels=64, out_channels=2).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    # Move graph structure to device once
    x_dict = data.x_dict
    edge_index_dict = data.edge_index_dict
    
    train_mask = data['event'].train_mask
    test_mask = data['event'].test_mask
    y = data['event'].y

    print("Starting training...")
    model.train()
    epochs = 100
    
    start_loss = None
    end_loss = None

    for epoch in range(1, epochs + 1):
        optimizer.zero_grad()
        out = model(x_dict, edge_index_dict)
        loss = F.cross_entropy(out[train_mask], y[train_mask])
        loss.backward()
        optimizer.step()
        
        if epoch == 1:
            start_loss = loss.item()
        if epoch == epochs:
            end_loss = loss.item()
            
        if epoch % 10 == 0:
            print(f"Epoch {epoch:03d}, Loss: {loss.item():.4f}")

    print(f"Training complete. Loss curve summary: Start={start_loss:.4f} -> End={end_loss:.4f}")
    torch.save(model.state_dict(), os.path.join(artifacts_dir, "gnn_model.pt"))

    # Evaluation
    model.eval()
    with torch.no_grad():
        out = model(x_dict, edge_index_dict)
        pred = out.argmax(dim=-1)
        probs = F.softmax(out, dim=-1)
        
        test_pred = pred[test_mask].cpu().numpy()
        test_probs = probs[test_mask, 1].cpu().numpy() # Probability of class 1 (attack)
        test_true = y[test_mask].cpu().numpy()

    prec = precision_score(test_true, test_pred, zero_division=0)
    rec = recall_score(test_true, test_pred, zero_division=0)
    f1 = f1_score(test_true, test_pred, zero_division=0)

    print("\n--- GNN Evaluation ---")
    print(f"Precision: {prec:.4f}")
    print(f"Recall:    {rec:.4f}")
    print(f"F1-Score:  {f1:.4f}")
    print("Confusion Matrix:\n", confusion_matrix(test_true, test_pred))

    # Log to Postgres
    print("\nLogging predictions to PostgreSQL...")
    engine = get_pg_engine()
    
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gnn_detection_result (
                detection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                event_id UUID NOT NULL,
                predicted_class VARCHAR(50) NOT NULL,
                confidence FLOAT NOT NULL,
                model_version VARCHAR(50) NOT NULL,
                detection_time TIMESTAMP NOT NULL DEFAULT now()
            )
        """))
        
        # We need to map test_pred to string classes and batch insert
        pred_labels = ["anomaly" if p == 1 else "normal" for p in test_pred]
        
        results = [
            {
                "event_id": str(eid),
                "predicted_class": label,
                "confidence": float(conf),
                "model_version": "gnn_v1.0"
            }
            for eid, label, conf in zip(test_eids, pred_labels, test_probs)
        ]
        
        for i in range(0, len(results), 5000):
            batch = results[i:i+5000]
            conn.execute(
                text("""
                INSERT INTO gnn_detection_result
                    (event_id, predicted_class, confidence, model_version)
                VALUES
                    (:event_id, :predicted_class, :confidence, :model_version)
                """),
                batch
            )
        print("Predictions logged.")

    # Fetch baseline for comparison
    print("\nFetching IsolationForest baseline results from DB for comparison...")
    baseline_query = """
        SELECT 
            e.is_attack, 
            CASE WHEN a.prediction = 'anomaly' THEN 1 ELSE 0 END as pred
        FROM anomaly_detection_result a
        JOIN network_event e ON a.event_id = e.event_id
    """
    baseline_df = pd.read_sql(baseline_query, engine)
    b_prec = precision_score(baseline_df['is_attack'], baseline_df['pred'], zero_division=0)
    b_rec = recall_score(baseline_df['is_attack'], baseline_df['pred'], zero_division=0)
    b_f1 = f1_score(baseline_df['is_attack'], baseline_df['pred'], zero_division=0)

    print("\n=======================================================")
    print("        BASELINE (IsolationForest) vs GNN (GraphSAGE)  ")
    print("=======================================================")
    print(f"Metric      | IsolationForest | GNN             ")
    print(f"------------|-----------------|-----------------")
    print(f"Precision   | {b_prec:.4f}          | {prec:.4f}         ")
    print(f"Recall      | {b_rec:.4f}          | {rec:.4f}         ")
    print(f"F1-Score    | {b_f1:.4f}          | {f1:.4f}         ")
    print("=======================================================\n")

if __name__ == "__main__":
    main()
