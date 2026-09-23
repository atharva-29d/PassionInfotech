import React, { useState, useEffect, useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api/graph';

export default function GraphView() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const fgRef = useRef();

  // Load overview on mount
  useEffect(() => {
    const fetchOverview = async () => {
      try {
        const res = await axios.get(`${API_BASE}/overview`);
        setOverview(res.data);
        if (res.data.default_host_id) {
          fetchSubgraph(res.data.default_host_id);
        } else {
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to fetch graph overview", err);
        setError("Failed to connect to Graph API. Ensure the backend is running.");
        setLoading(false);
      }
    };
    fetchOverview();
  }, []);

  const fetchSubgraph = async (nodeId) => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API_BASE}/subgraph`, {
        params: { node_id: nodeId, depth: 1 }
      });
      // The API returns edges as { source, target }, but ForceGraph2D expects exactly that format.
      setGraphData(res.data);
    } catch (err) {
      console.error("Failed to fetch subgraph", err);
      setError("Failed to fetch subgraph data.");
    } finally {
      setLoading(false);
    }
  };

  const handleNodeClick = useCallback((node) => {
    // Re-fetch centered on clicked node
    fetchSubgraph(node.id);
  }, []);

  // Determine node color by risk
  const getNodeColor = (node) => {
    if (node.type === 'host') {
      // High risk hosts are red, low risk are blue
      return node.risk_score > 0.5 ? '#ff4d4f' : '#1890ff';
    } else {
      // High risk events are red, low risk are green
      return node.risk_score > 0.5 ? '#ff4d4f' : '#52c41a';
    }
  };

  if (error) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#ff4d4f' }}>
        <h3>Error Loading Graph</h3>
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh' }}>
      {/* Overlay UI */}
      <div style={{ 
        position: 'absolute', 
        top: 10, left: 10, 
        zIndex: 10, 
        background: 'rgba(255, 255, 255, 0.9)', 
        padding: '1rem', 
        borderRadius: '8px',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
        fontFamily: 'sans-serif'
      }}>
        <h2>Threat Hunting Graph</h2>
        {loading && <p>Loading graph...</p>}
        {overview && (
          <div style={{ fontSize: '0.9rem' }}>
            <p><strong>Total Hosts:</strong> {overview.total_hosts.toLocaleString()}</p>
            <p><strong>Total Events:</strong> {overview.total_events.toLocaleString()}</p>
            <p><strong>Total Edges:</strong> {overview.total_edges.toLocaleString()}</p>
            <p><strong>System Attack Ratio:</strong> {(overview.attack_ratio * 100).toFixed(2)}%</p>
          </div>
        )}
        <div style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
          <strong>Legend:</strong>
          <div style={{ display: 'flex', gap: '1rem', marginTop: '4px' }}>
             <span style={{ color: '#1890ff' }}>● Safe Host</span>
             <span style={{ color: '#52c41a' }}>● Safe Event</span>
             <span style={{ color: '#ff4d4f' }}>● Anomalous / Attack</span>
          </div>
          <p style={{ marginTop: '0.5rem', color: '#666' }}>
            <em>Click any node to explore its connections.</em>
          </p>
        </div>
      </div>

      {/* Force Directed Graph */}
      <ForceGraph2D
        ref={fgRef}
        graphData={{ nodes: graphData.nodes, links: graphData.edges }}
        nodeLabel={(node) => {
          let label = `${node.label}\nRisk Score: ${node.risk_score.toFixed(2)}`;
          if (node.country) {
            label += `\nGeo: ${node.country} (${node.continent})`;
          }
          if (node.ip_address) {
            label += `\nIP: ${node.ip_address}`;
          }
          return label;
        }}
        nodeColor={getNodeColor}
        nodeRelSize={6}
        onNodeClick={handleNodeClick}
        linkDirectionalArrowLength={3.5}
        linkDirectionalArrowRelPos={1}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        d3VelocityDecay={0.3}
      />
    </div>
  );
}
