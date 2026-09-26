import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import './App.css';

const API = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

// --- Price Chart Component ---
function PriceChart({ priceHistory }) {
  const chartRef = useRef(null);

  useEffect(() => {
    if (!priceHistory || priceHistory.length < 2 || !chartRef.current) return;

    const svg = d3.select(chartRef.current);
    svg.selectAll('*').remove();

    const width = chartRef.current.clientWidth;
    const height = chartRef.current.clientHeight;
    const margin = { top: 10, right: 50, bottom: 25, left: 60 };
    const w = width - margin.left - margin.right;
    const h = height - margin.top - margin.bottom;

    const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

    const prices = priceHistory.map((d, i) => ({ ...d, index: i }));
    const xScale = d3.scaleLinear().domain([0, prices.length - 1]).range([0, w]);
    const yScale = d3.scaleLinear()
      .domain([0, Math.max(0.1, d3.max(prices, d => d.price) * 1.1)])
      .range([h, 0]);

    // Grid lines
    g.append('g')
      .attr('class', 'grid')
      .selectAll('line')
      .data(yScale.ticks(5))
      .enter()
      .append('line')
      .attr('x1', 0).attr('x2', w)
      .attr('y1', d => yScale(d)).attr('y2', d => yScale(d))
      .attr('stroke', 'rgba(0,255,136,0.1)');

    // Price line
    const line = d3.line()
      .x(d => xScale(d.index))
      .y(d => yScale(d.price))
      .curve(d3.curveMonotoneX);

    // Area fill under the line
    const area = d3.area()
      .x(d => xScale(d.index))
      .y0(h)
      .y1(d => yScale(d.price))
      .curve(d3.curveMonotoneX);

    g.append('path')
      .datum(prices)
      .attr('d', area)
      .attr('fill', 'rgba(0,255,136,0.05)');

    g.append('path')
      .datum(prices)
      .attr('d', line)
      .attr('fill', 'none')
      .attr('stroke', '#00ff88')
      .attr('stroke-width', 2);

    // Current price dot
    const last = prices[prices.length - 1];
    g.append('circle')
      .attr('cx', xScale(last.index))
      .attr('cy', yScale(last.price))
      .attr('r', 4)
      .attr('fill', '#00ff88');

    // Current price label
    g.append('text')
      .attr('x', w + 5)
      .attr('y', yScale(last.price) + 4)
      .attr('fill', '#00ff88')
      .attr('font-size', '12px')
      .attr('font-family', 'Courier New')
      .text(`$${last.price.toFixed(2)}`);

    // Y axis
    g.append('g')
      .selectAll('text')
      .data(yScale.ticks(5))
      .enter()
      .append('text')
      .attr('x', -5)
      .attr('y', d => yScale(d) + 4)
      .attr('text-anchor', 'end')
      .attr('fill', 'rgba(0,255,136,0.5)')
      .attr('font-size', '10px')
      .attr('font-family', 'Courier New')
      .text(d => `$${d.toFixed(2)}`);

    // Bottom label
    g.append('text')
      .attr('x', w / 2)
      .attr('y', h + 20)
      .attr('text-anchor', 'middle')
      .attr('fill', 'rgba(0,255,136,0.4)')
      .attr('font-size', '10px')
      .attr('font-family', 'Courier New')
      .text('ERCOT PRICE — LAST 2 MIN');

  }, [priceHistory]);

  return <svg ref={chartRef} style={{ width: '100%', height: '100%' }} />;
}


