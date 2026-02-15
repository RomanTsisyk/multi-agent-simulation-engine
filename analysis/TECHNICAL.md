# Multi-Agent Simulation Engine (WarGame Scenario Demo): Technical Architecture Documentation

**Version**: 2.0 (Claude Code Game Runner)
**Last Updated**: 2026-02-15

---

## 📐 Architecture Overview

WarGame is a sophisticated multi-agent geopolitical simulation engine that models complex international crises through:

1. **Multi-Faction Debates** - Each country contains 2-4 AI-powered factions with competing interests
2. **Game Master Resolution** - Deterministic resolution of military conflicts, economic impacts, and cascading effects
3. **World State Management** - Global state tracking with real-time metrics and escalation tracking
4. **Static Web Viewer** - No-backend HTML/JS interface for analyzing game results

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    WarGame System                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐      ┌──────────────┐   ┌──────────────┐ │
│  │   Game      │      │   Country    │   │   Faction    │ │
│  │   Engine    │─────▶│   Agents     │──▶│   Agents     │ │
│  │             │      │              │   │  (debates)   │ │
│  └─────────────┘      └──────────────┘   └──────────────┘ │
│        │                                         │          │
│        │ Orchestrates                           │ Debate   │
│        │ rounds                                 │ 3 rounds │
│        │                                         │          │
│        ▼                                         ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │        LLM Backend (Ollama / DeepSeek)             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │    World State Manager (Metrics, Cascading Effects)│   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │    Game Master (Combat Resolution, Validation)     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  Game Logs (JSON)  │
                    │  /logs/game_*/     │
                    │  round_*.json      │
                    └──────────┬─────────┘
                              │
                    ┌─────────▼──────────────────┐
                    │  Static Web Viewer         │
                    │  /viewer_static_demo/      │
                    │  production.html + Chart.js│
                    └────────────────────────────┘
```

---

## 🎮 Game Loop

### Round Execution Flow

```
Round Start
    │
    ├─► Load World State (from previous round)
    │
    ├─► Situation Briefing (GM writes context)
    │
    ├─► Country Deliberation (8 parallel agents)
    │   ├─ Each agent gets situation + country contexts
    │   ├─ Factions debate in 3 rounds (initial → rebuttal → synthesis)
    │   └─ Output: Unified country decisions with reasoning
    │
    ├─► GM Resolution
    │   ├─ Parse all country decisions
    │   ├─ Resolve military conflicts (combat formula)
    │   ├─ Check public opinion gates
    │   ├─ Apply economic consequences
    │   ├─ Generate headlines & surprises
    │   └─ Output: Resolution JSON
    │
    ├─► Update World State
    │   ├─ Apply military changes
    │   ├─ Update nuclear posture (escalation ladder)
    │   ├─ Cascading effects:
    │   │  ├─ Oil prices → war support changes
    │   │  ├─ Sanctions → EU gas prices
    │   │  ├─ Casualties → morale reduction
    │   │  ├─ Infrastructure damage → gov approval
    │   │  └─ NATO alert → auto-escalation
    │   └─ Calculate new metrics
    │
    ├─► Save Checkpoint
    │   └─ Write round_NNN.json with full state
    │
    └─► Check Victory Conditions
        └─ Continue → Next round or End game
```

---

## 🏛️ Core Components

### 1. Game Engine (`engine/game.py`)

**Responsibilities:**
- Orchestrate round execution
- Manage game lifecycle
- Load/save checkpoints
- Check victory conditions

**Key Methods:**
```python
async def run_round(round_num: int) -> None
    # Execute one complete round

async def execute_country_deliberation(round_num: int) -> Dict
    # Spawn 8 Task agents for parallel country decisions

def check_victory_conditions() -> Optional[str]
    # Return winner or None
