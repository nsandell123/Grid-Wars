import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import './App.css';

const API = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

function App() {
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);
  const [state, setState] = useState(null);
  const [selectedBattery, setSelectedBattery] = useState(null);

  // --- WebSocket connection ---
  useEffect(() => {
    let ws;
    let reconnectTimeout;

    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setState(data);
      };
      ws.onclose = () => {
        reconnectTimeout = setTimeout(connect, 1000);
      };
    }

    connect();
    return () => {
      ws?.close();
      clearTimeout(reconnectTimeout);
    };
  }, []);

  // --- D3 Visualization ---
  useEffect(() => {
    if (!state || !svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    // Layout batteries in a grid pattern
    const cols = 5;
    const rows = Math.ceil(state.batteries.length / cols);
    const spacingX = width / (cols + 1);
    const spacingY = height / (rows + 1);

    const batteryData = state.batteries.map((b, i) => ({
      ...b,
      x: spacingX * ((i % cols) + 1),
      y: spacingY * (Math.floor(i / cols) + 1),
    }));

    // Draw connection lines between neighboring batteries
    const lines = [];
    batteryData.forEach((b, i) => {
      // Connect to right neighbor
      if ((i + 1) % cols !== 0 && i + 1 < batteryData.length) {
        lines.push({ source: b, target: batteryData[i + 1] });
      }
      // Connect to bottom neighbor
      if (i + cols < batteryData.length) {
        lines.push({ source: b, target: batteryData[i + cols] });
      }
    });

    // --- Lines ---
    const lineSelection = svg.selectAll('.grid-line').data(lines, (d, i) => i);

    lineSelection.enter()
      .append('line')
      .attr('class', 'grid-line')
      .merge(lineSelection)
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y)
      .attr('stroke', d => {
        if (d.source.status === 'offline' || d.target.status === 'offline') return 'rgba(255,68,68,0.1)';
        return 'rgba(0,255,136,0.15)';
      })
      .attr('stroke-width', 1);

    lineSelection.exit().remove();

    // --- Battery nodes ---
    const getColor = (b) => {
      if (b.status === 'offline') return '#ff4444';
      if (b.target === 'utility') return '#4488ff';
      if (b.target === 'market') return '#00ff88';
      if (b.status === 'charging') return '#ffaa00';
      return 'rgba(0,255,136,0.3)'; // idle
    };

    const getRadius = (b) => {
      if (b.status === 'offline') return 8;
      return 12 + (b.soc * 16); // bigger when more charged
    };

    const getGlow = (b) => {
      if (b.status === 'offline') return 0;
      if (b.status === 'discharging') return 0.8;
      return 0.2;
    };

    // Glow filter
    if (svg.select('defs').empty()) {
      const defs = svg.append('defs');
      const filter = defs.append('filter').attr('id', 'glow');
      filter.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'blur');
      filter.append('feMerge')
        .selectAll('feMergeNode')
        .data(['blur', 'SourceGraphic'])
        .enter()
        .append('feMergeNode')
        .attr('in', d => d);
    }

    // Node circles
    const nodeSelection = svg.selectAll('.battery-node').data(batteryData, d => d.id);

    const nodeEnter = nodeSelection.enter()
      .append('circle')
      .attr('class', 'battery-node')
      .attr('filter', 'url(#glow)')
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        setSelectedBattery(d.id);
      })
      .on('mouseenter', (event, d) => {
        const tooltip = tooltipRef.current;
        if (tooltip) {
          tooltip.style.display = 'block';
          tooltip.style.left = (event.clientX + 15) + 'px';
          tooltip.style.top = (event.clientY - 10) + 'px';
          tooltip.innerHTML = `
            <div class="tip-row"><span class="tip-label">ID</span><span>${d.id}</span></div>
            <div class="tip-row"><span class="tip-label">SOC</span><span>${(d.soc * 100).toFixed(1)}%</span></div>
            <div class="tip-row"><span class="tip-label">Status</span><span>${d.status}</span></div>
            <div class="tip-row"><span class="tip-label">Target</span><span>${d.target || '—'}</span></div>
          `;
        }
      })
      .on('mouseleave', () => {
        if (tooltipRef.current) tooltipRef.current.style.display = 'none';
      });

    nodeEnter.merge(nodeSelection)
      .transition()
      .duration(300)
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)
      .attr('r', d => getRadius(d))
      .attr('fill', d => getColor(d))
      .attr('opacity', d => 0.3 + getGlow(d))
      .attr('stroke', d => d.id === selectedBattery ? '#fff' : 'none')
      .attr('stroke-width', 2);

    nodeSelection.exit().remove();

    // SOC text labels
    const labelSelection = svg.selectAll('.battery-label').data(batteryData, d => d.id);

    labelSelection.enter()
      .append('text')
      .attr('class', 'battery-label')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .attr('font-family', 'Courier New')
      .attr('pointer-events', 'none')
      .merge(labelSelection)
      .attr('x', d => d.x)
      .attr('y', d => d.y)
      .attr('fill', d => d.status === 'offline' ? '#ff4444' : '#fff')
      .text(d => d.status === 'offline' ? '✕' : `${Math.round(d.soc * 100)}%`);

    labelSelection.exit().remove();

  }, [state, selectedBattery]);

  // --- Chaos actions ---
  const killSelected = useCallback(() => {
    if (selectedBattery !== null) {
      fetch(`${API}/kill/${selectedBattery}`, { method: 'POST' });
    }
  }, [selectedBattery]);

  const reviveSelected = useCallback(() => {
    if (selectedBattery !== null) {
      fetch(`${API}/revive/${selectedBattery}`, { method: 'POST' });
    }
  }, [selectedBattery]);

  const priceSpike = () => fetch(`${API}/price-spike`, { method: 'POST' });
  const priceNormal = () => fetch(`${API}/price-normal`, { method: 'POST' });
  const heatwave = () => fetch(`${API}/heatwave`, { method: 'POST' });
  const heatwaveOff = () => fetch(`${API}/heatwave-off`, { method: 'POST' });

  if (!state) {
    return <div className="app" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
      <span>Connecting to simulation...</span>
    </div>;
  }

  return (
    <div className="app">
      {/* Top Stats */}
      <div className="stats-bar">
        <div className="stat">
          <span className="stat-label">ERCOT Price</span>
          <span className={`stat-value ${state.ercot_price > 0.5 ? 'danger' : state.ercot_price > 0.1 ? 'warning' : ''}`}>
            ${state.ercot_price.toFixed(2)}/kWh
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Utility Stress</span>
          <span className={`stat-value ${state.utility_stress > 0.7 ? 'danger' : state.utility_stress > 0.4 ? 'warning' : ''}`}>
            {(state.utility_stress * 100).toFixed(0)}%
          </span>
        </div>
        <div className="stat">
          <span className="stat-label">Fleet SOC</span>
          <span className="stat-value">{(state.fleet_soc * 100).toFixed(1)}%</span>
        </div>
        <div className="stat">
          <span className="stat-label">Active Nodes</span>
          <span className={`stat-value ${state.active_nodes < state.total_nodes ? 'danger' : ''}`}>
            {state.active_nodes}/{state.total_nodes}
          </span>
        </div>
      </div>

      {/* Event Banner */}
      <div className="banner-area">
        {state.ercot_price > 0.5 && (
          <div className="banner">⚡ PRICE SPIKE — ${state.ercot_price.toFixed(2)}/kWh — Fleet selling to market</div>
        )}
        {state.ercot_price > 0.1 && state.ercot_price <= 0.5 && (
          <div className="banner">📈 ELEVATED PRICING — ${state.ercot_price.toFixed(2)}/kWh — Profitable to discharge</div>
        )}
        {state.utility_stress > 0.7 && (
          <div className="banner">🔥 HEATWAVE — Utility stress {(state.utility_stress * 100).toFixed(0)}% — CoServe requesting fleet support</div>
        )}
        {state.active_nodes < state.total_nodes && (
          <div className="banner">💀 {state.total_nodes - state.active_nodes} NODE{state.total_nodes - state.active_nodes > 1 ? 'S' : ''} OFFLINE — Fleet redistributing load</div>
        )}
        {state.ercot_price <= 0.1 && state.utility_stress <= 0.7 && state.active_nodes === state.total_nodes && (
          <div className="banner">🟢 NORMAL OPERATIONS — Grid stable, fleet idle</div>
        )}
      </div>

      {/* Grid Visualization */}
      <div className="grid-container">
        <svg ref={svgRef} />
        <div className="tooltip" ref={tooltipRef} style={{ display: 'none' }} />
      </div>

      {/* Chaos Controls */}
      <div className="controls">
        <button className="danger" onClick={killSelected} disabled={selectedBattery === null}>
          Kill Node {selectedBattery !== null ? `#${selectedBattery}` : ''}
        </button>
        <button onClick={reviveSelected} disabled={selectedBattery === null}>
          Revive Node {selectedBattery !== null ? `#${selectedBattery}` : ''}
        </button>
        <button className="warning" onClick={priceSpike}>Price Spike</button>
        <button onClick={priceNormal}>Price Normal</button>
        <button className="danger" onClick={heatwave}>Heatwave</button>
        <button onClick={heatwaveOff}>Heatwave Off</button>
      </div>

      {/* Financial Ticker */}
      <div className="ticker">
        <span style={{ color: '#00ff88' }}>MARKET REVENUE: ${state.market_revenue?.toFixed(2) || '0.00'}</span>
        <span className="separator">|</span>
        <span style={{ color: '#4488ff' }}>UTILITY REVENUE: ${state.utility_revenue?.toFixed(2) || '0.00'}</span>
        <span className="separator">|</span>
        <span style={{ color: '#fff', fontWeight: 'bold' }}>TOTAL: ${state.total_revenue?.toFixed(2) || '0.00'}</span>
        <span className="separator">|</span>
        <span style={{ color: '#00ff88' }}>● {state.market_count || 0} MARKET</span>
        <span style={{ color: '#4488ff' }}>● {state.utility_count || 0} UTILITY</span>
        <span style={{ color: 'rgba(0,255,136,0.3)' }}>● {state.idle_count || 0} IDLE</span>
        <span style={{ color: '#ff4444' }}>● {state.total_nodes - state.active_nodes} OFFLINE</span>
      </div>
    </div>
  );
}

export default App;
