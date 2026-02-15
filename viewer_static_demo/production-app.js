let state = {
  availableGames: [],
  currentGame: null,
  currentGameData: {},
  rounds: {},
  status: null,
  charts: {},
};

const NUCLEAR_POSTURE_SCORES = {
  'peacetime': 0, 'elevated': 2, 'dispersal': 4, 'launch_ready': 6,
};

async function discoverGames() {
  try {
    console.log('🔍 Discovering games...');
    const knownGames = [
      'game_20260214_175118', 'game_20260214_175116', 'game_20260213_205400',
      'game_20260214_175117', 'game_20260213_220004',
    ];

    const games = [];
    for (const gameName of knownGames) {
      try {
        const url = `./demo_data/${gameName}/round_001.json`;
        const response = await fetch(url);
        if (response.ok) {
          let roundCount = 1;
          for (let i = 2; i <= 40; i++) {
            const padded = String(i).padStart(3, '0');
            const r = await fetch(`./demo_data/${gameName}/round_${padded}.json`);
            if (r.ok) roundCount = i;
            else break;
          }
          games.push({
            name: gameName, round_count: roundCount,
            rounds: Array.from({length: roundCount}, (_, i) => `round_${String(i+1).padStart(3, '0')}.json`),
          });
        }
      } catch (e) {
        console.error(`Error checking ${gameName}:`, e);
      }
    }
    console.log(`✅ Found ${games.length} games`);
    state.availableGames = games;
    return games;
  } catch (err) {
    console.error('Discovery error:', err);
    return [];
  }
}

async function loadGameData(gameName) {
  state.currentGame = gameName;
  state.rounds = {};

  const game = state.availableGames.find(g => g.name === gameName);
  if (!game) return;

  const promises = game.rounds.map(async (roundFile) => {
    const roundNum = parseInt(roundFile.match(/\d+/)[0]);
    try {
      const response = await fetch(`./demo_data/${gameName}/${roundFile}`);
      if (response.ok) {
        const data = await response.json();
        state.rounds[roundNum] = data;
      }
    } catch (err) {
      console.error(`Failed to load ${roundFile}:`, err);
    }
  });
  await Promise.all(promises);
  console.log(`Loaded ${Object.keys(state.rounds).length} rounds`);
}

function getChartOilPrice() {
  const data = [];
  for (const num of Object.keys(state.rounds).sort((a, b) => parseInt(a) - parseInt(b))) {
    const ws = state.rounds[num].world_state_after || {};
    const markets = ws.markets || {};
    data.push({
      round: parseInt(num),
      game_time: ws.game_time || `Round ${num}`,
      oil_price: markets.oil_price || 0,
    });
  }
  return data;
}

function getChartNuclear() {
  const data = [];
  for (const num of Object.keys(state.rounds).sort((a, b) => parseInt(a) - parseInt(b))) {
    const ws = state.rounds[num].world_state_after || {};
    const np_map = ws.nuclear_posture || {};
    const entry = { round: parseInt(num), game_time: ws.game_time || '' };
    for (const [country, posture] of Object.entries(np_map)) {
      entry[country] = NUCLEAR_POSTURE_SCORES[posture] || 0;
    }
    data.push(entry);
  }
  return data;
}

function getChartWarSupport() {
  const countriesData = {};
  for (const num of Object.keys(state.rounds).sort((a, b) => parseInt(a) - parseInt(b))) {
    const ws = state.rounds[num].world_state_after || {};
    const publicOpinion = ws.public_opinion || {};
    for (const [countryCode, opinion] of Object.entries(publicOpinion)) {
      if (!countriesData[countryCode]) countriesData[countryCode] = [];
      countriesData[countryCode].push({
        round: parseInt(num), war_support: opinion.war_support || 0,
      });
    }
  }
  return countriesData;
}

