# Threat Hunting Platform - Power Grid Cyber Environment

An advanced, real-time Threat Hunting and Graph Intelligence platform built to monitor and classify network telemetry. This system combines traditional baseline anomaly detection (Isolation Forest) with structural Graph Neural Networks (GraphSAGE) to provide comprehensive threat intelligence over streaming data.

## Architecture Highlights
- **Data Ingestion:** Real-time event ingestion via **Apache Kafka**. Events are deterministically routed to continent-specific topics.
- **Relational Storage:** **PostgreSQL** stores the raw telemetry (`network_event`), geography lookups (`host_geo`), and model inferences (`anomaly_detection_result`, `gnn_detection_result`).
- **Graph Intelligence:** **Neo4j** builds a real-time topology of network hosts and their communication patterns.
- **Machine Learning:** 
  - *Isolation Forest* for baseline statistical anomalies.
  - *Graph Neural Network (Heterogeneous GraphSAGE)* for structural relationship-based threat classification.
- **API & UI:** A **FastAPI** backend powering a live **React/Vite** 2D force-directed graph dashboard.

## Project Structure
```text
.
├── backend/
│   ├── api/            # FastAPI endpoints (graph topology, stats, simulation)
│   ├── features/       # Feature engineering pipelines (scikit-learn)
│   ├── graph/          # Neo4j ingestion, geography assignment, determinism logic
│   ├── ingestion/      # PostgreSQL schema, environment variables, bulk load scripts
│   ├── models/         # ML models (Anomaly Detector, GNN), training scripts
│   └── streaming/      # Kafka Producers and Consumers
├── docs/               # System audits, architecture diagrams, and API contracts
├── frontend/           # React + Vite dashboard
└── requirements.txt    # Python dependencies
```

## Setup & Execution

### 1. Prerequisites
- Docker & Docker Compose (for PostgreSQL, Neo4j, and Kafka)
- Python 3.10+
- Node.js 18+

### 2. Environment Configuration
Ensure you configure the environment variables properly. Refer to:
- `backend/ingestion/.env.example` -> `backend/ingestion/.env`
- `backend/graph/.env.example` -> `backend/graph/.env`

### 3. Running the Stack
1. **Start Infrastructure (Databases & Kafka):**
   Open a terminal in the root folder and start the Docker containers:
   ```bash
   docker-compose up -d
   ```
2. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the API Backend:**
   ```bash
   cd backend/api
   uvicorn main:app --reload --port 8000
   ```
4. **Start the Kafka Consumer:**
   ```bash
   python backend/streaming/consumer.py
   ```
5. **Start the Frontend Dashboard:**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Model Performance
Our recent rigorous end-to-end evaluation yields the following performance on the test split:

**Graph Neural Network (Heterogeneous GraphSAGE)**
- Accuracy: **78.9%**
- Precision: **92.7%**
- Recall: **68.4%**
- F1 Score: **78.7%**

*Note: The platform processes events end-to-end via Kafka in ~130ms.*

---
*For a full security and data audit, see `docs/SYSTEM_AUDIT.md`.*
