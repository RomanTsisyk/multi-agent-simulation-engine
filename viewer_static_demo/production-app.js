let state = {
  availableGames: [],
  currentGame: null,
  currentGameData: {},
  rounds: {},
  status: null,
  charts: {},
};

const NUCLEAR_POSTURE_SCORES = {
  'peacetime': 0,
  'elevated': 2,
  'dispersal': 4,
  'launch_ready': 6,
};

async function discoverGames() {
  try {
    console.log('🔍 Starting game discovery...');
    const knownGames = [
      'game_20260214_175118',
      'game_20260214_175116',
      'game_20260213_205400',
      'game_20260214_175117',
      'game_20260213_220004',
    ];

    const games = [];
    for (const gameName of knownGames) {
      try {
        const url = `/logs/${gameName}/round_001.json`;
        console.log(`  Checking: ${gameName}`);
        const response = await fetch(url);
        console.log(`  Response: ${response.status}`);

        if (response.ok) {
          let roundCount = 1;
          for (let i = 2; i <= 40; i++) {
            const padded = String(i).padStart(3, '0');
            const r = await fetch(`/logs/${gameName}/round_${padded}.json`);
            if (r.ok) roundCount = i;
            else break;
          }

          console.log(`  Found: ${gameName} (${roundCount} rounds)`);
          games.push({
            name: gameName,
            round_count: roundCount,
            rounds: Array.from({length: roundCount}, (_, i) => `round_${String(i+1).padStart(3, '0')}.json`),
            has_summary: false,
          });
        }
      } catch (e) {
        console.error(`  Error: ${e.message}`);
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
  state.currentGameData = {};
  state.rounds = {};

  const game = state.availableGames.find(g => g.name === gameName);
  if (!game) {
    console.error('Game not found:', gameName);
    return;
  }

  const promises = game.rounds.map(async (roundFile) => {
    const roundNum = parseInt(roundFile.match(/\d+/)[0]);
    try {
      const response = await fetch(`/logs/${gameName}/${roundFile}`);
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
      euro_usd: markets.euro_usd || 0,
    });
  }
  return data;
}

function getChartNuclear() {
  const data = [];
  for (const num of Object.keys(state.rounds).sort((a, b) => parseInt(a) - parseInt(b))) {
    const ws = state.rounds[num].world_state_after || {};
    const np_map = ws.nuclear_posture || {};
    const entry = {
      round: parseInt(num),
      game_time: ws.game_time || '',
    };
    for (const [country, posture] of Object.entries(np_map)) {
      entry[country] = NUCLEAR_POSTURE_SCORES[posture] || 0;
      entry[`${country}_label`] = posture;
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
      if (!countriesData[countryCode]) {
        countriesData[countryCode] = [];
      }
      countriesData[countryCode].push({
        round: parseInt(num),
        war_support: opinion.war_support || 0,
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
    
    let natoStrength = 0;
    let ruByStrength = 0;
    
    for (const unit of units) {
      if (typeof unit === 'object' && unit !== null) {
        const strength = unit.strength || 0;
        const country = unit.country || unit.nation || '';
        
        if (['PL', 'US', 'GB', 'FR', 'DE', 'FI', 'SE', 'NO'].includes(country)) {
          natoStrength += strength;
        } else if (['RU', 'BY'].includes(country)) {
          ruByStrength += strength;
        }
      }
    }
    
    data.push({
      round: parseInt(num),
      game_time: ws.game_time || '',
      nato_strength: natoStrength,
      ru_by_strength: ruByStrength,
      balance: natoStrength - ruByStrength,
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
    
    console.log('✅ Charts rendered');
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
        label: 'Oil Price',
        data: data.map(d => d.oil_price),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true } },
      scales: { y: { beginAtZero: false } },
    },
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
      label: c,
      data: data.map(d => d[c] || 0),
      borderColor: colors[c],
      tension: 0.3,
    }));
  
  state.charts.nuclear = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: {
      labels: data.map(d => d.game_time),
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true } },
      scales: { y: { min: 0, max: 6 } },
    },
  });
}

async function renderWarSupportChart(data) {
  const ctx = document.getElementById('chart-warSupport');
  if (!ctx) return;
  
  if (state.charts.warSupport) state.charts.warSupport.destroy();
  
  const countries = Object.keys(data).slice(0, 8);
  const colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];
  
  const datasets = countries.map((country, idx) => ({
    label: country,
    data: data[country].map(d => d.war_support),
    borderColor: colors[idx],
    tension: 0.3,
  }));
  
  state.charts.warSupport = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: {
      labels: Array.from({length: data[countries[0]]?.length || 0}, (_, i) => `R${i + 1}`),
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true } },
      scales: { y: { min: 0, max: 100 } },
    },
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
        {
          label: 'NATO',
          data: data.map(d => d.nato_strength),
          borderColor: '#10b981',
          tension: 0.3,
        },
        {
          label: 'RU/BY',
          data: data.map(d => d.ru_by_strength),
          borderColor: '#ef4444',
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: true } },
      scales: { y: { beginAtZero: true } },
    },
  });
}

async function init() {
  try {
    console.log('🚀 Init started');
    
    const gameSelect = document.getElementById('gameSelect');
    if (!gameSelect) {
      console.error('gameSelect not found');
      return;
    }
    
    gameSelect.innerHTML = '<option>Loading games...</option>';
    const status = document.getElementById('status');
    if (status) status.textContent = 'Discovering games...';
    
    console.log('🎮 Discovering games');
    const games = await discoverGames();
    console.log(`Found ${games.length} games`);
    
    gameSelect.innerHTML = '<option value="">Select game</option>';
    games.forEach(game => {
      const option = document.createElement('option');
      option.value = game.name;
      option.textContent = `${game.name} (${game.round_count} rounds)`;
      gameSelect.appendChild(option);
    });
    
    if (games.length > 0) {
      gameSelect.value = games[0].name;
      if (status) status.textContent = 'Loading data...';
      await loadGameData(games[0].name);
      if (status) status.textContent = 'Rendering charts...';
      await renderCharts();
      if (status) status.textContent = 'Ready';
    }
    
    gameSelect.addEventListener('change', async (e) => {
      if (e.target.value) {
        if (status) status.textContent = 'Loading...';
        await loadGameData(e.target.value);
        await renderCharts();
        if (status) status.textContent = 'Ready';
      }
    });
    
    console.log('✅ Init complete');
  } catch (err) {
    console.error('Init error:', err);
    const gameSelect = document.getElementById('gameSelect');
    if (gameSelect) gameSelect.innerHTML = '<option>Error: ' + err.message + '</option>';
  }
}

if (document.readyState === 'loading') {
  console.log('DOM loading...');
  document.addEventListener('DOMContentLoaded', init);
} else {
  console.log('DOM ready, init now');
  init();
}
