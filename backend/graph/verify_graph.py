from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__)) # This is backend
ENV_PATH = os.path.join(BASE_DIR, "graph", ".env")
load_dotenv(ENV_PATH)

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD", "threatpass")

driver = GraphDatabase.driver(uri, auth=(user, password))

print("--- GRAPH VERIFICATION ---\n")

with driver.session() as session:
    # 1. Total Hosts
    res = session.run("MATCH (h:Host) RETURN count(h) AS total")
    print(f"Total Host nodes: {res.single()['total']}")
    
    # 2. Total Events
    res = session.run("MATCH (e:Event) RETURN count(e) AS total")
    print(f"Total Event nodes: {res.single()['total']}")

    # 3. Total COMMUNICATES_WITH
    res = session.run("MATCH ()-[r:COMMUNICATES_WITH]->() RETURN count(r) AS total")
    print(f"Total COMMUNICATES_WITH relationships: {res.single()['total']}")

    # 4. Top 10 Busiest Hosts
    print("\nTop-10 busiest hosts by event count:")
    res = session.run("""
        MATCH (h:Host)-[:GENERATED]->(e:Event) 
        RETURN h.host_id AS host_id, count(e) AS cnt 
        ORDER BY count(e) DESC LIMIT 10
    """)
    for record in res:
        print(f"Host: {record['host_id']}, Events: {record['cnt']}")

driver.close()
