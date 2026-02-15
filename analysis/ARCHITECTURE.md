# Architecture: Multi-Agent Simulation Engine

---

## System Overview

```
┌────────────────────────────────────────────────────────┐
│           Game Loop (engine/game.py)                   │
├────────────────────────────────────────────────────────┤
│                                                        │
│  1. Load World State (from checkpoint)                 │
│  2. Write Situation Briefing (GM context)              │
│  3. Spawn 8 Country Agents (parallel)                  │
│     ├─ Each agent loads situation + country context   │
│     ├─ Spawns 2-4 faction agents                       │
│     └─ Outputs: Unified country decision (JSON)       │
│  4. Game Master Resolution (validate & resolve)        │
│     ├─ Combat: strength formulas                       │
│     ├─ Economy: oil price effects                      │
│     ├─ Narrative: headlines & surprises               │
│  5. World State Updates (cascading effects)            │
│     ├─ Military changes                                │
│     ├─ Nuclear escalation                              │
│     ├─ Economic shocks                                 │
│     └─ Public opinion changes                          │
│  6. Save Checkpoint (round_NNN.json)                   │
│  7. Check Victory Conditions                           │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### Core Engine (`engine/`)

**game.py** - Round Orchestration
- `GameState` class: Holds current game + world state
- `run_round()`: Execute one complete round
- `execute_country_deliberation()`: Spawn 8 Task agents
- `check_victory_conditions()`: Determine if game ends

**world_state.py** - State Management
- `WorldState` class: Military, nuclear, economic, political state
- `apply_updates()`: Apply resolution to state
- `calculate_escalation()`: Compute escalation metrics
- Cascading effects (oil → opinion, casualties → morale)

**game_master.py** - Conflict Resolution
- Validate country decisions against public opinion gates
- Combat formula: Strength × Readiness × Force multipliers
- Generate GM output: Combat results, headlines, surprises
- Enforce game rules (nuclear limits, supply constraints)

**checkpoint.py** - Persistence
- `save_checkpoint()`: Write round_NNN.json
- `load_checkpoint()`: Resume from checkpoint
- Full JSON serialization of world state

---

### Agent System (`agents/`)

**country.py** - Country Orchestration
- Loads situation briefing + country context
- Spawns parallel faction agents (2-4 per country)
- Synthesizes decisions: weights faction positions, averages priorities
- Returns structured decision JSON

**faction.py** - Faction Debates
- 3-round debate protocol:
  1. Initial position (citing historical precedents)
  2. Rebuttal (attacking other factions)
  3. Synthesis (consensus statement)
- Configured via YAML:
  - Personality (role: hawk, dove, diplomat, etc.)
  - Priorities (ordered list)
  - Red lines (non-negotiable)
  - Influence weight (varies by phase)

---

### LLM Backends (`backends/`)

**OllamaBackend** - Local LLM
- Runs deepseek-r1:32b or other models locally
- No API key required
- Sequential queries only (no parallelism)
- Privacy-preserving

**DeepSeekBackend** - Cloud API
- Parallel queries (up to 10 concurrent)
- Faster than local
- ~$0.50-3.00 per game
- API key required

Both implement same interface:
```python
class LLMBackend:
    async def query(prompt: str) -> str
    async def batch_query(prompts: List[str]) -> List[str]
```

---

## Country Batching Strategy

**Why parallel agents?**
- US ≠ Poland politically (different constraints)
- NATO vs Russia must deliberate independently (don't leak strategy)
- Parallel execution: 8 agents × 3 rounds = ~24 parallel queries

**Batch Assignments:**

| Agent | Countries | Rationale |
|-------|-----------|-----------|
| 1 | **PL** | Frontline urgency, solo independence |
| 2 | **LT, LV, EE** | Regional bloc, shared threat model |
| 3 | **US** | Superpower, must decide independently |
| 4 | **GB, FR, DE** | Major allies, nuclear powers |
| 5 | **FI, SE, NO, DK** | Nordic bloc, shared geography |
| 6 | **CA, NL, BE, CZ, RO** | NATO contributors |
| 7 | **RU** | Adversary isolation, no NATO leakage |
| 8 | **BY, TR, HU, CN** | Wildcards + observers |

**Benefits:**
- Reduces artifact dependencies (US policy not pre-influenced by NATO)
- Parallel execution (8 agents × timeout)
- Maintains information asymmetry (Russia doesn't see NATO debate)

---

## Data Flow

```
Round N
  │
  ├─► situation_briefing.txt (GM writes context)
  │
  ├─► country_context:
  │   ├─ PL: military_strength, factions, history, alliances
  │   ├─ US: same
  │   └─ RU: same (isolated, no NATO context)
  │
  ├─► 8 Task Agents (parallel)
  │   ├─ Agent 1 (PL): Faction debates → unified decision
  │   ├─ Agent 2 (LT,LV,EE): Faction debates → 3 unified decisions
  │   ├─ ...
  │   └─ Agent 8 (BY,TR,HU,CN): 4 unified decisions
  │
  ├─► GM Resolution (Claude Code)
  │   ├─ Read all 8 agent outputs
  │   ├─ Resolve military conflicts
  │   ├─ Check public opinion gates
  │   ├─ Apply cascading effects
  │   └─ Generate narrative (headlines, surprises)
  │
  ├─► apply_resolution()
  │   ├─ Update military positions
  │   ├─ Update public opinion (cascading)
  │   ├─ Update economic state
  │   └─ Recalculate escalation level
  │
  └─► Checkpoint
      └─ Save round_N.json with full state

