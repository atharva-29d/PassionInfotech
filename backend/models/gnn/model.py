import torch
import torch.nn.functional as F
from torch_geometric.nn import HeteroConv, SAGEConv, Linear

class GNNThreatClassifier(torch.nn.Module):
    def __init__(self, hidden_channels=64, out_channels=2):
        super().__init__()
        
        # We define a multi-layer HeteroConv architecture
        # Layer 1
        self.conv1 = HeteroConv({
            ('host', 'communicates_with', 'host'): SAGEConv(-1, hidden_channels),
            ('host', 'rev_communicates_with', 'host'): SAGEConv(-1, hidden_channels),
            ('event', 'generated_by', 'host'): SAGEConv((-1, -1), hidden_channels),
            ('host', 'rev_generated_by', 'event'): SAGEConv((-1, -1), hidden_channels),
        }, aggr='mean')
        
        # Layer 2
        self.conv2 = HeteroConv({
            ('host', 'communicates_with', 'host'): SAGEConv(-1, hidden_channels),
            ('host', 'rev_communicates_with', 'host'): SAGEConv(-1, hidden_channels),
            ('event', 'generated_by', 'host'): SAGEConv((-1, -1), hidden_channels),
            ('host', 'rev_generated_by', 'event'): SAGEConv((-1, -1), hidden_channels),
        }, aggr='mean')

        # Final classification head for events
        self.lin = Linear(hidden_channels, out_channels)

    def forward(self, x_dict, edge_index_dict):
        # Layer 1
        x_dict = self.conv1(x_dict, edge_index_dict)
        x_dict = {key: F.relu(x) for key, x in x_dict.items()}
        
        # Layer 2
        x_dict = self.conv2(x_dict, edge_index_dict)
        x_dict = {key: F.relu(x) for key, x in x_dict.items()}
        
        # We only care about predicting the 'event' node classes
        out = self.lin(x_dict['event'])
        return out
