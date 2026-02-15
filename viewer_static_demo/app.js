// WarGame Static Viewer
// Loads simulation JSON and displays metrics

const gameSelect = document.getElementById('gameSelect');
const roundSlider = document.getElementById('roundSlider');
const roundDisplay = document.getElementById('roundDisplay');
const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');

// Metric elements
const metricIds = {
    nucRU: document.getElementById('nucRU'),
    nucUS: document.getElementById('nucUS'),
    nucGB: document.getElementById('nucGB'),
    nucFR: document.getElementById('nucFR'),
    oilPrice: document.getElementById('oilPrice'),
    eurUsd: document.getElementById('eurUsd'),
    corridor: document.getElementById('corridor'),
    natolert: document.getElementById('natolert'),
    casualties: document.getElementById('casualties'),
    refugees: document.getElementById('refugees'),
    eventsPanel: document.getElementById('eventsPanel'),
    roundInfo: document.getElementById('roundInfo')
};

// Current game and round
let currentGame = 'game_20260214_175118';
let currentRound = 1;
let gameMetadata = {};

// Logging helper
function log(section, message, data = null) {
    const timestamp = new Date().toLocaleTimeString();
    const prefix = `[${timestamp}] [${section}]`;
    if (data !== null) {
        console.log(`${prefix} ${message}`, data);
    } else {
        console.log(`${prefix} ${message}`);
    }
}

// Initialize
gameSelect.addEventListener('change', (e) => {
    log('gameSelect', `Game changed to: ${e.target.value}`);
    currentGame = e.target.value;
    currentRound = 1;
    roundSlider.value = 1;
    roundDisplay.textContent = '1';
    loadRound(1);
});

roundSlider.addEventListener('input', (e) => {
    currentRound = parseInt(e.target.value);
    roundDisplay.textContent = currentRound;
    log('roundSlider', `Round changed to: ${currentRound}`);
    loadRound(currentRound);
});

prevBtn.addEventListener('click', () => {
    if (currentRound > 1) {
        currentRound--;
        roundSlider.value = currentRound;
        roundDisplay.textContent = currentRound;
        log('prevBtn', `Moved to previous round: ${currentRound}`);
        loadRound(currentRound);
    } else {
        log('prevBtn', `Already at round 1, cannot go back`);
    }
});

nextBtn.addEventListener('click', () => {
    if (currentRound < 30) {
        currentRound++;
        roundSlider.value = currentRound;
        roundDisplay.textContent = currentRound;
        log('nextBtn', `Moved to next round: ${currentRound}`);
        loadRound(currentRound);
    } else {
        log('nextBtn', `Already at round 30, cannot go forward`);
    }
});

