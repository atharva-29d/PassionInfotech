"""
build_graph.py

Pulls network events from PostgreSQL, generates synthetic source and destination
host identities based on selected features, and batch-loads the resulting topology
into Neo4j.
"""

import os
import hashlib
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from neo4j import GraphDatabase
from geo_reference import get_deterministic_geo

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) # This is backend
ENV_PATH = os.path.join(BASE_DIR, "graph", ".env")

load_dotenv(ENV_PATH)

def get_pg_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")

def hash_str(s):
    return hashlib.sha256(s.encode()).hexdigest()[:16]

def generate_synthetic_hosts(df):
    print("Generating synthetic host identities and geography...")
    # Fill NAs safely just in case
    df['dst_host_srv_count'] = df['dst_host_srv_count'].fillna(0).astype(float)
    df['dst_host_count'] = df['dst_host_count'].fillna(0).astype(float)
    
    # Bucket into 10 ranges (values range roughly 0-255)
    df['dst_host_srv_count_bucket'] = (df['dst_host_srv_count'] // 25.5).astype(int)
    df['dst_host_count_bucket'] = (df['dst_host_count'] // 25.5).astype(int)
    
    # Generate Source ID
    df['src_host_id'] = df.apply(
        lambda row: hash_str(f"{row['protocol_type']}_{row['service']}_{row['dst_host_srv_count_bucket']}"), 
        axis=1
    )
    
    # Generate Destination ID
    df['dst_host_id'] = df.apply(
        lambda row: hash_str(f"{row['service']}_{row['flag']}_{row['dst_host_count_bucket']}"), 
        axis=1
    )

    # Attach deterministic geo mapping for each host
    # For Neo4j batch insertion
    src_geos = df['src_host_id'].apply(get_deterministic_geo)
    df['src_continent'] = src_geos.apply(lambda x: x['continent'])
    df['src_country'] = src_geos.apply(lambda x: x['country'])
    df['src_region'] = src_geos.apply(lambda x: x['region'])
    df['src_ip'] = src_geos.apply(lambda x: x['ip_address'])

    dst_geos = df['dst_host_id'].apply(get_deterministic_geo)
    df['dst_continent'] = dst_geos.apply(lambda x: x['continent'])
    df['dst_country'] = dst_geos.apply(lambda x: x['country'])
    df['dst_region'] = dst_geos.apply(lambda x: x['region'])
    df['dst_ip'] = dst_geos.apply(lambda x: x['ip_address'])
    
    return df

def batch_load_neo4j(driver, records, batch_size=5000):
    cypher_query = """
    UNWIND $batch AS row
    
    MERGE (src:Host {host_id: row.src_host_id})
    ON CREATE SET 
        src.continent = row.src_continent, 
        src.country = row.src_country, 
        src.region = row.src_region, 
        src.ip_address = row.src_ip
        
    MERGE (dst:Host {host_id: row.dst_host_id})
    ON CREATE SET 
        dst.continent = row.dst_continent, 
        dst.country = row.dst_country, 
        dst.region = row.dst_region, 
        dst.ip_address = row.dst_ip
    
    MERGE (e:Event {event_id: row.event_id})
    ON CREATE SET 
        e.label = row.label, 
        e.is_attack = row.is_attack, 
        e.risk_score = row.anomaly_score
        
    MERGE (src)-[:GENERATED]->(e)
    
    MERGE (src)-[r:COMMUNICATES_WITH]->(dst)
    ON CREATE SET r.weight = 1
    ON MATCH SET r.weight = r.weight + 1
    """
    
    total = len(records)
    with driver.session() as session:
        # Create indexes for performance before starting
        session.run("CREATE INDEX IF NOT EXISTS FOR (h:Host) ON (h.host_id)")
        session.run("CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.event_id)")
        
        for i in range(0, total, batch_size):
            batch = records[i:i+batch_size]
            session.run(cypher_query, batch=batch)
            print(f"Loaded {i + len(batch)} / {total} records into Neo4j...")
            
        # Post-process the event counts safely
        print("Calculating event_count for all Hosts...")
        session.run("""
        MATCH (h:Host)
        OPTIONAL MATCH (h)-[:GENERATED]->(e:Event)
        WITH h, count(e) AS cnt
        SET h.event_count = cnt
        """)

def main():
    pg_engine = get_pg_engine()
    
    print("Extracting events from PostgreSQL...")
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
            a.anomaly_score
        FROM network_event e
        LEFT JOIN anomaly_detection_result a ON e.event_id = a.event_id
    """
    
    df = pd.read_sql(query, pg_engine)
    print(f"Extracted {len(df)} rows.")
    
    df = generate_synthetic_hosts(df)
    
    # Cast UUID objects to strings so Neo4j driver can serialize them
    df['event_id'] = df['event_id'].astype(str)
    
    # Convert for Neo4j consumption (replace NaNs with None)
    records = df.where(pd.notnull(df), None).to_dict('records')
    
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "threatpass")
    
    print(f"Connecting to Neo4j at {neo4j_uri}...")
    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    
    try:
        batch_load_neo4j(driver, records, batch_size=5000)
        print("Graph build complete!")
    finally:
        driver.close()

if __name__ == "__main__":
    main()
