# Threat Hunting Platform - System Architecture

This diagram illustrates the end-to-end data flow and layered architecture of the platform.

```mermaid
flowchart TD
    %% Define Styles
    classDef frontend fill:#005a9e,stroke:#003366,stroke-width:2px,color:#fff
    classDef backend fill:#2c3e50,stroke:#1a252f,stroke-width:2px,color:#fff
    classDef streaming fill:#e67e22,stroke:#d35400,stroke-width:2px,color:#fff
    classDef ai fill:#8e44ad,stroke:#732d91,stroke-width:2px,color:#fff
    classDef database fill:#27ae60,stroke:#1e8449,stroke-width:2px,color:#fff

    subgraph FrontendLayer ["💻 Frontend Layer (React / Vite)"]
        direction TB
        UI["Security Dashboard UI"]:::frontend
        GraphVis["Digital Twin (react-force-graph)"]:::frontend
    end

    subgraph APILayer ["⚙️ Backend API Layer (FastAPI)"]
        direction TB
        API["REST API Endpoints"]:::backend
    end

    subgraph StreamingLayer ["⚡ Real-Time Streaming Layer (Apache Kafka)"]
        direction LR
        Producer["Kafka Producer\n(Attack Simulator)"]:::streaming
        Topic[("Kafka Topic\n'network-events'")]:::streaming
    end

    subgraph AILayer ["🧠 AI & Inference Layer (Python)"]
        direction TB
        Consumer["Kafka Consumer Engine"]:::ai
        FeatureEng["Feature Engineering Pipeline"]:::ai
        
        subgraph Models ["Detection Models"]
            IF["Isolation Forest\n(Baseline)"]:::ai
            GNN["Graph Neural Network\n(PyTorch GraphSAGE)"]:::ai
        end
    end

    subgraph StorageLayer ["🗄️ Polyglot Storage Layer"]
        direction LR
        PG[("PostgreSQL\n(Events & Predictions)")]:::database
        Neo4j[("Neo4j\n(Knowledge Graph)")]:::database
    end

    %% Flow Connections
    UI <-->|HTTP/REST| API
    GraphVis <-->|Graph Topologies| API
    
    API -->|Trigger Simulation| Producer
    Producer -->|Publish Event| Topic
    Topic -->|Stream Event| Consumer
    
    Consumer --> FeatureEng
    FeatureEng --> IF
    FeatureEng --> GNN
    
    Consumer -->|Write Events & Alerts| PG
    
    API <-->|Query Alerts & Metrics| PG
    API <-->|Query Nodes & Edges| Neo4j
```

### Component Breakdown:
*   **💻 Frontend Layer**: The React dashboard the operators use. It fetches real-time data from the backend.
*   **⚙️ Backend API Layer**: The FastAPI server that bridges the databases, the UI, and triggers the attack simulator.
*   **⚡ Streaming Layer**: The Kafka message broker that ensures high-throughput, fault-tolerant ingestion of network packets.
*   **🧠 AI & Inference Layer**: A continuously running Python engine that pulls from Kafka, formats the data, and runs it through the PyTorch (GNN) and Scikit-Learn (IF) models.
*   **🗄️ Storage Layer**: 
    *   **PostgreSQL**: Handles the heavy tabular data (raw event features, AI confidence scores, historical logs).
    *   **Neo4j**: Handles the complex structural relationships (which IP talked to which IP) enabling lateral movement detection.