Round N+1
  └─ Load checkpoint, repeat
```

---

## State Persistence

Each round saved as JSON:

```json
{
  "round": 1,
  "game_time": "Day 1, 06:00 UTC",

  "world_state_before": {
    "corridor_control": "contested",
    "military_units": { "PL": [...], "RU": [...] },
    "nuclear_posture": { "US": "peacetime", "RU": "peacetime" },
    "war_support": { "PL": 75, "US": 60 },
    "oil_price": 89.5,
    ...
  },

  "situation_briefing": "Russia has seized the Suwalki corridor...",

  "country_decisions": [
    {
      "country": "PL",
      "actions": ["Deploy 2nd brigade", "Request US support"],
      "diplomatic_messages": [...],
      "reasoning": "..."
    },
    ...
  ],

  "gm_resolution": {
    "combat_results": [...],
    "headlines": [...],
    "surprises": [...]
  },

  "world_state_after": {
    "corridor_control": "contested",
    "casualties": { "PL": 150, "RU": 300 },
    "war_support": { "PL": 72, "US": 65 },
    ...
  },

  "metrics": {
    "escalation_level": 4.2,
    "nato_alert": "heightened",
    ...
  }
}
```

Full game playback from logs without re-running simulation.

---

## Web Viewer Architecture

**Static deployment** (no backend):

```
┌─────────────────────────────────────────────┐
│  production.html (main interface)           │
├─────────────────────────────────────────────┤
│                                             │
│  Chart.js (CDN) ← Charts library            │
│  production-app.js ← Game logic             │
│                                             │
│  ├─ discoverGames() → demo_data/game_*/     │
│  ├─ loadGameData() → fetch round_*.json     │
│  ├─ renderCharts() → Chart.js visualize     │
│  ├─ renderRoundsView() → Show decisions     │
│  ├─ renderCountriesView() → Show metrics    │
│  └─ renderWorldStateView() → Show state     │
│                                             │
└─────────────────────────────────────────────┘
         ↓
    GitHub Pages
         ↓
    roman-tsisyk.com/viewer_static_demo/
```

**No server required.**
- Games: `/viewer_static_demo/demo_data/game_*/round_*.json`
- Charts: Client-side Chart.js rendering
- Navigation: View switching via DOM manipulation
- Export: Full JSON download for analysis

---

## Extension Points

### New Scenarios

Create `scenarios/SCENARIO_NAME.yaml`:
```yaml
name: "Taiwan Strait Crisis"
participants: [US, CN, TW, JP]
initial_state:
  corridor_control: "contested"
  nuclear_posture: {US: "elevated", CN: "peacetime"}
victory_conditions:
  - id: "chinese_victory"
    threshold_rounds: 10
```

### New Countries

Create `countries/CODE.yaml`:
```yaml
name: "Vietnam"
military_strength: 4
factions:
  - name: "Communist Party"
    role: "hawk"
    priorities: ["Counter Chinese expansion"]
```

### New Backend

Implement `LLMBackend` interface:
```python
class MyBackend(LLMBackend):
    async def query(self, prompt: str) -> str:
        # Call your LLM API
        pass
```

---

## Runtime Characteristics

**Round Time Breakdown:**

| Phase | Time | Notes |
|-------|------|-------|
| Situation Briefing | 30s | GM writes context |
| Country Context Load | 30s | 8 loads (parallel) |
| Faction Debates | 120s | 8 agents × 3 rounds |
| GM Resolution | 60s | Combat + narrative |
| State Updates | 10s | Cascading effects |
| **Total** | **~240s** | **~4 minutes/round** |

**Full Game:**
- 10 countries × 10 rounds ≈ 40 minutes
- 20 countries × 10 rounds ≈ 60 minutes

---

## Error Handling & Recovery

**Checkpoint-based recovery:**
- Save before applying each resolution
- Can resume from any checkpoint
- Resume loads `round_N.json` and continues from N+1

**Agent timeouts:**
- Default: 120s per agent
- If timeout: Use fallback decision (minimal action)
- Log error but continue game

**Combat validation:**
- Check supply constraints
- Verify force ratio feasibility
- Reject decisions that violate public opinion gates

---

**Next: See DESIGN.md for architectural decision rationale.**
