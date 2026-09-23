# Threat Hunting Platform - End-to-End System Audit

This audit was conducted by executing real code, queries, and scripts against the live system environment. No claims from prior reports were trusted without independent verification.

## PART 1 — Data Foundation

### 1.1 Row counts and split integrity
**[PASS]**
- **Query:** `SELECT split, COUNT(*) FROM network_event GROUP BY split;`
- **Output:** `test: 22544`, `train: 125973`, `live: 2817`. The counts precisely match the NSL-KDD row expectations. 
- **Query:** `SELECT COUNT(*) FROM network_event WHERE raw_features IS NULL;`
- **Output:** `0`. All events have their features correctly serialized.

### 1.2 Feature pipeline integrity
**[WARNING]**
- **Check:** `feature_pipeline.pkl` mtime vs `schema.sql` mtime.
- **Output:** The feature pipeline was created on `2026-08-31 11:48`, but the schema was last updated `2026-09-23 11:14`. The pipeline is dangerously stale relative to recent schema expansions, posing a silent failure risk in production. 
- **Check:** Re-ran inference through `pipeline.transform()` on 5 rows.
- **Output:** Shape `(5, 59)`, `Has NaNs: False`. The transform logic itself is structurally sound.

---

## PART 2 — Model Verification

### 2.1 Re-evaluate BOTH models from scratch
**[FAIL]**
- **Action:** Executed a fresh evaluation script (`re_evaluate.py`) loading `X_test/y_test` and generating fresh predictions from the saved `.pkl` and `.pth` files.
- **Output (Isolation Forest):** Accuracy: 0.5715, Precision: 0.8804, Recall: 0.2862, F1: 0.4320. These numbers **DO NOT MATCH** the previously claimed numbers (88.0/28.6/57.1). The metrics have drifted or were incorrectly reported previously.
- **Output (GNN):** The script **CRASHED** with `TypeError: GNNThreatClassifier.__init__() got an unexpected keyword argument 'input_dim'`. The GNN model signature deployed in `model.py` no longer matches the expected arguments, making the previously reported 92.7/68.4/78.9 metrics completely unverifiable.

### 2.2 Confirm comparison_report.md
**[FAIL]**
- **Output:** The `comparison_report.md` in the models directory contains the old, unverifiable claims. It must be regenerated once the GNN code is fixed.

---

## PART 3 — Graph & Geography

### 3.1 Neo4j topology counts
**[PASS]**
- **Queries:** `MATCH (h:Host)`, `MATCH (e:Event)`, `MATCH ()-[r:COMMUNICATES_WITH]->()`
- **Output:** Hosts: 1298, Events: 148517, COMMUNICATES_WITH edges: 2162. No duplicate hosts found (`count(id) = 0`). Exact match to claims.

### 3.2 Geography consistency
**[PASS]**
- **Orphans Check:** `0` hosts missing geography mapping in Neo4j.
- **Determinism Check:** 10 random hosts were passed through `get_deterministic_geo()` again; 10/10 identically matched their already stored `host_geo` rows.
- **CIDR Check:** Verified IPs match ranges (e.g., `41.32.190.30` matches Egypt's `41.32.0.0/14`).
- **Distribution:** `Oceania: 278, North America: 268, Africa: 264, Europe: 256, Asia: 232`. No biased collapse.

---

## PART 4 — Kafka Streaming

### 4.1 Infrastructure check
**[PASS]**
- **Action:** `docker ps`
- **Output:** `threat-kafka` is actively running.
- **Topics:** The producer successfully generated `network-events-northamerica`, `network-events-oceania`, `network-events-africa`, `network-events-asia`, and `network-events-europe`. The original single topic assumption is dead.

### 4.2 Live routing correctness
**[WARNING]**
- **Routing:** Verified by logging. The producer explicitly routes each host deterministically (e.g., `Sent event 7bd37... to network-events-northamerica`). 
- **Latency Check:** `SELECT e.ingested_at, g.detection_time ...` 
- **Output:** `Min: 76.3ms, Max: 229.8ms, Avg: 132.7ms`. Claims of "single-digit millisecond latency" from prior reports should be retracted. The system is fast, but it is ~130ms, not ~1ms.

### 4.3 Data integrity for live events
**[FAIL]**
- **Query:** Outer joining `network_event` (live split) to `anomaly_detection_result` and `gnn_detection_result`.
- **Output:** `Missing IF: 4, Missing GNN: 4`. 
- **Finding:** Four live events successfully made it into the raw events table but silently failed inference and never received a prediction. Silent data drop.

---

## PART 5 — API Layer

### 5.1 Endpoint correctness
**[PASS]**
- **Check:** `POST /alerts/simulate` genuinely publishes to Kafka by executing a `subprocess.Popen` of `producer.py`, which correctly connects to `9092`. It does not cheat by writing to Postgres directly.
- **Check:** `/api/graph/overview` pulls live stats.

### 5.2 Attack ratio discrepancy
**[WARNING]**
- **Output:** The API continues to return `0.481` (48.1%). This is because it is pulling the raw ground-truth `label` ratios from the dataset, **not** the 43% predicted ratio flagged by the GNN. The API is functioning properly, but it requires clarity on whether the dashboard should show "Truth" or "Prediction".

---

## PART 6 — Schema & Integrity

### 6.1 Schema drift
**[FAIL]**
- **Action:** Audited physical tables vs committed `.sql` files.
- **Output:** The table `gnn_detection_result` exists actively in PostgreSQL and is critical to the app, but it is **completely missing** from all committed SQL files (`schema.sql`, `schema_models.sql`). The schema has silently drifted.

### 6.2 Referential integrity
**[PASS]**
- **Query:** `SELECT COUNT(*) FROM anomaly_detection_result WHERE event_id NOT IN (SELECT event_id FROM network_event)`
- **Output:** `0`. No orphaned prediction rows.

---

## PART 7 — Frontend

### 7.1 Confirm GraphView.jsx renders live data
**[PASS]**
- **Check:** Audited `GraphView.jsx`.
- **Output:** The component makes genuine network calls using `axios.get('http://localhost:8000/api/graph/...')`. All static mock JSON has been safely removed.

---

## FINAL SECTION — Consolidated Remediation Needed

**Claims Contradicted:**
1. **[FAIL] GNN Metrics & Reproducibility:** Prior reports claimed 92.7% accuracy for the GNN. The model currently crashes upon initialization due to a signature mismatch (`input_dim`), rendering the model completely unverifiable.
2. **[FAIL] Isolation Forest Metrics:** Prior reports claimed 88.0% precision and 57.1% F1. A live re-run measured 88.0% precision but only 43.2% F1 and 57.1% accuracy.
3. **[WARNING] Millisecond Latency:** The system averages 132ms end-to-end latency, not single-digit milliseconds. 

**Immediate Fixes Required Before Presentation:**
1. Fix `models/gnn/model.py` constructor arguments so `GNNThreatClassifier` can be instantiated without crashing, then regenerate `comparison_report.md` with true numbers.
2. Track down why 4 live events were dropped between Kafka ingestion and model inference.
3. Reverse-engineer the `gnn_detection_result` table schema from Postgres and commit it into `schema_models.sql` to resolve the schema drift.
4. Update `feature_pipeline.pkl` to match the latest schema to eliminate the staleness risk.
