# Threat Hunting & Graph Intelligence Platform
**Complete Project Overview & Onboarding Guide**

Welcome to the project! This document is written to help new team members understand exactly what this platform is, how it works under the hood, and what technologies we are using.

---

## 1. What is this project?
At its core, this project is a **Real-Time Cybersecurity Monitor**. 

Imagine a massive corporate network (like a power grid or an office network) where thousands of computers are constantly talking to each other. Some of this traffic is normal, but some of it might be a hacker trying to steal data or break into a server. 

Instead of having a human manually read through network logs, this platform acts as an intelligent security guard. It ingests network traffic in real-time, uses **Artificial Intelligence (AI)** to classify whether the traffic is "Normal" or an "Anomaly" (an attack), and visualizes the entire network on a live, interactive map.

---

## 2. Core Concepts (The "Why")
To understand this project, you need to know about three main concepts we rely on:

1. **Streaming Data:** Network traffic doesn't stop. We use a tool called **Apache Kafka**, which acts like a massive, high-speed conveyor belt. As soon as a network event happens, it goes on the belt and is instantly processed by our AI without waiting.
2. **Graph Intelligence:** Traditional security systems look at a single event in isolation (e.g., "Computer A sent 500 bytes to Computer B"). Our system uses a **Graph Database (Neo4j)** to see the bigger picture—acting like a social network map for computers. We can see if Computer A has recently talked to 50 other suspicious computers. 
3. **Graph Neural Networks (GNN):** Because our data is structured as a "Graph" (computers connected by communication lines), we use a highly advanced AI called a GNN. It learns to spot attacks not just by looking at a single network packet, but by analyzing the *behavior of the entire neighborhood* of computers.

---

## 3. How it Works (The Data Flow)
Here is the step-by-step journey of a single piece of network traffic passing through our platform:

1. **Ingestion (The Producer):** A piece of network traffic (from a dataset called NSL-KDD) is converted into a JSON message. We automatically assign it a realistic IP address, Country, and Continent.
2. **The Conveyor Belt (Kafka):** The message is published to a continent-specific Kafka topic (e.g., `network-events-asia`).
3. **Processing & AI (The Consumer):** Our Python backend constantly listens to Kafka. The millisecond an event arrives:
   - It runs the event through a basic AI model (**Isolation Forest**).
   - It runs the event through our advanced AI model (**Graph Neural Network**).
4. **Storage (Postgres & Neo4j):** The raw data and the AI predictions are permanently saved to **PostgreSQL**. Simultaneously, the relationship ("Computer A talked to Computer B") is mapped into **Neo4j**.
5. **Visualization (React UI):** The frontend dashboard queries the backend and displays the network nodes as floating bubbles on the screen, coloring them red if an attack is detected.

---

## 4. What's Been Implemented?
The platform is fully functional end-to-end. Here is the technology stack and what has been built:

### A. The Data Layer
*   **NSL-KDD Dataset:** We use a famous cybersecurity dataset as our baseline traffic.
*   **Synthetic Geography:** Because the original dataset lacks IP addresses, we wrote a deterministic hashing algorithm. It takes a computer's ID and mathematically guarantees it always gets the exact same real-world IP address, Region, and Continent every single time the system runs.

### B. The Infrastructure Layer
*   **Apache Kafka:** Runs natively using KRaft (no ZooKeeper needed) to handle the real-time data queues.
*   **PostgreSQL:** Stores tabular data: the raw events, the geography lookup tables, and the AI tracking tables.
*   **Neo4j:** Stores the nodes (Hosts) and edges (Communications).

### C. The Machine Learning (AI) Layer
We implemented two models to prove our advanced system is better than older methods:
*   **Baseline (Isolation Forest):** An unsupervised algorithm that looks for statistical outliers. It acts as our "basic" standard. (Accuracy: ~57%).
*   **Advanced (Heterogeneous GraphSAGE):** Built using **PyTorch Geometric**. It is a neural network that understands graph structures. (Accuracy: **78.9%**, Precision: **92.7%**).

### D. The Backend Layer
*   Built in Python using **FastAPI**. 
*   It exposes endpoints so the frontend can request data (e.g., `GET /api/graph/overview`) or trigger new simulations (`POST /api/graph/alerts/simulate`).

### E. The Frontend Layer
*   Built with **React** and **Vite**.
*   Uses `react-force-graph-2d` to render a beautiful, physics-based 2D map of the network. You can hover over nodes to see their IP address and country.

---

## 5. How to Run It (For Newbies)
*(Note: You need Docker, Python, and Node.js installed).*

1. **Start the Databases:** Open Docker Desktop to ensure Postgres, Neo4j, and Kafka are running.
2. **Start the API:** 
   Open a terminal, go to `backend/api` and run: `uvicorn main:app --reload --port 8000`
3. **Start the Kafka Consumer:**
   Open a terminal, go to the root folder, and run: `python backend/streaming/consumer.py` (This turns on the AI engine).
4. **Start the Dashboard:**
   Open a terminal, go to `frontend/`, run `npm install`, then run `npm run dev`.

Once the UI opens in your browser, click **"Simulate Attack"** to watch the entire pipeline work in real-time!

---
*If you have deeper technical questions, review the `docs/SYSTEM_AUDIT.md` file for exact latency numbers and database schemas.*