function getChartMilitary() {
  const data = [];
  for (const num of Object.keys(state.rounds).sort((a, b) => parseInt(a) - parseInt(b))) {
    const ws = state.rounds[num].world_state_after || {};
    const units = ws.military_units || [];
    let natoStrength = 0, ruByStrength = 0;
    for (const unit of units) {
      if (typeof unit === 'object' && unit !== null) {
        const strength = unit.strength || 0;
        const country = unit.country || '';
        if (['PL', 'US', 'GB', 'FR', 'DE', 'FI', 'SE', 'NO'].includes(country)) natoStrength += strength;
        else if (['RU', 'BY'].includes(country)) ruByStrength += strength;
      }
    }
    data.push({
      round: parseInt(num), game_time: ws.game_time || '',
      nato_strength: natoStrength, ru_by_strength: ruByStrength,
    });
  }
  return data;
}

async function renderCharts() {
  try {
    const oilData = getChartOilPrice();
    await renderOilChart(oilData);
    const nuclearData = getChartNuclear();
    await renderNuclearChart(nuclearData);
    const warData = getChartWarSupport();
    await renderWarSupportChart(warData);
    const militaryData = getChartMilitary();
    await renderMilitaryChart(militaryData);
  } catch (err) {
    console.error('Chart error:', err);
  }
}

async function renderOilChart(data) {
  const ctx = document.getElementById('chart-oil');
  if (!ctx) return;
  if (state.charts.oil) state.charts.oil.destroy();
  state.charts.oil = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: {
      labels: data.map(d => d.game_time),
      datasets: [{
        label: 'Oil Price', data: data.map(d => d.oil_price),
        borderColor: '#f59e0b', backgroundColor: 'rgba(245,158,11,0.1)',
        fill: true, tension: 0.3, pointRadius: 4,
      }],
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } } },
  });
}

async function renderNuclearChart(data) {
  const ctx = document.getElementById('chart-nuclear');
  if (!ctx) return;
  if (state.charts.nuclear) state.charts.nuclear.destroy();
  const countries = ['RU', 'US', 'GB', 'FR'];
  const colors = { RU: '#ef4444', US: '#10b981', GB: '#8b5cf6', FR: '#3b82f6' };
  const datasets = countries
    .filter(c => data[0] && data[0][c] !== undefined)
    .map(c => ({
      label: c, data: data.map(d => d[c] || 0),
      borderColor: colors[c], tension: 0.3,
    }));
  state.charts.nuclear = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: { labels: data.map(d => d.game_time), datasets },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } } },
  });
}

async function renderWarSupportChart(data) {
  const ctx = document.getElementById('chart-warSupport');
  if (!ctx) return;
  if (state.charts.warSupport) state.charts.warSupport.destroy();
  const countries = Object.keys(data).slice(0, 8);
  const colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];
  const datasets = countries.map((country, idx) => ({
    label: country, data: data[country].map(d => d.war_support),
    borderColor: colors[idx], tension: 0.3,
  }));
  state.charts.warSupport = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: { labels: Array.from({length: data[countries[0]]?.length || 0}, (_, i) => `R${i + 1}`), datasets },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } } },
  });
}

async function renderMilitaryChart(data) {
  const ctx = document.getElementById('chart-military');
  if (!ctx) return;
  if (state.charts.military) state.charts.military.destroy();
  state.charts.military = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: {
      labels: data.map(d => d.game_time),
      datasets: [
        { label: 'NATO', data: data.map(d => d.nato_strength), borderColor: '#10b981', tension: 0.3 },
        { label: 'RU/BY', data: data.map(d => d.ru_by_strength), borderColor: '#ef4444', tension: 0.3 },
      ],
    },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: true } } },
  });
}

function switchView(viewName) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const view = document.getElementById(`view-${viewName}`);
  if (view) view.classList.add('active');
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.remove('active');
    if (item.dataset.view === viewName) item.classList.add('active');
  });
}