// --- Order Book Component ---
function OrderBook({ orderBook, recentTrades }) {
  if (!orderBook) return null;

  const bids = (orderBook.bids || []).sort((a, b) => b.price - a.price);
  const asks = (orderBook.asks || []).sort((a, b) => a.price - b.price);

  return (
    <div className="order-book">
      <div className="ob-section">
        <div className="ob-header">BIDS (BUYING POWER)</div>
        {bids.map((b, i) => (
          <div key={i} className="ob-row bid">
            <span className="ob-source">{b.source}</span>
            <span className="ob-price">${b.price.toFixed(2)}</span>
            <span className="ob-kw">{b.kw === 999 ? '∞' : b.kw.toFixed(1)} kW</span>
          </div>
        ))}
      </div>

      <div className="ob-spread">
        SPREAD: ${Math.abs((asks[0]?.price || 0) - (bids[0]?.price || 0)).toFixed(2)}
      </div>

      <div className="ob-section">
        <div className="ob-header">ASKS (SELLING POWER)</div>
        {asks.map((a, i) => (
          <div key={i} className="ob-row ask">
            <span className="ob-source">{a.source}</span>
            <span className="ob-price">${a.price.toFixed(2)}</span>
            <span className="ob-kw">{a.kw.toFixed(1)} kW</span>
          </div>
        ))}
      </div>

      {recentTrades && recentTrades.length > 0 && (
        <div className="ob-section">
          <div className="ob-header">RECENT TRADES</div>
          {recentTrades.slice(-5).reverse().map((t, i) => (
            <div key={i} className="ob-row trade">
              <span className={t.side === 'sell' ? 'ob-sell' : 'ob-buy'}>
                {t.side.toUpperCase()}
              </span>
              <span className="ob-price">${t.filled_price?.toFixed(2)}</span>
              <span className="ob-kw">{t.kw.toFixed(1)} kW</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// --- Limit Order Form ---
function OrderForm() {
  const [side, setSide] = useState('sell');
  const [price, setPrice] = useState('');
  const [kw, setKw] = useState('');

  const placeOrder = async () => {
    if (!price || !kw) return;
    await fetch(`${API}/order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ side, price: parseFloat(price), kw: parseFloat(kw) }),
    });
    setPrice('');
    setKw('');
  };

  return (
    <div className="order-form">
      <div className="of-title">PLACE LIMIT ORDER</div>
      <div className="of-row">
        <button
          className={`of-side ${side === 'sell' ? 'active-sell' : ''}`}
          onClick={() => setSide('sell')}
        >SELL</button>
        <button
          className={`of-side ${side === 'buy' ? 'active-buy' : ''}`}
          onClick={() => setSide('buy')}
        >BUY</button>
      </div>
      <div className="of-row">
        <input
          type="number"
          placeholder="Price $/kWh"
          value={price}
          onChange={e => setPrice(e.target.value)}
          step="0.01"
        />
        <input
          type="number"
          placeholder="kW"
          value={kw}
          onChange={e => setKw(e.target.value)}
          step="1"
        />
      </div>
      <button className="of-submit" onClick={placeOrder}>
        {side === 'sell' ? '⚡ SELL POWER' : '🔋 BUY POWER'}
      </button>
    </div>
  );
}


// --- Main App ---
function App() {
  const svgRef = useRef(null);
  const tooltipRef = useRef(null);
  const [state, setState] = useState(null);
  const [selectedBattery, setSelectedBattery] = useState(null);
  const [view, setView] = useState('grid'); // 'grid' or 'trading'

  // WebSocket connection
  useEffect(() => {
    let ws;
    let reconnectTimeout;
    function connect() {
      ws = new WebSocket(WS_URL);
      ws.onmessage = (event) => setState(JSON.parse(event.data));
      ws.onclose = () => { reconnectTimeout = setTimeout(connect, 1000); };
    }
    connect();
    return () => { ws?.close(); clearTimeout(reconnectTimeout); };
  }, []);

  // D3 Grid Visualization
  useEffect(() => {
    if (!state || !svgRef.current || view !== 'grid') return;

    const svg = d3.select(svgRef.current);
    const width = svgRef.current.clientWidth;
    const height = svgRef.current.clientHeight;

    const cols = 5;
    const rows = Math.ceil(state.batteries.length / cols);
    const spacingX = width / (cols + 1);
    const spacingY = height / (rows + 1);

    const batteryData = state.batteries.map((b, i) => ({
      ...b,
      x: spacingX * ((i % cols) + 1),
      y: spacingY * (Math.floor(i / cols) + 1),
    }));

    const lines = [];
    batteryData.forEach((b, i) => {
      if ((i + 1) % cols !== 0 && i + 1 < batteryData.length)
        lines.push({ source: b, target: batteryData[i + 1] });
      if (i + cols < batteryData.length)
        lines.push({ source: b, target: batteryData[i + cols] });
    });

    const lineSelection = svg.selectAll('.grid-line').data(lines, (d, i) => i);
    lineSelection.enter().append('line').attr('class', 'grid-line')
      .merge(lineSelection)
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y)
      .attr('stroke', d => (d.source.status === 'offline' || d.target.status === 'offline') ? 'rgba(255,68,68,0.1)' : 'rgba(0,255,136,0.15)')
      .attr('stroke-width', 1);
    lineSelection.exit().remove();

    const getColor = (b) => {
      if (b.status === 'offline') return '#ff4444';
      if (b.target === 'utility') return '#4488ff';
      if (b.target === 'market') return '#00ff88';
      if (b.status === 'charging') return '#ffaa00';
      return 'rgba(0,255,136,0.3)';
    };

    const getRadius = (b) => b.status === 'offline' ? 8 : 12 + (b.soc * 16);
    const getGlow = (b) => b.status === 'offline' ? 0 : b.status === 'discharging' ? 0.8 : 0.2;

    if (svg.select('defs').empty()) {
      const defs = svg.append('defs');
      const filter = defs.append('filter').attr('id', 'glow');
      filter.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'blur');
      filter.append('feMerge').selectAll('feMergeNode').data(['blur', 'SourceGraphic'])
        .enter().append('feMergeNode').attr('in', d => d);
    }

    const nodeSelection = svg.selectAll('.battery-node').data(batteryData, d => d.id);
    const nodeEnter = nodeSelection.enter().append('circle')
      .attr('class', 'battery-node').attr('filter', 'url(#glow)').style('cursor', 'pointer')
      .on('click', (event, d) => setSelectedBattery(d.id))
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
      .on('mouseleave', () => { if (tooltipRef.current) tooltipRef.current.style.display = 'none'; });

    nodeEnter.merge(nodeSelection).transition().duration(300)
      .attr('cx', d => d.x).attr('cy', d => d.y)
      .attr('r', d => getRadius(d)).attr('fill', d => getColor(d))
      .attr('opacity', d => 0.3 + getGlow(d))
      .attr('stroke', d => d.id === selectedBattery ? '#fff' : 'none').attr('stroke-width', 2);
    nodeSelection.exit().remove();

    const labelSelection = svg.selectAll('.battery-label').data(batteryData, d => d.id);
    labelSelection.enter().append('text').attr('class', 'battery-label')
      .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
      .attr('font-size', '12px').attr('font-weight', 'bold')
      .attr('font-family', 'Courier New').attr('pointer-events', 'none')
      .merge(labelSelection)
      .attr('x', d => d.x).attr('y', d => d.y)
      .attr('fill', d => d.status === 'offline' ? '#ff4444' : '#fff')
      .text(d => d.status === 'offline' ? '✕' : `${Math.round(d.soc * 100)}%`);
    labelSelection.exit().remove();
  }, [state, selectedBattery, view]);

  // Chaos actions
  const killSelected = useCallback(() => {
    if (selectedBattery !== null) fetch(`${API}/kill/${selectedBattery}`, { method: 'POST' });
  }, [selectedBattery]);
  const reviveSelected = useCallback(() => {
    if (selectedBattery !== null) fetch(`${API}/revive/${selectedBattery}`, { method: 'POST' });
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
      {/* Top Stats + View Toggle */}
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
        <button className="view-toggle" onClick={() => setView(view === 'grid' ? 'trading' : 'grid')}>
          {view === 'grid' ? '📈 TRADING' : '🔋 GRID'}
        </button>
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

      {/* Main Content Area */}
      {view === 'grid' ? (
        <>
          <div className="grid-container">
            <svg ref={svgRef} />
            <div className="tooltip" ref={tooltipRef} style={{ display: 'none' }} />
          </div>

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
        </>
      ) : (
        <div className="trading-view">
          <div className="trading-left">
            <div className="chart-container">
              <PriceChart priceHistory={state.price_history} />
            </div>
            <OrderForm />
          </div>
          <div className="trading-right">
            <OrderBook orderBook={state.order_book} recentTrades={state.recent_trades} />
          </div>
        </div>
      )}

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
