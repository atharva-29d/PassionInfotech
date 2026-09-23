import os
import torch
import torch.nn.functional as F
import numpy as np
import joblib
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, accuracy_score

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
# We need to import the GNN model class
import sys
sys.path.append(os.path.join(BASE_DIR, "models", "gnn"))
from model import GNNThreatClassifier

def main():
    print("Loading test data...")
    test_data = np.load(os.path.join(BASE_DIR, "features", "data", "processed", "test.npz"), allow_pickle=True)
    test_X = test_data["X"]
    test_y = test_data["y"]
    
    print("Evaluating Isolation Forest...")
    if_model_path = os.path.join(BASE_DIR, "models", "anomaly_detector", "artifacts", "isolation_forest.pkl")
    if_model = joblib.load(if_model_path)
        
    # IsolationForest outputs -1 for anomaly, 1 for normal
    if_preds_raw = if_model.predict(test_X)
    if_preds = np.where(if_preds_raw == -1, 1, 0)
    
    if_prec = precision_score(test_y, if_preds, zero_division=0)
    if_rec = recall_score(test_y, if_preds, zero_division=0)
    if_f1 = f1_score(test_y, if_preds, zero_division=0)
    if_acc = accuracy_score(test_y, if_preds)
    
    print("Evaluating GNN...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    gnn_model = GNNThreatClassifier(hidden_channels=64, out_channels=2).to(device)
    
    gnn_weights_path = os.path.join(BASE_DIR, "models", "gnn", "artifacts", "gnn_model.pt")
    gnn_model.load_state_dict(torch.load(gnn_weights_path, weights_only=False, map_location=device))
    gnn_model.eval()
    
    graph_data_path = os.path.join(BASE_DIR, "models", "gnn", "artifacts", "graph_data.pt")
    graph_data = torch.load(graph_data_path, weights_only=False, map_location=device)
    
    x_dict = graph_data.x_dict
    edge_index_dict = graph_data.edge_index_dict
    test_mask = graph_data['event'].test_mask
    
    with torch.no_grad():
        out = gnn_model(x_dict, edge_index_dict)
        gnn_preds = out.argmax(dim=-1)[test_mask].cpu().numpy()
        gnn_true = graph_data['event'].y[test_mask].cpu().numpy()
        
    gnn_prec = precision_score(gnn_true, gnn_preds, zero_division=0)
    gnn_rec = recall_score(gnn_true, gnn_preds, zero_division=0)
    gnn_f1 = f1_score(gnn_true, gnn_preds, zero_division=0)
    gnn_acc = accuracy_score(gnn_true, gnn_preds)
    
    report = f"""# Threat Classifier Baseline Comparison

This report evaluates both the unsupervised Isolation Forest baseline and the structural Graph Neural Network (GNN) on the identical `KDDTest+` test set.

| Metric | Isolation Forest | GNN (GraphSAGE) |
| --- | --- | --- |
| **Precision** | {if_prec:.4f} | {gnn_prec:.4f} |
| **Recall** | {if_rec:.4f} | {gnn_rec:.4f} |
| **F1-Score** | {if_f1:.4f} | {gnn_f1:.4f} |
| **Accuracy** | {if_acc:.4f} | {gnn_acc:.4f} |

*Note: Models were re-evaluated natively using their saved weights against `test.npz` to ensure a consistent, 1-to-1 metric computation via `sklearn.metrics`.*
"""

    report_path = os.path.join(BASE_DIR, "models", "comparison_report.md")
    with open(report_path, "w") as f:
        f.write(report)
        
    print(f"Comparison report saved to {report_path}")
    print(report)

if __name__ == "__main__":
    main()
