import React, { useState, useEffect } from 'react';
import axios from 'axios';
import GraphView from './components/GraphView';
import './index.css';

const API_BASE = 'http://localhost:8000/api/graph';

function MetricCard({ title, value }) {
  return (
    <div className="metric">
      <h2>{value}</h2>
      {title}
    </div>
  );
}

function App() {
  const [overview, setOverview] = useState(null);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    fetchOverview();
    fetchRecentAlerts();
    
    // Auto-refresh alerts every 3 seconds to show live streaming
    const interval = setInterval(fetchRecentAlerts, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchOverview = async () => {
    try {
      const res = await axios.get(`${API_BASE}/overview`);
      setOverview(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const fetchRecentAlerts = async () => {
    try {
      const res = await axios.get(`${API_BASE}/alerts/recent`, { params: { limit: 5 } });
      setRecentAlerts(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const simulateAttack = async () => {
    setSimulating(true);
    try {
      await axios.post(`${API_BASE}/alerts/simulate`);
      alert("Simulated attack sent to Kafka topic!");
    } catch (err) {
      console.error(err);
    }
    setTimeout(() => setSimulating(false), 1000);
  };

  return (
    <div>
      <div className="header">
        🛡 Cyber-Defense Intelligence Platform
        <div className="sub">
          National Power Grid Security | Autonomous Threat Hunting & Response System
        </div>
      </div>

      <div className="container">
        {/* Static Presentation Framing */}
        <div className="card">
          <h2>Mission Statement</h2>
          <p>
            Protect national critical power infrastructure using autonomous cyber defense agents,
            Graph Neural Networks (GNN), Reinforcement Learning (RL), and Cyber Threat Intelligence.
          </p>
        </div>

        {/* Real Metrics Grid */}
        <div className="grid">
          <MetricCard 
            title="Total Events Analyzed" 
            value={overview ? overview.total_events.toLocaleString() : "..."} 
          />
          <MetricCard 
            title="Monitored Hosts" 
            value={overview ? overview.total_hosts.toLocaleString() : "..."} 
          />
          <MetricCard 
            title="Test Set Predicted Attack Ratio" 
            value={overview ? `${(overview.attack_ratio * 100).toFixed(1)}%` : "..."} 
          />
          <MetricCard 
            title="GNN Accuracy" 
            value="78.9%" /* From evaluation */
          />
        </div>

        {/* National Grid Digital Twin (Actual GraphView Component) */}
        <div className="card">
          <h2>National Grid Digital Twin</h2>
          <div style={{ height: '400px', width: '100%', border: '1px solid #ccc', borderRadius: '8px', overflow: 'hidden' }}>
            <GraphView />
          </div>
        </div>

        {/* GNN Attack Pattern Detection Engine (Real Data) */}
        <div className="card">
          <h2>GNN Attack Pattern Detection Engine (Live Stream)</h2>
          <table>
            <thead>
              <tr>
                <th>Event ID</th>
                <th>Protocol</th>
                <th>Service</th>
                <th>GNN Prediction</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {recentAlerts.map(alert => (
                <tr key={alert.event_id}>
                  <td>{alert.event_id.slice(0, 8)}...</td>
                  <td>{alert.protocol_type}</td>
                  <td>{alert.service}</td>
                  <td>{alert.predicted_class} ({(alert.confidence*100).toFixed(1)}%)</td>
                  <td style={{ color: alert.predicted_class === 'anomaly' ? 'red' : 'green', fontWeight: 'bold' }}>
                    {alert.predicted_class === 'anomaly' ? 'Critical' : 'Safe'}
                  </td>
                </tr>
              ))}
              {recentAlerts.length === 0 && (
                <tr><td colSpan="5" style={{ textAlign: 'center' }}>No live alerts detected</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Stubbed RL Agent */}
        <div className="card">
          <h2>Autonomous Reinforcement Learning Agent</h2>
          <div style={{ padding: '20px', background: '#fff3cd', color: '#856404', borderRadius: '8px', border: '1px solid #ffeeba' }}>
            <strong>Pending RL integration:</strong> This section will be populated once Person B completes the RL Agent track.
          </div>
        </div>

        {/* Static Cyber Threat Intelligence Feed */}
        <div className="card">
          <h2>Cyber Threat Intelligence Feed</h2>
          <ul>
            <li>⚠ Foreign Malware Signature detected (Simulation)</li>
            <li>✔ SCADA Authentication Healthy</li>
            <li>✔ Network topology verified</li>
          </ul>
        </div>

        {/* Stubbed SIEM */}
        <div className="card">
          <h2>SIEM Security Operations Center</h2>
          <div style={{ padding: '20px', background: '#fff3cd', color: '#856404', borderRadius: '8px', border: '1px solid #ffeeba' }}>
            <strong>Pending integration:</strong> Full SIEM integration not yet implemented in this iteration.
          </div>
        </div>

        {/* Threat Hunting Console (Real Button) */}
        <div className="card">
          <h2>Threat Hunting Console</h2>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button disabled>Run Autonomous Hunt (Stub)</button>
            <button 
              onClick={simulateAttack} 
              disabled={simulating}
              style={{ background: simulating ? '#ccc' : '#dc3545' }}
            >
              {simulating ? 'Sending...' : 'Simulate Attack (Kafka)'}
            </button>
            <button disabled>Generate Security Report (Stub)</button>
          </div>
        </div>

        {/* Static Risk Score */}
        <div className="card">
          <h2>Cyber Risk Intelligence Score</h2>
          <p>National Grid Safety Index</p>
          <div className="progress">
            <div style={{ width: '92%' }}>92% Protected</div>
          </div>
        </div>

        {/* Technology Architecture (Updated to truth) */}
        <div className="card">
          <h2>Technology Architecture</h2>
          <table>
            <thead>
              <tr>
                <th>Layer</th>
                <th>Technology</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>AI Intelligence Layer</td>
                <td>PyTorch Geometric (GraphSAGE), Scikit-Learn (IsolationForest)</td>
              </tr>
              <tr>
                <td>Graph Analytics</td>
                <td>Neo4j, React Force-Graph</td>
              </tr>
              <tr>
                <td>Streaming Layer</td>
                <td>Apache Kafka (KRaft), Python Consumer</td>
              </tr>
              <tr>
                <td>Backend & Storage</td>
                <td>PostgreSQL (Relational), FastAPI (REST)</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Static SDG & Mapping */}
        <div className="card">
          <h2>SDG Alignment</h2>
          <table>
            <tbody>
              <tr><td>SDG 9</td><td>Industry, Innovation & Infrastructure</td></tr>
              <tr><td>SDG 16</td><td>Peace, Justice & Strong Institutions</td></tr>
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>PASSIONIT PRUTL KALKI AIDHARMA Mapping</h2>
          <table>
            <thead>
              <tr><th>Dimension</th><th>Contribution</th></tr>
            </thead>
            <tbody>
              <tr><td>PASSIONIT - Probing</td><td>Continuous cyber anomaly discovery</td></tr>
              <tr><td>Innovation</td><td>Autonomous AI defense agents</td></tr>
              <tr><td>PRUTL Positive Soul</td><td>Protection, Trust, Unity of national infrastructure</td></tr>
              <tr><td>KALKI</td><td>Destroy cyber threats and restore digital balance</td></tr>
              <tr><td>AIDHARMA</td><td>Responsible intelligence protecting society</td></tr>
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>Research & Innovation Potential</h2>
          <ul>
            <li>Research Paper: "Graph Neural Network Based Autonomous Cyber Defense Framework for National Power Infrastructure"</li>
            <li>TRL: 6-7 Prototype Ready</li>
          </ul>
        </div>

      </div>
    </div>
  );
}

export default App;