// Normalize stringified Python dicts to JSON (fixes games 175116, 175117, 220004)
function normalizeData(obj, path = 'root') {
    if (typeof obj !== 'object' || obj === null) return obj;

    if (Array.isArray(obj)) {
        let stringifiedCount = 0;
        const result = obj.map((item, idx) => {
            if (typeof item === 'string' && item.startsWith('{')) {
                stringifiedCount++;
                try {
                    // Convert stringified Python dict to JSON
                    let normalized = item
                        .replace(/'/g, '"')           // Single quotes → double quotes
                        .replace(/True/g, 'true')     // Python True → JSON true
                        .replace(/False/g, 'false')   // Python False → JSON false
                        .replace(/None/g, 'null');    // Python None → JSON null
                    return JSON.parse(normalized);
                } catch (e) {
                    log('normalizeData', `Failed to parse stringified dict at ${path}[${idx}]: ${e.message}`);
                    return item; // Return as-is if parsing fails
                }
            }
            return normalizeData(item, `${path}[${idx}]`);
        });
        if (stringifiedCount > 0) {
            log('normalizeData', `Converted ${stringifiedCount} stringified dicts in ${path}`);
        }
        return result;
    }

    if (typeof obj === 'object') {
        const normalized = {};
        for (const [key, value] of Object.entries(obj)) {
            normalized[key] = normalizeData(value, `${path}.${key}`);
        }
        return normalized;
    }

    return obj;
}

// Load and display round data
async function loadRound(round) {
    const padded = String(round).padStart(3, '0');
    const url = `../logs/${currentGame}/round_${padded}.json`;

    log('loadRound', `─────────────────────────────────`);
    log('loadRound', `Starting load for round ${round}`, { game: currentGame, url: url });

    try {
        log('loadRound', `Sending fetch() request...`);
        const response = await fetch(url);

        log('loadRound', `Fetch completed`, {
            status: response.status,
            ok: response.ok,
            statusText: response.statusText
        });

        if (!response.ok) {
            const errorMsg = `Round ${round} data unavailable (HTTP ${response.status})`;
            log('loadRound', `❌ FETCH FAILED: ${errorMsg}`);
            showError(errorMsg);
            return;
        }

        log('loadRound', `Parsing JSON response...`);
        let data = await response.json();
        log('loadRound', `✓ JSON parsed successfully`, {
            keys: Object.keys(data),
            keyCount: Object.keys(data).length
        });

        log('loadRound', `Normalizing data for stringified Python dicts...`);
        data = normalizeData(data);
        log('loadRound', `✓ Data normalized`);

        log('loadRound', `Displaying round data...`);
        displayRoundData(data);
        log('loadRound', `✅ Round ${round} loaded and displayed successfully`);
        log('loadRound', `─────────────────────────────────`);

    } catch (error) {
        const errorMsg = `Error loading round ${round}: ${error.message}`;
        log('loadRound', `❌ EXCEPTION: ${errorMsg}`, error);
        showError(errorMsg);
    }
}

// Display parsed round data
function displayRoundData(data) {
    log('displayRoundData', `Processing world_state_after...`);

    const ws = data.world_state_after;
    if (!ws) {
        log('displayRoundData', `❌ ERROR: world_state_after not found in data!`, { dataKeys: Object.keys(data) });
        showError('Invalid data structure: missing world_state_after');
        return;
    }

    log('displayRoundData', `✓ world_state_after found`, {
        keyCount: Object.keys(ws).length,
        hasNuclear: !!ws.nuclear_posture,
        hasMarkets: !!ws.markets,
        hasMilitaryUnits: !!ws.military_units,
        hasRefugees: !!ws.refugee_flows
    });

    // Nuclear posture
    const nuc = ws.nuclear_posture || {};
    log('displayRoundData', `Setting nuclear posture`, nuc);
    metricIds.nucRU.textContent = nuc.RU || '—';
    metricIds.nucUS.textContent = nuc.US || '—';
    metricIds.nucGB.textContent = nuc.GB || '—';
    metricIds.nucFR.textContent = nuc.FR || '—';

    // Economic
    const markets = ws.markets || {};
    const oilPrice = markets.oil_price ? markets.oil_price.toFixed(2) : '—';
    const eurUsd = markets.euro_usd ? markets.euro_usd.toFixed(2) : '—';
    log('displayRoundData', `Setting market prices`, { oilPrice, eurUsd });
    metricIds.oilPrice.textContent = oilPrice;
    metricIds.eurUsd.textContent = eurUsd;

    // Military
    log('displayRoundData', `Setting military status`, {
        corridor: ws.corridor_control,
        natolert: ws.nato_alert_level
    });
    metricIds.corridor.textContent = ws.corridor_control || '—';
    metricIds.natolert.textContent = ws.nato_alert_level || '—';

    // Conflict impact
    const casualties = calculateCasualties(ws.military_units || []);
    log('displayRoundData', `Calculated casualties from ${(ws.military_units || []).length} units`, { casualties });
    metricIds.casualties.textContent = casualties.toLocaleString();

    const refugees = calculateRefugees(ws.refugee_flows || []);
    log('displayRoundData', `Calculated refugees from ${(ws.refugee_flows || []).length} flows`, { refugees });
    metricIds.refugees.textContent = refugees.toLocaleString();

    // Events
    log('displayRoundData', `Displaying events and headlines...`);
    displayEvents(data);

    // Round info
    log('displayRoundData', `Displaying round info...`);
    displayRoundInfo(data);

    log('displayRoundData', `✅ All metrics displayed successfully`);
}

// Calculate total casualties from military units
function calculateCasualties(units) {
    if (!Array.isArray(units)) return 0;
    return units.reduce((sum, unit) => {
        if (typeof unit === 'object' && unit !== null) {
            return sum + (parseInt(unit.casualties) || 0);
        }
        return sum;
    }, 0);
}

// Calculate total refugee flows
function calculateRefugees(flows) {
    if (!Array.isArray(flows)) return 0;
    return flows.reduce((sum, flow) => {
        if (typeof flow === 'object' && flow !== null) {
            const count = parseInt(flow.count) || parseInt(flow.volume) || 0;
            return sum + count;
        }
        return sum;
    }, 0);
}

// Display events and headlines
function displayEvents(data) {
    log('displayEvents', `Processing events...`);
    const html = [];
    const ws = data.world_state_after;

    // Headlines from resolution
    if (data.resolution && data.resolution.headlines && Array.isArray(data.resolution.headlines) && data.resolution.headlines.length > 0) {
        log('displayEvents', `Found ${data.resolution.headlines.length} headlines`);
        html.push('<strong>Headlines:</strong>');
        data.resolution.headlines.slice(0, 3).forEach((headline, idx) => {
            log('displayEvents', `  Headline ${idx + 1}: ${headline.substring(0, 60)}...`);
            html.push(`<p>• ${headline}</p>`);
        });
    }

    // Surprises from resolution
    if (data.resolution && data.resolution.surprises && Array.isArray(data.resolution.surprises) && data.resolution.surprises.length > 0) {
        log('displayEvents', `Found ${data.resolution.surprises.length} surprise developments`);
        html.push('<strong>Developments:</strong>');
        data.resolution.surprises.slice(0, 2).forEach((surprise, idx) => {
            log('displayEvents', `  Development ${idx + 1}: ${surprise.substring(0, 60)}...`);
            html.push(`<p>⚡ ${surprise}</p>`);
        });
    }

    // Fallback: if no headlines/surprises, use recent_events from world_state_after
    if (html.length === 0 && ws.recent_events && Array.isArray(ws.recent_events) && ws.recent_events.length > 0) {
        log('displayEvents', `No headlines/surprises, using recent_events fallback (${ws.recent_events.length} events)`);
        html.push('<strong>Recent Events:</strong>');
        ws.recent_events.slice(0, 3).forEach((event, idx) => {
            if (typeof event === 'string') {
                log('displayEvents', `  Event ${idx + 1}: ${event.substring(0, 60)}...`);
                html.push(`<p>• ${event}</p>`);
            }
        });
    }

    // Final fallback
    if (html.length === 0) {
        log('displayEvents', `No events found anywhere, showing placeholder`);
        html.push('<p class="placeholder">No major events this round</p>');
    }

    metricIds.eventsPanel.innerHTML = html.join('');
}

// Display round metadata
function displayRoundInfo(data) {
    log('displayRoundInfo', `Processing round information...`);
    const html = [];
    const ws = data.world_state_after;

    html.push(`<p><strong>Game Time:</strong> ${ws.game_time || '—'}</p>`);
    html.push(`<p><strong>Round:</strong> ${ws.round_number || currentRound}</p>`);

    // Summary - try resolution.narrative first, fallback to recent_events
    const summary = [];
    if (data.resolution && data.resolution.narrative && data.resolution.narrative.trim().length > 0) {
        log('displayRoundInfo', `Using resolution.narrative`);
        const narrative = data.resolution.narrative.split('.')[0] + '.';
        summary.push(`<p><em>${narrative}</em></p>`);
    } else if (ws.recent_events && ws.recent_events.length > 0) {
        // Fallback: show first recent event as summary
        log('displayRoundInfo', `No resolution.narrative, using recent_events fallback`);
        const firstEvent = ws.recent_events[0];
        if (typeof firstEvent === 'string') {
            const eventText = firstEvent.split('.')[0] + '.';
            summary.push(`<p><em>${eventText}</em></p>`);
        }
    } else {
        log('displayRoundInfo', `No narrative or events found`);
    }

    html.push(summary.join(''));
    metricIds.roundInfo.innerHTML = html.join('');
    log('displayRoundInfo', `✓ Round info displayed`);
}

// Error display
function showError(message) {
    Object.values(metricIds).forEach(el => {
        if (el.textContent && el.textContent !== '—') {
            el.textContent = '—';
        }
    });
    metricIds.eventsPanel.innerHTML = `<p class="error">${message}</p>`;
    metricIds.roundInfo.innerHTML = `<p class="error">${message}</p>`;
}

// Initialize on load
window.addEventListener('DOMContentLoaded', () => {
    log('INIT', `═══════════════════════════════════`);
    log('INIT', `WarGame Viewer Initializing...`);
    log('INIT', `Page loaded and DOM ready`, {
        defaultGame: currentGame,
        defaultRound: currentRound,
        totalMetricsElements: Object.keys(metricIds).length
    });
    log('INIT', `Loading initial round...`);
    loadRound(1);
});