```

**Country Agent Batching:**
- **PL (Poland)** - Solo agent (frontline urgency)
- **LT, LV, EE (Baltics)** - Shared agent (regional coordination)
- **US** - Solo agent (superpower independence)
- **GB, FR, DE** - Shared agent (major allies)
- **FI, SE, NO, DK** - Shared agent (Nordic bloc)
- **CA, NL, BE, CZ, RO** - Shared agent (NATO contributors)
- **RU (Russia)** - Solo agent (adversary isolation)
- **BY, TR, HU, CN** - Shared agent (wildcards/observers)

### 2. World State (`engine/world_state.py`)

**State Structure:**
```python
class WorldState:
    round_num: int
    game_time: str                      # e.g., "Day 3, 18:00 UTC"

    # Military
    corridor_control: str               # "contested", "nato", "russian"
    military_units: Dict[str, List]     # Brigades, positions, readiness
    casualties: Dict[str, int]          # Deaths by country
    supply_levels: Dict[str, float]     # 0-10, affects combat power

    # Nuclear
    nuclear_posture: Dict[str, str]     # "peacetime" → "elevated" → "dispersal" → "launch_ready"
    nuclear_weapons_used: bool          # Game end condition

    # Economic
    markets: Dict                       # oil_price, exchange_rates, etc.
    sanctions: Dict[str, List[str]]     # Who is sanctioning whom

    # Political/Public Opinion
    war_support: Dict[str, float]       # 0-100% by country
    gov_approval: Dict[str, float]      # 0-100% by country
    public_morale: Dict[str, float]     # 0-100%, affects military readiness

    # Escalation Tracking
    escalation_level: float             # 0 (cold war) to 10 (nuclear)
    nato_alert_level: str               # "peacetime", "heightened", "combat", "maximum"

    # Refugees & Displacement
    refugee_count: int
    displaced_persons: Dict[str, int]
```

**Key Cascading Effects** (applied after each round):

| Trigger | Effect | Formula |
|---------|--------|---------|
| Oil price spike | War support ↓ | support -= (oil_price - baseline) × 0.5 |
| Casualties | Morale ↓ | morale -= (casualties / population) × 100 |
| Sanctions | Gov approval ↓ | approval -= sanctions_count × 3 |
| Low supply | Combat power ↓ | effectiveness *= 0.7 if supply < 3 |
| High casualties | Public opposition ↑ | war_support cap = 50% if casualties > threshold |
| NATO invoked | Auto-escalation | nuclear_posture ++ |

### 3. Game Master (`engine/game_master.py`)

**Responsibilities:**
- Validate country decisions
- Resolve military conflicts
- Apply GM rules (public opinion gates, force ratios)
- Generate narrative (headlines, surprises)

**Combat Resolution Formula:**

```
attacker_effectiveness = strength × (readiness/10) × air_mult × supply_mult
defender_effectiveness = strength × (readiness/10) × terrain_mult × supply_mult

where:
  air_mult = 1.3 (with air superiority) or 1.0
  terrain_mult = 1.2 (forest/urban/mountains) or 1.0
  supply_mult = 0.7 (if supply < 3) or 1.0

casualty_ratio = attacker_eff / (defender_eff + 0.1)
if casualty_ratio > 1.0:
    defender loses more; attacker may advance
else:
    attacker halts or retreats; high casualties
