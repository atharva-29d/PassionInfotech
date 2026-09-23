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
    gnn_model = GNNThreatClassifier(hidden_channels=64, out_channels=2).to(device)
    
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
    
    gnn_weights_path = 'backend/models/gnn/artifacts/gnn_model.pt'
    # Actually it's gnn_model.pt, let me verify the extension
    if not os.path.exists(gnn_weights_path):
        gnn_weights_path = 'backend/models/gnn/artifacts/gnn_model.pth' # Just in case

    gnn_model.load_state_dict(torch.load(gnn_weights_path, map_location=device, weights_only=False))
    gnn_model.eval()

    # Load graph data
    data_path = 'backend/models/gnn/artifacts/graph_data.pt'
    data = torch.load(data_path, map_location=device, weights_only=False)
    
    with torch.no_grad():
        out = gnn_model(data.x_dict, data.edge_index_dict)
        test_mask = data['event'].test_mask
        
        y_test_gnn = data['event'].y[test_mask].numpy()
        y_pred_gnn = out[test_mask].argmax(dim=1).numpy()
        
    print(f"Accuracy: {accuracy_score(y_test_gnn, y_pred_gnn):.4f}")
    print(f"Precision: {precision_score(y_test_gnn, y_pred_gnn):.4f}")
    print(f"Recall: {recall_score(y_test_gnn, y_pred_gnn):.4f}")
    print(f"F1: {f1_score(y_test_gnn, y_pred_gnn):.4f}")

if __name__ == '__main__':
    evaluate_models()
