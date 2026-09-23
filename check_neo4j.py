import neo4j

URI = "bolt://localhost:7687"
AUTH = ("neo4j", "threatpass")

driver = neo4j.GraphDatabase.driver(URI, auth=AUTH)

with driver.session() as session:
    print("--- 3.1 Neo4j counts ---")
    hosts = session.run("MATCH (h:Host) RETURN count(h)").single()[0]
    print(f"Hosts: {hosts}")
    
    events = session.run("MATCH (e:Event) RETURN count(e)").single()[0]
    print(f"Events: {events}")
    
    rels = session.run("MATCH ()-[r:COMMUNICATES_WITH]->() RETURN count(r)").single()[0]
    print(f"COMMUNICATES_WITH edges: {rels}")
    
    dups = session.run("MATCH (h:Host) WITH h.host_id AS id, count(h) AS c WHERE c > 1 RETURN count(id)").single()[0]
    print(f"Duplicate hosts: {dups}")
    
    print("\n--- 3.2 Geography Consistency ---")
    # Orphans in Neo4j without Geo
    orphans = session.run("MATCH (h:Host) WHERE h.country IS NULL RETURN count(h)").single()[0]
    print(f"Hosts missing Geo in Neo4j: {orphans}")
