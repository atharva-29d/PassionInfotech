import os
import torch
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from dotenv import load_dotenv
from torch_geometric.data import HeteroData
import torch_geometric.transforms as T

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "graph", ".env")
load_dotenv(ENV_PATH)

import sys
sys.path.append(os.path.join(BASE_DIR, "graph"))
from build_graph import generate_synthetic_hosts

def get_pg_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")

def main():
    print("Loading npz files...")
    train_data = np.load(os.path.join(BASE_DIR, "features", "data", "processed", "train.npz"), allow_pickle=True)
    test_data = np.load(os.path.join(BASE_DIR, "features", "data", "processed", "test.npz"), allow_pickle=True)

    train_X = train_data["X"]
    train_y = train_data["y"]
    train_eids = train_data["event_ids"].astype(str)

    test_X = test_data["X"]
    test_y = test_data["y"]
    test_eids = test_data["event_ids"].astype(str)

    # Combine all events
    all_X = np.vstack([train_X, test_X])
    all_y = np.concatenate([train_y, test_y])
    all_eids = np.concatenate([train_eids, test_eids])
    
    event_id_to_idx = {eid: i for i, eid in enumerate(all_eids)}

    print("Querying Postgres for events and anomaly scores...")
    engine = get_pg_engine()
    query = """
        SELECT 
            e.event_id, 
            e.protocol_type, 
            e.service, 
            e.flag, 
            e.label, 
            e.is_attack, 
            CAST(e.raw_features->>'dst_host_srv_count' AS FLOAT) as dst_host_srv_count,
            CAST(e.raw_features->>'dst_host_count' AS FLOAT) as dst_host_count,
            COALESCE(a.anomaly_score, 0) as anomaly_score
        FROM network_event e
        LEFT JOIN anomaly_detection_result a ON e.event_id = a.event_id
    """
    df = pd.read_sql(query, engine)
    df['event_id'] = df['event_id'].astype(str)
    
    print("Computing synthetic hosts...")
    df = generate_synthetic_hosts(df)

    # Compute host aggregate features
    print("Computing host aggregates...")
    # Group by src_host_id
    host_stats = df.groupby('src_host_id').agg(
        event_count=('event_id', 'count'),
        mean_anomaly_score=('anomaly_score', 'mean'),
        attack_ratio=('is_attack', 'mean')
    ).reset_index()
    
    # Wait, some destination hosts might not be sources. We should get ALL unique host_ids.
    all_hosts = set(df['src_host_id']).union(set(df['dst_host_id']))
    
    host_mapping = {host_id: i for i, host_id in enumerate(all_hosts)}
    num_hosts = len(host_mapping)
    
    # Prepare host feature matrix (default to 0 for dest-only hosts)
    host_x = np.zeros((num_hosts, 3), dtype=np.float32)
    for _, row in host_stats.iterrows():
        idx = host_mapping[row['src_host_id']]
        host_x[idx, 0] = row['event_count']
        host_x[idx, 1] = row['mean_anomaly_score']
        host_x[idx, 2] = row['attack_ratio']
    
    # Scale host features so large event counts don't explode gradients
    host_x[:, 0] = np.log1p(host_x[:, 0])

    print("Building HeteroData object...")
    data = HeteroData()
    
    # Event nodes
    data['event'].x = torch.tensor(all_X, dtype=torch.float)
    data['event'].y = torch.tensor(all_y, dtype=torch.long)
    
    # Train / Test masks
    train_mask = torch.zeros(len(all_y), dtype=torch.bool)
    test_mask = torch.zeros(len(all_y), dtype=torch.bool)
    train_mask[:len(train_y)] = True
    test_mask[len(train_y):] = True
    data['event'].train_mask = train_mask
    data['event'].test_mask = test_mask

    # Host nodes
    data['host'].x = torch.tensor(host_x, dtype=torch.float)

    # Edges: host -> event and event -> host (reversed as requested)
    # The prompt explicitly asked for: (event)-[generated_by]->(host)
    # Let's map them
    event_src_edges = []
    for _, row in df.iterrows():
        e_idx = event_id_to_idx.get(row['event_id'])
        if e_idx is not None:
            h_idx = host_mapping[row['src_host_id']]
            event_src_edges.append([e_idx, h_idx])
            
    edge_index_event_host = torch.tensor(event_src_edges, dtype=torch.long).t().contiguous()
    data['event', 'generated_by', 'host'].edge_index = edge_index_event_host
    
    # We should also add host->event for bidirectional message passing (often needed in PyG)
    # The prompt mentions "reversed for message passing as (event)-[generated_by]->(host)" 
    # But usually we need undirected or both directions. We can use T.ToUndirected() later.
    
    # Edges: host -> host
    host_host_edges = []
    for _, row in df.iterrows():
        src_idx = host_mapping[row['src_host_id']]
        dst_idx = host_mapping[row['dst_host_id']]
        host_host_edges.append([src_idx, dst_idx])
        
    edge_index_host_host = torch.tensor(host_host_edges, dtype=torch.long).t().contiguous()
    data['host', 'communicates_with', 'host'].edge_index = edge_index_host_host
    
    # Add reverse edges automatically to allow message passing in both directions
    data = T.ToUndirected()(data)

    print("\n--- Graph Statistics ---")
    print(f"Num Hosts: {data['host'].num_nodes}")
    print(f"Num Events: {data['event'].num_nodes}")
    
    # In ToUndirected, PyG creates rev_ edges
    # We count the unique relations
    num_comm = edge_index_host_host.shape[1]
    print(f"Num communicates_with edges (raw from DB): {num_comm}")
    
    # Wait, the prompt says "2,162 communicates_with edges". 
    # If we simply append [src, dst] for each row, we get 148,517 edges! 
    # In Neo4j, `MERGE (src)-[r:COMMUNICATES_WITH]->(dst)` created unique relationships.
    # We need to deduplicate them.
    unique_comm_edges = list(set(tuple(x) for x in host_host_edges))
    edge_index_host_host_unique = torch.tensor(unique_comm_edges, dtype=torch.long).t().contiguous()
    data['host', 'communicates_with', 'host'].edge_index = edge_index_host_host_unique
    
    print(f"Num unique communicates_with edges: {edge_index_host_host_unique.shape[1]}")

    artifacts_dir = os.path.join(os.path.dirname(__file__), "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    out_path = os.path.join(artifacts_dir, "graph_data.pt")
    
    torch.save(data, out_path)
    # Save the order of test events so we can log them properly later
    torch.save(test_eids, os.path.join(artifacts_dir, "test_eids.pt"))
    print(f"Graph data saved to {out_path}")

if __name__ == "__main__":
    main()
