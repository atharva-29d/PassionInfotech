import os
from fastapi import APIRouter, Query, HTTPException
from neo4j import GraphDatabase
from sqlalchemy import create_engine, text
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ENV_PATH = os.path.join(BASE_DIR, "backend", "graph", ".env")
load_dotenv(ENV_PATH)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "threatpass")

PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = os.getenv("DB_PORT", "5433")
PG_NAME = os.getenv("DB_NAME", "threat_hunting")
PG_USER = os.getenv("DB_USER", "postgres")
PG_PASSWORD = os.getenv("DB_PASSWORD", "")
PG_URI = f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_NAME}"

# Dependency-like accessors
def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_pg_engine():
    return create_engine(PG_URI)

import subprocess
import sys

@router.post("/alerts/simulate")
def simulate_attack():
    producer_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "streaming", "producer.py")
    subprocess.Popen([sys.executable, producer_path, "--count", "1"])
    return {"status": "simulating"}

@router.get("/alerts/recent")
def get_recent_alerts(limit: int = 5):
    query = text("""
        SELECT e.event_id, e.protocol_type, e.service, g.predicted_class, g.confidence
        FROM network_event e
        JOIN gnn_detection_result g ON e.event_id = g.event_id
        ORDER BY g.detection_time DESC
        LIMIT :limit
    """)
    engine = get_pg_engine()
    with engine.connect() as conn:
        result = conn.execute(query, {"limit": limit}).fetchall()
        
    return [
        {
            "event_id": row[0],
            "protocol_type": row[1],
            "service": row[2],
            "predicted_class": row[3],
            "confidence": row[4]
        }
        for row in result
    ]

@router.get("/overview")
def get_overview():
    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            host_res = session.run("MATCH (h:Host) RETURN count(h) AS c").single()
            event_res = session.run("MATCH (e:Event) RETURN count(e) AS c").single()
            edge_res = session.run("MATCH ()-[r:COMMUNICATES_WITH]->() RETURN count(r) AS c").single()
            
            total_hosts = host_res["c"] if host_res else 0
            total_events = event_res["c"] if event_res else 0
            total_edges = edge_res["c"] if edge_res else 0
            
            # Subquery to get highest event count host to serve as default for frontend
            highest_host_res = session.run("""
                MATCH (h:Host)-[:GENERATED]->(e:Event)
                RETURN h.host_id AS host_id, count(e) AS event_count
                ORDER BY event_count DESC LIMIT 1
            """).single()
            
            highest_host_id = highest_host_res["host_id"] if highest_host_res else None
    except Exception as e:
        driver.close()
        raise HTTPException(status_code=500, detail=f"Neo4j Error: {str(e)}")
    
    driver.close()
    
    # Get attack ratio from Postgres
    engine = get_pg_engine()
    try:
        with engine.begin() as conn:
            query = text("""
                SELECT 
                    SUM(CASE WHEN predicted_class = 'anomaly' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS attack_ratio
                FROM gnn_detection_result
            """)
            res = conn.execute(query).fetchone()
            attack_ratio = float(res[0]) if res and res[0] is not None else 0.0
    except Exception as e:
        attack_ratio = 0.0
        
    return {
        "total_hosts": total_hosts,
        "total_events": total_events,
        "total_edges": total_edges,
        "attack_ratio": round(attack_ratio, 4),
        "default_host_id": highest_host_id
    }


