# Graph Visualization API Contract

This document defines the REST API endpoints for Person B's frontend dashboard to retrieve the Neo4j graph structure and GNN anomaly classifications.

## 1. Graph Overview
**Endpoint:** `GET /api/graph/overview`  
**Description:** Returns graph-level summary statistics including node and edge counts, and the **predicted attack ratio** (specifically the ratio of events flagged as anomalous by the GNN across the test set, which differs from the raw ground-truth dataset label ratio).

**Response Body:**
```json
{
  "total_hosts": 1298,
  "total_events": 148517,
  "total_edges": 2162,
  "attack_ratio": 0.43
}
```

## 2. Graph Subgraph Traversal
**Endpoint:** `GET /api/graph/subgraph`  
**Query Parameters:**
- `node_id` (string, required): The ID of the node (host or event) to center the graph around.
- `depth` (integer, optional, default=1): Traversal depth (e.g., 1 fetches immediate neighbors).

**Description:** Returns a bounded subgraph for rendering in a web client. Due to the scale of the full graph (148k+ nodes), the API requires traversing from a specific `node_id`. 

**Response Body:**
```json
{
  "nodes": [
    {
      "id": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "type": "host",
      "label": "Host: e3b0c...",
      "risk_score": 0.95,
      "continent": "North America",
      "country": "United States",
      "region": "California",
      "ip_address": "104.16.0.5"
    },
    {
      "id": "c1f1fdb9-1111-4212-b132-0c1516e11123",
      "type": "event",
      "label": "Event: TCP / HTTP",
      "risk_score": 0.88
    }
  ],
  "edges": [
    {
      "source": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "target": "c1f1fdb9-1111-4212-b132-0c1516e11123",
      "relationship": "COMMUNICATES_WITH",
      "weight": 1.0
    }
  ]
}
```
*Note on `risk_score`: For event nodes, this reflects the raw confidence score output by the GNN model (0.0 = Benign, 1.0 = Attack). For host nodes, this is an aggregated risk metric.*

## 3. Recent Alerts
**Endpoint:** `GET /api/graph/alerts/recent`  
**Query Parameters:**
- `limit` (integer, optional, default=5): Number of recent alerts to fetch.

**Description:** Returns the most recent events streaming through Kafka, classified by the GNN.

**Response Body:**
```json
[
  {
    "event_id": "d3f6128b...",
    "protocol_type": "tcp",
    "service": "http",
    "predicted_class": "anomaly",
    "confidence": 0.98
  }
]
```