async function renderDashboardStats() {
  if (Object.keys(state.rounds).length === 0) return;
  const lastRound = Math.max(...Object.keys(state.rounds).map(Number));
  const ws = state.rounds[lastRound].world_state_after || {};
  let html = '';
  html += `<div class="stat-card"><div class="stat-label">Oil Price</div><div class="stat-value">$${Math.round(ws.markets?.oil_price || 0)}</div></div>`;
  html += `<div class="stat-card"><div class="stat-label">Round</div><div class="stat-value">${lastRound}</div></div>`;
  html += `<div class="stat-card"><div class="stat-label">Corridor</div><div class="stat-value">${(ws.corridor_control || 'CONTESTED').toUpperCase()}</div></div>`;
  html += `<div class="stat-card"><div class="stat-label">NATO Alert</div><div class="stat-value">${(ws.nato_alert_level || 'NORMAL').toUpperCase()}</div></div>`;
  const dashboardStats = document.getElementById('dashboard-stats');
  if (dashboardStats) dashboardStats.innerHTML = html;
}

async function renderRoundsView() {
  const roundNav = document.getElementById('round-nav');
  if (!roundNav) return;
  let html = '';
  for (const num of Object.keys(state.rounds).sort((a, b) => Number(a) - Number(b))) {
    html += `<button class="round-btn" onclick="loadRound(${num})">R${num}</button>`;
  }
  roundNav.innerHTML = html;
  if (Object.keys(state.rounds).length > 0) {
    const firstRound = Object.keys(state.rounds).sort((a, b) => Number(a) - Number(b))[0];
    loadRound(parseInt(firstRound));
  }
}

async function loadRound(num) {
  const round = state.rounds[num];
  if (!round) return;
  document.querySelectorAll('#round-nav .round-btn').forEach(b => {
    b.classList.remove('active');
    if (parseInt(b.textContent.replace('R', '')) === num) b.classList.add('active');
  });

  const ws = round.world_state_after || {};
  const countries = round.country_decisions || [];
  const resolution = round.resolution || {};
  
  let html = `<h2>Round ${num}</h2>`;
  html += `<div class="card"><div class="card-title">Briefing</div><p style="font-size:13px;color:var(--text-secondary);margin-top:8px;white-space:pre-wrap;">${(round.briefing || '').substring(0, 800)}</p></div>`;
  
  html += `<div class="card"><div class="card-title">Country Decisions (${countries.length})</div>`;
  for (const cd of countries) {
    html += `<div class="collapsible"><div class="collapsible-header" onclick="this.parentElement.classList.toggle('open')"><strong>${cd.country}</strong> <span class="collapsible-arrow">›</span></div>`;
    html += `<div class="collapsible-body">`;
    if (cd.actions) {
      html += `<strong>Actions:</strong><ul style="margin:8px 0;padding-left:20px;">`;
      for (const action of cd.actions) html += `<li style="margin:4px 0;">${action}</li>`;
      html += `</ul>`;
    }
    if (cd.diplomatic_messages && cd.diplomatic_messages.length > 0) {
      html += `<strong>Diplomatic Messages:</strong><div style="margin:8px 0;">`;
      for (const msg of cd.diplomatic_messages) {
        html += `<div class="diplo-msg"><strong>${msg.to}:</strong> ${msg.message}</div>`;
      }
      html += `</div>`;
    }
    html += `</div></div>`;
  }
  html += `</div>`;
  
  if (resolution.combat_results) {
    html += `<div class="card"><div class="card-title">Combat Results</div><p style="font-size:12px;white-space:pre-wrap;">${resolution.combat_results}</p></div>`;
  }
  if (resolution.headlines && resolution.headlines.length > 0) {
    html += `<div class="card"><div class="card-title">Headlines</div>`;
    for (const headline of resolution.headlines) {
      html += `<div class="headline-item">${headline}</div>`;
    }
    html += `</div>`;
  }

  const detail = document.getElementById('round-detail');
  if (detail) detail.innerHTML = html;
}