@router.get("/subgraph")
def get_subgraph(node_id: str, depth: int = Query(1, ge=1, le=3)):
    driver = get_neo4j_driver()
    
    # Find the node (Host or Event) and its neighbors
    cypher_query = f"""
        MATCH path = (start)-[*1..{depth}]-(neighbor)
        WHERE start.host_id = $node_id OR start.event_id = $node_id
        RETURN path LIMIT 150
    """
    
    nodes_map = {}
    edges_list = []
    
    try:
        with driver.session() as session:
            result = session.run(cypher_query, node_id=node_id)
            for record in result:
                path = record["path"]
                
                # Extract nodes
                for node in path.nodes:
                    node_id = node.get("host_id") or node.get("event_id")
                    if node_id and node_id not in nodes_map:
                        node_type = "host" if "Host" in node.labels else "event"
                        node_data = {
                            "id": node_id,
                            "type": node_type,
                            "label": f"{node_type.capitalize()}: {node_id[:8]}...",
                            "risk_score": 0.0 # Default, to be joined from Postgres
                        }
                        if node_type == "host":
                            node_data["continent"] = node.get("continent")
                            node_data["country"] = node.get("country")
                            node_data["region"] = node.get("region")
                            node_data["ip_address"] = node.get("ip_address")
                        nodes_map[node_id] = node_data
                        
                # Extract edges
                for rel in path.relationships:
                    start_node = rel.start_node
                    end_node = rel.end_node
                    
                    start_id = start_node.get("host_id") or start_node.get("event_id")
                    end_id = end_node.get("host_id") or end_node.get("event_id")
                    
                    edges_list.append({
                        "source": start_id,
                        "target": end_id,
                        "relationship": rel.type,
                        "weight": 1.0
                    })
    except Exception as e:
        driver.close()
        raise HTTPException(status_code=500, detail=f"Neo4j Query Error: {str(e)}")
    
    driver.close()
    
    # Edge deduplication
    unique_edges = []
    seen = set()
    for e in edges_list:
        k = (e["source"], e["target"], e["relationship"])
        if k not in seen:
            seen.add(k)
            unique_edges.append(e)

    # Join risk scores from Postgres
    event_ids = [k for k, v in nodes_map.items() if v["type"] == "event"]
    
    if event_ids:
        engine = get_pg_engine()
        try:
            with engine.begin() as conn:
                # In batches if there are too many (subgraph shouldn't be too huge though)
                query = text("""
                    SELECT event_id, confidence, predicted_class 
                    FROM gnn_detection_result 
                    WHERE event_id = ANY(:eids)
                """)
                res = conn.execute(query, {"eids": event_ids}).fetchall()
                
                for row in res:
                    eid = str(row[0])
                    conf = float(row[1])
                    p_class = row[2]
                    # Map confidence logic: if predicted 'normal', risk = 1 - conf (close to 0)
                    # If predicted 'anomaly', risk = conf (close to 1)
                    # Assuming softmax output where confidence is for the predicted class
                    # Wait, our script saved probability of class 1 directly in 'confidence'!
                    # Let's just use the raw 'confidence' which is P(attack)
                    nodes_map[eid]["risk_score"] = conf
                    
            # For hosts, calculate average risk score of generated events
            # For simplicity in this bounded response, we'll just average the events returned in this subgraph
            # Or we could fetch host aggregates from Postgres if we had a host table.
            # Let's average the risk_scores of event nodes connected to each host in this subgraph.
            for e in unique_edges:
                if e["relationship"] == "GENERATED":
                    h_id = e["source"]
                    e_id = e["target"]
                    if h_id in nodes_map and e_id in nodes_map and nodes_map[e_id]["risk_score"] > 0:
                        if "total_risk" not in nodes_map[h_id]:
                            nodes_map[h_id]["total_risk"] = 0
                            nodes_map[h_id]["event_cnt"] = 0
                        nodes_map[h_id]["total_risk"] += nodes_map[e_id]["risk_score"]
                        nodes_map[h_id]["event_cnt"] += 1
                        
            for k, v in nodes_map.items():
                if v["type"] == "host" and "event_cnt" in v:
                    nodes_map[k]["risk_score"] = v["total_risk"] / v["event_cnt"]
                    del nodes_map[k]["total_risk"]
                    del nodes_map[k]["event_cnt"]
                    
        except Exception as e:
            pass # Fail gracefully, risk scores remain 0.0

    return {
        "nodes": list(nodes_map.values()),
        "edges": unique_edges
    }
