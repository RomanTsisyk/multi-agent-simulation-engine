/**
 * WarGame Production Viewer - Static/Client-Side
 * Replaces FastAPI backend with pure JavaScript + JSON
 * 
 * Reads from: ../logs/game_*/round_*.json
 * No backend required - works on GitHub Pages
 */

// ============================================================
// STATE MANAGEMENT
// ============================================================

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

// ============================================================
// GAME DISCOVERY & LOADING
// ============================================================

/**
 * Discover available games by scanning logs/ directory
 * Returns list of game metadata
 */
async function discoverGames() {
  try {
    console.log('🔍 Starting game discovery...');
    // Fetch available games by trying to load metadata
    // Since we can't scan directories in browser, we'll try known patterns
    const knownGames = [
      'game_20260214_175118',
      'game_20260214_175116',
      'game_20260213_205400',
      'game_20260214_175117',
      'game_20260213_220004',
    ];

    const games = [];
    for (const gameName of knownGames) {
      // Try to load round 1 to verify game exists
      try {
        const url = `/logs/${gameName}/round_001.json`;
        console.log(`  Checking game: ${gameName} (${url})`);
        const response = await fetch(url);
        console.log(`  Response: ${response.status} ${response.statusText}`);

        if (response.ok) {
          // Count available rounds
          let roundCount = 1;
          for (let i = 2; i <= 40; i++) {
            const padded = String(i).padStart(3, '0');
            const r = await fetch(`/logs/${gameName}/round_${padded}.json`);
            if (r.ok) roundCount = i;
            else break;
          }

          console.log(`  ✅ Game found: ${gameName} with ${roundCount} rounds`);
          games.push({
            name: gameName,
            round_count: roundCount,
            rounds: Array.from({length: roundCount}, (_, i) => `round_${String(i+1).padStart(3, '0')}.json`),
            has_summary: false,
          });
        } else {
          console.log(`  ❌ Game not found: ${gameName}`);
        }
      } catch (e) {
        console.error(`  Error checking ${gameName}:`, e);
      }
    }

    console.log(`🎮 Game discovery complete: ${games.length} games found`);
    state.availableGames = games;
    return games;
  } catch (err) {
    console.error('Failed to discover games:', err);
    return [];
  }
}

/**
 * Load all rounds for a specific game
 */
async function loadGameData(gameName) {
  state.currentGame = gameName;
  state.currentGameData = {};
  state.rounds = {};

  const game = state.availableGames.find(g => g.name === gameName);
  if (!game) {
    console.error('Game not found:', gameName);
    return;
  }

  // Load all rounds in parallel
  const promises = game.rounds.map(async (roundFile) => {
    const roundNum = parseInt(roundFile.match(/\d+/)[0]);
    try {
      const response = await fetch(`../logs/${gameName}/${roundFile}`);
      if (response.ok) {
        const data = await response.json();
        state.rounds[roundNum] = data;
      }
    } catch (err) {
      console.error(`Failed to load ${roundFile}:`, err);
    }
  });

  await Promise.all(promises);
  console.log(`Loaded ${Object.keys(state.rounds).length} rounds for ${gameName}`);
}

// ============================================================
// CHART DATA PROCESSING (replaces /api/charts/*)
// ============================================================

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

// ============================================================
// RENDERING (replaces all chart rendering)
// ============================================================

async function renderCharts() {
  try {
    // Oil Price Chart
    const oilData = getChartOilPrice();
    await renderOilChart(oilData);
    
    // Nuclear Chart
    const nuclearData = getChartNuclear();
    await renderNuclearChart(nuclearData);
    
    // War Support Chart
    const warData = getChartWarSupport();
    await renderWarSupportChart(warData);
    
    // Military Chart
    const militaryData = getChartMilitary();
    await renderMilitaryChart(militaryData);
    
    console.log('✅ All charts rendered');
  } catch (err) {
    console.error('Failed to render charts:', err);
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
        label: 'Oil Price ($/barrel)',
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
      plugins: {
        legend: { display: true, position: 'top' },
      },
      scales: {
        y: { beginAtZero: false, ticks: { callback: v => '$' + v } },
      },
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
      backgroundColor: colors[c] + '20',
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
      plugins: {
        legend: { display: true, position: 'top' },
      },
      scales: {
        y: {
          min: 0,
          max: 6,
          ticks: {
            callback: v => {
              const labels = {0: 'Peacetime', 2: 'Elevated', 4: 'Dispersal', 6: 'Launch Ready'};
              return labels[v] || '';
            },
          },
        },
      },
    },
  });
}