```

**Public Opinion Gates:**

| War Support | Allowed Actions |
|-------------|-----------------|
| > 70% | Offensive, foreign deployments |
| 50-70% | Defensive operations only |
| 30-50% | Diplomatic pressure only |
| < 30% | No military action (crisis) |

**Decision Validation Rules:**
- Can't attack if war_support < 30%
- Can't deploy troops without public approval
- Nuclear escalation → must cite public/military justification
- Can't claim air superiority without documented control

### 4. Analytics (`engine/analytics.py`)

Post-game analysis:
- Timeline of key turning points
- Faction influence on outcomes
- Economic trends
- Escalation trajectory
- Victory analysis

---

## 🤖 Agents

### Country Agent (`agents/country.py`)

**Role**: Orchestrates country's internal deliberation

**Responsibilities:**
1. Load situation briefing + country context
2. Spawn 2-4 faction agents (simultaneous)
3. Collect faction positions
4. Synthesize unified decision
5. Return structured decision JSON

**Decision Schema:**
```json
{
  "country": "PL",
  "country_name": "Poland",
  "reasoning": "Brief internal consensus explanation",
  "actions": [
    "Deploy 2nd mechanized brigade to Suwalki corridor",
    "Request US air support",
    "Invoke Article 5"
  ],
  "diplomatic_messages": [
    {
      "to": "US",
      "channel": "private",
      "message": "We need immediate air superiority or corridor is lost in 12 hours"
    }
  ],
  "nuclear_posture": "elevated",
  "supply_request": 5
}
```

### Faction Agent (`agents/faction.py`)

**Role**: Represents single faction (hawk, dove, diplomat, etc.)

**Debate Protocol** (3 rounds):

1. **Round 1: Initial Position**
   - Faction states opening argument
   - Cites historical precedents
   - Outlines strategic concerns

2. **Round 2: Rebuttal**
   - Respond to other factions
   - Challenge assumptions
   - Propose alternative strategies

3. **Round 3: Synthesis**
   - Move toward consensus
   - Identify acceptable compromises
   - Agree on unified position

**Personality Definition** (from YAML):
```yaml
factions:
  - name: "President & National Security Council"
    role: "hawk"
    personality: |
      Aggressive, nationalist, sees Russian expansion as existential threat.
      References 1939 Munich Agreement constantly. Wants immediate military action.
    priorities:
      - "Defend Polish territory at all costs"
      - "Activate NATO Article 5"
    red_lines:
      - "Will not accept Russian control of Polish soil"
    influence_weight: 3.0  # In escalation phases
```

---

## 💾 State Management

### Checkpoint System (`engine/checkpoint.py`)

Saves complete game state after each round:

```python
def save_checkpoint(game_state: GameState, round_num: int) -> str:
    """
    Writes: logs/game_TIMESTAMP/round_NNN.json
    Contains:
    - world_state_before
    - situation_briefing
    - country_decisions (all 8 agents' outputs)
    - gm_resolution (combat, headlines, surprises)
    - world_state_after
    - metrics (casualties, morale, etc.)
    """
```

**Resume Capability:**
```bash
python run.py play --preset suwalki --resume logs/game_20260215_123456/
```

---

## 🌐 Static Web Viewer

### Architecture

The viewer runs entirely in the browser without a backend server.

**Files:**
```
viewer_static_demo/
├── production.html          # Main interface
├── production-app.js        # Game logic & visualization
├── index.html              # Landing page
├── demo_data/              # Static game logs
│   ├── game_20260213_205400/
│   │   ├── round_001.json
│   │   ├── round_002.json
│   │   └── ...
│   ├── game_20260214_175116/
│   └── ...
```

### Viewer Features

**Dashboard View:**
- 4 interactive Chart.js visualizations
  - Oil Price ($/barrel over time)
  - Nuclear Posture (country escalation ladder)
  - War Support (% by country)
  - Military Balance (NATO vs Russia strength)
- Key metrics (current round, casualties, corridor control)

**Rounds View:**
- Select any round from dropdown
- Situation briefing
- All country decisions (expandable)
  - Actions taken
  - Diplomatic messages
  - Reasoning
- Combat results
- Headlines & surprise developments

**Countries View:**
- Table of all 66+ countries
- War support %
- Government approval %
- Military morale
- Nuclear posture

**World State View:**
- Global metrics (oil price, sanctions, refugees)
- Full JSON export for analysis

### Data Loading

```javascript
async function discoverGames() {
  // Check for game_*/round_001.json in demo_data/
  // Build list of available games
}

async function loadGameData(gameName) {
  // Fetch all rounds for selected game
  // Populate state.rounds[N] with JSON data
}

function renderCharts() {
  // Use Chart.js to visualize:
  // - Oil prices
  // - Nuclear posture
  // - War support
  // - Military balance
}

function renderRoundsView() {
  // Show situation briefing
  // Expand country decisions
  // Display combat results
  // Show headlines
}
```

### Deployment

GitHub Pages serves from `/viewer_static_demo/`:

```
https://roman-tsisyk.com/viewer_static_demo/production.html
```

Or via GitHub URL:
```
https://RomanTsisyk.github.io/multi-agent-simulation-engine/viewer_static_demo/production.html
```

**No backend required** - all data is static JSON files served as-is.

---

## ⚙️ Configuration

### Scenario Files (`scenarios/`)

```yaml
name: "Suwalki Gap Crisis"
description: "Russia seizes corridor between Poland and Lithuania..."

