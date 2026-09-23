import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend', 'graph'))

from geo_reference import get_deterministic_geo
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import neo4j

load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', 'graph', '.env'))

# PostgreSQL setup
def get_pg_engine():
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5433") # Use 5433 for Docker bypass
    name = os.getenv("DB_NAME", "threat_hunting")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "12345678")
    return create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}")

# Neo4j setup
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "threatpass")

pg_engine = get_pg_engine()
neo4j_driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def backfill():
    # 1. Create table in PG
    with pg_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS host_geo (
                host_id VARCHAR(50) PRIMARY KEY,
                ip_address VARCHAR(50) NOT NULL,
                country VARCHAR(100) NOT NULL,
                region VARCHAR(100) NOT NULL,
                continent VARCHAR(100) NOT NULL
            );
        """))
        
    # 2. Get distinct hosts from Neo4j (since that's our source of truth for hosts)
    with neo4j_driver.session() as session:
        result = session.run("MATCH (h:Host) RETURN h.host_id AS host_id")
        hosts = [row["host_id"] for row in result]
        
    print(f"Found {len(hosts)} hosts in Neo4j.")
    
    # 3. Generate Geo Data
    geo_records = [get_deterministic_geo(h) for h in hosts]
    
    # 4. Insert into PG
    with pg_engine.begin() as conn:
        # Clear existing
        conn.execute(text("TRUNCATE TABLE host_geo;"))
        # Insert new
        conn.execute(
            text("""
                INSERT INTO host_geo (host_id, continent, country, region, ip_address)
                VALUES (:host_id, :continent, :country, :region, :ip_address)
            """),
            geo_records
        )
    print(f"Inserted {len(geo_records)} rows into host_geo.")
    
    # 5. Update Neo4j hosts with geo data
    with neo4j_driver.session() as session:
        cypher = """
        UNWIND $batch AS row
        MATCH (h:Host {host_id: row.host_id})
        SET h.continent = row.continent,
            h.country = row.country,
            h.region = row.region,
            h.ip_address = row.ip_address
        """
        # Batch update
        batch_size = 500
        for i in range(0, len(geo_records), batch_size):
            session.run(cypher, batch=geo_records[i:i+batch_size])
            
    print("Updated Neo4j hosts.")

    # 6. Verify and print distribution
    with pg_engine.connect() as conn:
        result = conn.execute(text("SELECT continent, COUNT(*) FROM host_geo GROUP BY continent;"))
        print("\n--- Host Geo Distribution ---")
        for row in result:
            print(f"{row[0]}: {row[1]}")
            
if __name__ == "__main__":
    backfill()