async function renderCountriesView() {
  const countriesList = document.getElementById('countries-list');
  if (!countriesList) return;
  if (Object.keys(state.rounds).length === 0) {
    countriesList.innerHTML = '<div class="loading">No data loaded</div>';
    return;
  }

  const lastRound = Math.max(...Object.keys(state.rounds).map(Number));
  const ws = state.rounds[lastRound].world_state_after || {};
  const publicOpinion = ws.public_opinion || {};

  let html = '<div class="country-grid">';
  for (const [code, opinion] of Object.entries(publicOpinion).slice(0, 15)) {
    html += `<div class="country-card"><div class="country-code">${code}</div>`;
    html += `<div style="font-size:12px;margin-top:8px;">`;
    html += `<p><strong>War Support:</strong> ${Math.round(opinion.war_support || 0)}%</p>`;
    html += `<p><strong>Gov Approval:</strong> ${Math.round(opinion.gov_approval || 0)}%</p>`;
    html += `<p><strong>Morale:</strong> ${Math.round(opinion.morale || 0)}%</p>`;
    html += `</div></div>`;
  }
  html += '</div>';
  countriesList.innerHTML = html;
}

async function renderWorldStateView() {
  const wsRoundNav = document.getElementById('ws-round-nav');
  if (!wsRoundNav) return;
  let html = '';
  for (const num of Object.keys(state.rounds).sort((a, b) => Number(a) - Number(b))) {
    html += `<button class="round-btn" onclick="loadWorldState(${num})">R${num}</button>`;
  }
  wsRoundNav.innerHTML = html;
  if (Object.keys(state.rounds).length > 0) {
    const firstRound = Object.keys(state.rounds).sort((a, b) => Number(a) - Number(b))[0];
    loadWorldState(parseInt(firstRound));
  }
}

async function loadWorldState(num) {
  const round = state.rounds[num];
  if (!round) return;
  document.querySelectorAll('#ws-round-nav .round-btn').forEach(b => {
    b.classList.remove('active');
    if (parseInt(b.textContent.replace('R', '')) === num) b.classList.add('active');
  });

  const ws = round.world_state_after || {};
  const wsMetrics = document.getElementById('ws-metrics');
  if (wsMetrics) {
    let html = '';
    html += `<div class="metric-item"><div class="metric-label">Corridor</div><div class="metric-value">${ws.corridor_control || '—'}</div></div>`;
    html += `<div class="metric-item"><div class="metric-label">NATO Alert</div><div class="metric-value">${ws.nato_alert_level || '—'}</div></div>`;
    html += `<div class="metric-item"><div class="metric-label">Oil Price</div><div class="metric-value">$${ws.markets?.oil_price || '—'}</div></div>`;
    html += `<div class="metric-item"><div class="metric-label">Military Units</div><div class="metric-value">${(ws.military_units || []).length}</div></div>`;
    html += `<div class="metric-item"><div class="metric-label">Nuclear Status</div><div class="metric-value">${Math.max(...Object.values(ws.nuclear_posture || {})) || 'PEACETIME'}</div></div>`;
    wsMetrics.innerHTML = html;
  }

  const wsJson = document.getElementById('ws-json');
  if (wsJson) {
    wsJson.textContent = JSON.stringify(ws, null, 2);
  }
}

async function init() {
  try {
    const gameSelect = document.getElementById('gameSelect');
    if (!gameSelect) return;
    
    gameSelect.innerHTML = '<option>Discovering...</option>';
    const games = await discoverGames();
    
    gameSelect.innerHTML = '<option value="">-- Select a game --</option>';
    games.forEach(game => {
      const option = document.createElement('option');
      option.value = game.name;
      option.textContent = `${game.name} (${game.round_count} rounds)`;
      gameSelect.appendChild(option);
    });
    
    if (games.length > 0) {
      gameSelect.value = games[0].name;
      await loadGameData(games[0].name);
      await renderCharts();
      await renderDashboardStats();
      await renderRoundsView();
      await renderCountriesView();
      await renderWorldStateView();
    }
    
    gameSelect.addEventListener('change', async (e) => {
      if (e.target.value) {
        await loadGameData(e.target.value);
        await renderCharts();
        await renderDashboardStats();
        await renderRoundsView();
        await renderCountriesView();
        await renderWorldStateView();
      }
    });

    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        const view = e.currentTarget.dataset.view;
        if (view) switchView(view);
      });
    });
  } catch (err) {
    console.error('Init error:', err);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