participants:
  - code: "PL"
    name: "Poland"
  - code: "RU"
    name: "Russia"
  - code: "US"
    name: "United States"
  # ... etc

initial_state:
  corridor_control: "contested"
  nuclear_posture:
    RU: "peacetime"
    US: "peacetime"
  war_support:
    PL: 75
    US: 60
    RU: 45

victory_conditions:
  - id: "russian_victory"
    type: "corridor_control"
    threshold_rounds: 6
    description: "Russia holds corridor for 6 complete rounds"

  - id: "nato_victory"
    type: "corridor_control"
    threshold_rounds: 10
    description: "NATO liberates corridor within 10 rounds"

  - id: "nuclear_escalation"
    type: "immediate"
    description: "Game ends immediately if nuclear weapon detonates"
```

### Country Files (`countries/*.yaml`)

```yaml
name: "Poland"
code: "PL"
capital: "Warsaw"

# Military Capability (1-10 scale)
military_strength: 5
military_composition:
  brigades: 25
  tanks: 800
  aircraft: 60
  air_defense: "limited"

# Economic Indicators
gdp_billions: 880
population_millions: 37.7
economic_strength: 6

# Nuclear Status
nuclear_weapons: false
nuclear_research: false

# Geopolitical Alignment
alliances:
  - "NATO"
  - "EU"
strategic_partners:
  - "US"
  - "UK"
  - "Germany"

# Internal Factions
factions:
  - name: "President & National Security Council"
    role: "hawk"
    personality: |
      Aggressive, nationalist, existential threat framing.
      References 1939 appeasement. Wants immediate military action.
    priorities:
      - "Defend Polish territory"
      - "Invoke Article 5"
    red_lines:
      - "Will not accept Russian control of Polish soil"
    influence_weight: 3.0      # In escalation

  - name: "Prime Minister & Government"
    role: "diplomat"
    personality: |
      Pragmatic, consensus-builder, risk-aware.
      Emphasizes NATO unity and institutional processes.
    priorities:
      - "Maintain NATO cohesion"
      - "Avoid unilateral escalation"
    red_lines:
      - "NATO fracture = defeat"
    influence_weight: 2.0

  - name: "General Staff"
    role: "military_realist"
    personality: |
      Concerned with force ratios, logistics, realistic assessments.
      Cites military doctrine and operational constraints.
    priorities:
      - "Preserve force effectiveness"
      - "Secure supply lines"
    red_lines:
      - "Overextension without support"
    influence_weight: 2.5
```

### System Config (`config.yaml`)

```yaml
game:
  scenario: "suwalki"
  num_countries: 20
  max_rounds: 10

backend:
  type: "deepseek"  # or "ollama"
  model: "deepseek-r1:32b"
  api_key: "${DEEPSEEK_API_KEY}"
  max_concurrent: 10
  timeout_seconds: 120

llm:
  temperature: 0.7
  max_tokens: 2000

logging:
  level: "INFO"
  save_rounds: true
  output_dir: "logs"
```

---

## 🔧 Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run quick game (4 countries, 3 rounds)
python run.py play --preset quick

# Run with specific backend
python run.py play --preset medium --backend deepseek

# Resume interrupted game
python run.py play --preset suwalki --resume logs/game_20260215_123456/

# View results in browser
python run.py view logs/game_20260215_123456/
```

### Testing

```bash
# Unit tests
pytest tests/ -v

# Coverage report
pytest --cov=engine,agents,backends

# Specific test
pytest tests/test_combat.py::test_attacker_advantage -v
```

### Code Structure

```
wargame/
├── engine/
│   ├── game.py              # Game orchestration
│   ├── world_state.py       # State management
│   ├── game_master.py       # Combat resolution, validation
│   ├── analytics.py         # Post-game analysis
│   └── checkpoint.py        # Save/load
├── agents/
│   ├── country.py           # Country orchestration
│   └── faction.py           # Faction debates
├── backends/
│   ├── ollama_backend.py    # Local LLM
│   └── deepseek_backend.py  # Cloud LLM
├── scenarios/               # YAML scenario files
├── countries/               # YAML country configs (66+)
├── tests/
│   ├── test_combat.py
│   ├── test_cascading.py
│   ├── test_fixes.py
│   └── ...
├── viewer_static_demo/      # Web viewer
│   ├── production.html
│   ├── production-app.js
│   ├── demo_data/           # Static game logs
│   └── index.html
├── claude_runner/           # Claude Code integration
│   ├── game_state.py        # State management CLI
│   └── prompts.py           # Prompt templates
├── run.py                   # Main CLI
├── config.yaml              # System configuration
├── presets.py               # Game presets (quick/medium/full)
└── CLAUDE.md                # Claude Code instructions
```

---

## 📊 Key Metrics & Calculations

### Escalation Level (0-10)

```python
def calculate_escalation() -> float:
    base = 0

    # Nuclear posture contribution
    postures = {"peacetime": 0, "elevated": 2, "dispersal": 4, "launch_ready": 6}
    base += mean(postures[np] for np in nuclear_postures.values())

    # Military activity contribution
    base += (total_casualties / 100000) * 2
    base += (active_combat_zones) * 0.5

    # Economic impact
    base += (oil_price - 70) / 20  # Baseline $70/barrel

    # NATO alert level
    alert_contribution = {
        "peacetime": 0,
        "heightened": 1,
        "combat": 3,
        "maximum": 5
    }
    base += alert_contribution[nato_alert]

    return min(base, 10)
```

### Military Readiness

```python
readiness = (personnel_percent × 0.4) +
            (equipment_condition × 0.3) +
            (supply_level × 0.2) +
            (training_level × 0.1)
```

### Public Opinion Constraints

Calculated from cascading effects:
- Oil prices (commodity shock)
- Casualties (human cost)
- Economic sanctions (financial impact)
- War duration (fatigue)
- Media narratives (GM headlines)

---

## 🔌 Integration Points

### LLM Backends

Both backends implement same interface:

```python
class LLMBackend:
    async def query(self, prompt: str, max_tokens: int) -> str
    async def batch_query(self, prompts: List[str]) -> List[str]
```

**Ollama** (local):
- Supports deepseek-r1:32b, llama2-70b, etc.
- No API key needed
- Slower, privacy-preserving

**DeepSeek** (cloud):
- Faster, supports reasoning models
- Parallel queries (up to 10 concurrent)
- API key required
- ~$0.50-3.00 per game

### Claude Code Integration (`claude_runner/`)

Game Master role played by Claude Code directly:

```bash
# Initialize game
python3 claude_runner/game_state.py init --preset suwalki-claude

# Get briefing for round
python3 claude_runner/game_state.py briefing --game-dir logs/game_XXXXX

# Get country context for deliberation
python3 claude_runner/game_state.py country-context --game-dir logs/game_XXXXX --countries PL US RU

# Apply round resolution
python3 claude_runner/game_state.py apply --game-dir logs/game_XXXXX --resolution round_N.json --round N
```

**Rate Limits:**
- ~15 Claude API calls per round
- Each round = ~300K tokens
- ~4-6 rounds per 5-hour window with Claude Max

---

## 🐛 Known Limitations & Future Work

### Current Limitations

1. **No dynamic country creation** - Limited to pre-configured 66 countries
2. **No human player mode** - All decisions made by AI
3. **Limited scenario variety** - Primary scenario is Suwalki Gap
4. **Simplified economics** - Oil price main driver, limited trade dynamics
5. **No real-time multiplayer** - Single-player AI simulation only

### Planned Improvements

- [ ] Player mode (human controls 1 country)
- [ ] Visual scenario editor
- [ ] Real-time War Room dashboard
- [ ] Enhanced economic modeling
- [ ] Diplomacy event system (treaties, alliances)
- [ ] Alternative victory conditions
- [ ] Mobile-responsive web viewer

---

## 📚 References

- RAND Corporation: "War with China" and Baltic defense studies
- Clausewitz: *On War* (friction, fog, escalation dynamics)
- Game Theory: Nash equilibrium, prisoner's dilemma applications
- Crisis Studies: Brody & Ramsbotham escalation models

---

**For implementation details, see CLAUDE.md for Claude Code runner protocol.**