async function renderWarSupportChart(data) {
  const ctx = document.getElementById('chart-warSupport');
  if (!ctx) return;
  
  if (state.charts.warSupport) state.charts.warSupport.destroy();
  
  const countries = Object.keys(data).slice(0, 8); // Top 8 countries
  const colors = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];
  
  const datasets = countries.map((country, idx) => ({
    label: country,
    data: data[country].map(d => d.war_support),
    borderColor: colors[idx],
    backgroundColor: colors[idx] + '20',
    tension: 0.3,
  }));
  
  // Get max round from first country
  const maxRound = data[countries[0]]?.length || 0;
  const roundLabels = Array.from({length: maxRound}, (_, i) => `R${i + 1}`);
  
  state.charts.warSupport = new Chart(ctx.getContext('2d'), {
    type: 'line',
    data: {
      labels: roundLabels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top' },
      },
      scales: {
        y: { min: 0, max: 100, ticks: { callback: v => v + '%' } },
      },
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
          label: 'NATO Strength',
          data: data.map(d => d.nato_strength),
          borderColor: '#10b981',
          backgroundColor: 'rgba(16,185,129,0.1)',
          tension: 0.3,
        },
        {
          label: 'RU/BY Strength',
          data: data.map(d => d.ru_by_strength),
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239,68,68,0.1)',
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top' },
      },
      scales: {
        y: { beginAtZero: true },
      },
    },
  });
}

// ============================================================
// INITIALIZATION
// ============================================================

async function init() {
  try {
    console.log('🚀 Initializing production viewer...');

    // 2. Populate game selector - DO THIS FIRST to show something is happening
    const gameSelect = document.getElementById('gameSelect');
    if (!gameSelect) {
      console.error('❌ gameSelect element not found!');
      return;
    }
    console.log('✅ Found gameSelect element');

    // Update to show we're loading
    gameSelect.innerHTML = '<option value="">Loading games...</option>';

    // 1. Discover games
    console.log('🎮 Discovering games...');
    const games = await discoverGames();
    console.log(`✅ Found ${games.length} games`, games);

    // Update dropdown
    gameSelect.innerHTML = '<option value="">-- Select a game --</option>';
    if (games.length === 0) {
      gameSelect.innerHTML += '<option value="">No games found</option>';
    } else {
      games.forEach(game => {
        const option = document.createElement('option');
        option.value = game.name;
        option.textContent = `${game.name} (${game.round_count} rounds)`;
        gameSelect.appendChild(option);
      });

      // Auto-select first game
      gameSelect.value = games[0].name;
      console.log('🎬 Auto-loading first game:', games[0].name);
      await loadGameData(games[0].name);
      await renderCharts();
    }

    // Listen for game selection
    gameSelect.addEventListener('change', async (e) => {
      if (e.target.value) {
        console.log('🎮 Game selected:', e.target.value);
        await loadGameData(e.target.value);
        await renderCharts();
      }
    });

    console.log('✅ Init complete!');
  } catch (err) {
    console.error('💥 Init error:', err);
    const gameSelect = document.getElementById('gameSelect');
    if (gameSelect) {
      gameSelect.innerHTML = '<option value="">Error: ' + err.message + '</option>';
    }
  }
}

// Start on page load
console.log('📄 production-app.js loaded. DOM readyState:', document.readyState);
if (document.readyState === 'loading') {
  console.log('⏳ DOM still loading, waiting for DOMContentLoaded...');
  document.addEventListener('DOMContentLoaded', () => {
    console.log('🎬 DOMContentLoaded fired, calling init()');
    init();
  });
} else {
  console.log('✅ DOM already loaded, calling init() immediately');
  init();
}
