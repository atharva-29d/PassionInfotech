import sys
import os
import joblib
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score
import torch
import torch.nn.functional as F
from torch_geometric.data import Data

sys.path.append('backend')
from ingestion.load_nsl_kdd import load_dataframe, transform
from models.gnn.model import GNNThreatClassifier

def evaluate_models():
    # Load test data
    df_test_raw = load_dataframe('backend/ingestion/data/KDDTest+.txt')
    
    # Load labels
    y_test = (df_test_raw['label'] != 'normal').astype(int).values
    
    # Transform features
    pipeline = joblib.load('backend/features/artifacts/feature_pipeline.pkl')
    X_test = pipeline.transform(df_test_raw)
    
    print("--- Isolation Forest ---")
    if_model = joblib.load('backend/models/anomaly_detector/artifacts/isolation_forest.pkl')
    # IF returns 1 for normal, -1 for anomaly. We map to 0 (normal) and 1 (attack).
    y_pred_if_raw = if_model.predict(X_test)
    y_pred_if = (y_pred_if_raw == -1).astype(int)
    
    print(f"Accuracy: {accuracy_score(y_test, y_pred_if):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred_if):.4f}")
    print(f"Recall: {recall_score(y_test, y_pred_if):.4f}")
    print(f"F1: {f1_score(y_test, y_pred_if):.4f}")
    
    print("\n--- GNN ---")
    device = torch.device('cpu')
    model = GNNThreatClassifier(input_dim=59, hidden_dim=64, output_dim=2).to(device)
    model.load_state_dict(torch.load('backend/models/gnn/gnn_model.pth', map_location=device))
    model.eval()
    
    # For inference on flat rows without edges (inductive), we pass empty edge_index
    # just as we do in the consumer.
    x_tensor = torch.tensor(X_test, dtype=torch.float32)
    edge_index = torch.empty((2, 0), dtype=torch.long)
    
    with torch.no_grad():
        out = model(x_tensor, edge_index)
        y_pred_gnn = out.argmax(dim=1).numpy()
        
    print(f"Accuracy: {accuracy_score(y_test, y_pred_gnn):.4f}")
    print(f"Precision: {precision_score(y_test, y_pred_gnn):.4f}")
    print(f"Recall: {recall_score(y_test, y_pred_gnn):.4f}")
    print(f"F1: {f1_score(y_test, y_pred_gnn):.4f}")

if __name__ == '__main__':
    evaluate_models()
