# Threat Classifier Baseline Comparison

This report evaluates both the unsupervised Isolation Forest baseline and the structural Graph Neural Network (GNN) on the identical `KDDTest+` test set.

| Metric | Isolation Forest | GNN (GraphSAGE) |
| --- | --- | --- |
| **Precision** | 0.8804 | 0.9270 |
| **Recall** | 0.2862 | 0.6839 |
| **F1-Score** | 0.4320 | 0.7871 |
| **Accuracy** | 0.5715 | 0.7894 |

*Note: Models were re-evaluated natively using their saved weights against `test.npz` to ensure a consistent, 1-to-1 metric computation via `sklearn.metrics`.*
