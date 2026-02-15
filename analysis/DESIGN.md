# Design Decisions: Multi-Agent Simulation Engine

---

## Core Design: Why Multi-Agent?

### Problem Statement
Traditional wargames model countries as monolithic entities (President decides, everyone follows). This is unrealistic:
- Internal factions have competing interests
- Military vs civilians disagree on escalation
- Decision-making is messy, not clean

### Solution: Faction-Based Deliberation
Each country contains 2-4 independent factions that debate before deciding:

```
Poland Round 1:
  President (Hawk): "Attack NOW! Russia gains 1hr/position advantage"
  PM (Diplomat): "Fracture NATO = worse than losing corridor"
  General (Realist): "Force ratio is 1.4:1 against us"

→ Synthesis: Coordinated diplomatic pressure + 48h ultimatum
```

**Benefits:**
- Emergent decisions (not pre-scripted)
- Realistic political conflict
- Narrative depth
- Reproducible results (same LLM, same output)

---

## Decision 1: Parallel Country Agents

### Why 8 agents instead of 1?

| Approach | Pros | Cons |
|----------|------|------|
| 1 agent | Simple, sequential | Countries influence each other (artifact) |
| **8 agents** | **Independent decisions** | **More complex, higher token cost** |
| 66 agents | True independence | 66 timeouts, unmanageable parallelism |

### Chosen: 8 agents (batched by strategic interest)

```
Agent 1: PL           (frontline urgency)
Agent 2: LT, LV, EE   (regional bloc)
Agent 3: US           (superpower independence)
Agent 4: GB, FR, DE   (major allies)
Agent 5: FI, SE, NO   (Nordic bloc)
Agent 6: CA, NL, BE, CZ, RO (NATO contributors)
Agent 7: RU           (adversary, no NATO leakage)
Agent 8: BY, TR, HU, CN (wildcards)
```

**Rationale:**
- Each agent gets shared strategic context (same threat model)
- Countries within agent batch coordinate (realistic)
- Cross-batch decisions are independent
- US ≠ NATO (critical to prevent artificial consensus)
- Russia deliberates without seeing NATO debate (info asymmetry)

---

## Decision 2: 3-Round Faction Debate

### Why 3 rounds?

| Rounds | Result |
|--------|--------|
| 1 | Initial positions (static) |
| **3** | **Debate → Rebuttal → Synthesis** |
| 5+ | Diminishing returns (repetitive) |

### The 3-Round Protocol

1. **Opening**: Each faction states position, cites precedents
2. **Rebuttal**: Factions challenge each other, propose alternatives
3. **Synthesis**: Move toward consensus, identify compromises

**Why this structure?**
- Round 1: Captures ideological diversity
- Round 2: Forces engagement with opposing views
- Round 3: Produces unified decision (not gridlock)

Without rebuttal, factions just state positions and average them (boring).
With 3-round debate, emergent compromises appear.

---

## Decision 3: Game Master Arbitration

### Why not just average faction outputs?

**Problem:** Simple averaging of positions ignores:
- Military feasibility (attack needs 60% support + 2:1 force ratio)
- Economic constraints (can't invade if war support < 30%)
- Cascading effects (casualties reduce morale → lower future support)

### Solution: GM validates & resolves

```
Country Decision: "Poland attacks Russian 1st Army"
                     ↓
GM Checks:
  ✓ War support 75% > 30% minimum → ALLOWED
  ✓ Force ratio 1.1:1 vs 1.0:1 required → MARGINAL (high casualties)
  ✓ Supply level 6/10 → NO penalty
                     ↓
Combat Resolution:
  Polish: 5 (strength) × 0.8 (readiness) × 1.3 (terrain) × 1.0 (supply) = 5.2
  Russian: 4 × 0.7 × 1.0 × 1.0 = 2.8
  Ratio: 5.2/2.8 = 1.86 → Poland wins but with 300 casualties
                     ↓
Cascading Effects:
  Oil price spike (conflict) → war support -5%
  300 casualties (8,000 population) → morale -4%
  NATO invoked → auto-escalate nuclear posture
```

**Why arbitration?**
- Enforces military realism (can't attack with 1.0:1 ratio)
- Tracks consequences (action → state change → future constraints)
- Prevents degenerate outcomes (infinite escalation, free victories)

---

## Decision 4: Cascading Effects

### Problem
Most wargames isolate decisions:
- Battle happens, casualties accounted for
- But nobody asks: "How does 1000 deaths affect public opinion?"

### Solution: Cascading effects chain

```
Oil price spike ($120 → $140)
    ↓
Global economic shock
    ↓
EU gas prices ↑ → Trade disruption
    ↓
War support ↓ in non-frontline countries
    ↓
Political pressure on allies to escalate
    ↓
Germany hesitates on article 5
```

**Effect Categories:**

| Driver | Effect | Formula |
|--------|--------|---------|
| Oil spike | War support | support -= (price - baseline) × 0.5 |
| Casualties | Morale | morale -= (deaths / population) × 100 |
| Sanctions | Approval | approval -= sanction_count × 3 |
| Infrastructure damage | Readiness | readiness × 0.8 if damage > threshold |
| Refugee flows | Gov approval | approval -= refugee_count / population × 50 |

**Why cascading?**
- Decisions have long-term consequences
- Prevents "reset" mentality (each round is independent)
- Creates strategic depth (think 2-3 rounds ahead)
- Models realistic pressure (public opinion constrains escalation)

---

## Decision 5: Static Web Viewer

### Why no backend?

| Approach | Pros | Cons |
|----------|------|------|
| FastAPI backend | Real-time data, dynamic queries | Requires hosting, maintenance |
| **Static HTML/JS** | **Deploy anywhere, no server, fast** | **Limited interactivity** |

### Chosen: Static HTML/JS with Chart.js

**Architecture:**
```
production.html
    ↓
Loads demo_data/game_*/round_*.json (static files)
    ↓
production-app.js
    ├─ discoverGames() → check /demo_data/
    ├─ loadGameData() → fetch all rounds
    ├─ renderCharts() → Chart.js visualize
    └─ renderViews() → DOM manipulation
    ↓
Browser renders everything client-side
```

**Benefits:**
- Zero server cost (GitHub Pages hosts it free)
- Instant load (no API latency)
- Works offline
- Transparent (users see raw JSON)
- Deployable anywhere (just copy HTML folder)

**Trade-offs:**
- Can't add real-time live feeds
- Limited to pre-recorded games
- No dynamic queries

**Rationale:** WarGame is research tool, not product. Static viewer is perfect for analyzing historical games (post-hoc analysis).

---

## Decision 6: Claude Code Game Master

### Why Claude as GM instead of local LLM?

| System | Speed | Cost | Reasoning Quality |
|--------|-------|------|------------------|
| Ollama (local) | Slow | Free | Medium |
| **Claude Code** | **Fast** | **$0.50-3/game** | **Excellent** |
| DeepSeek API | Fast | Cheap | Good |

### Chosen: Claude Code (for feature/claude-code-runner)

**Game Master Tasks:**
- Validate political decisions against public opinion
- Resolve complex combat (1.4:1 ratio with air superiority vs terrain defense)
- Generate narrative (headlines that capture escalation)
- Handle surprise events (embassy evacuation, defection, cyber attack)

**Why Claude?**
- Excellent at complex reasoning (combat formula application)
- Good at narrative (headlines feel authentic, not generic)
- Fast iteration (quick feedback loop)
- Scales to full game (~15 messages per round)

**Trade-off:** Cost. But reliability and narrative quality justify $3-5 per game.

---

## Decision 7: Deterministic Resolution

### Problem
Stochastic resolution (dice rolls, random events) makes debugging hard:
- "Why did Russia win in Game A but lose in Game B?"
- Hard to replay, learn lessons

### Solution: Deterministic rules + LLM reasoning

```
Attack Resolution:
  attacker_strength = 5
  defender_strength = 4
  attacker_readiness = 0.8
  defender_readiness = 0.7

  attacker_eff = 5 × 0.8 × 1.3 (air) × 1.0 (supply) = 5.2
  defender_eff = 4 × 0.7 × 1.2 (terrain) × 1.0 = 3.36

  ratio = 5.2 / 3.36 = 1.55

  → Attacker wins with 20% casualty rate
```

**No randomness**, same LLM = same outcome.

**Benefits:**
- Reproducible (can debug and analyze)
- Transparent (users see the formula)
- Debuggable (understand why battle went certain way)
- Scalable (no statistical variance to confuse results)

---

## Decision 8: YAML Configuration

### Why YAML instead of hardcoding?

**Extensibility:**
```yaml
# Create new country instantly
name: "Taiwan"
military_strength: 6
factions:
  - name: "Democratic Party"
    role: "dove"
    priorities: ["Avoid Chinese invasion"]

# Create new scenario
name: "Taiwan Strait 2027"
participants: [US, CN, TW, JP]
victory_conditions:
  - id: "chinese_victory"
    threshold_rounds: 5
```

**No code changes needed.** Scenario designers can create games without programming.

---

## Decision 9: Country Batching Strategy

### Why batch countries by strategic interest?

**Alternative:** 1 agent per country
- Pro: True independence
- Con: 66 timeouts, 66 API calls per round, chaotic

**Chosen:** 8 agents (strategic grouping)

```
Agent 1: PL (solo)
  → Poland must decide alone (frontline urgency)

Agent 2: LT, LV, EE (grouped)
  → Baltics coordinate (shared threat from Russia)

Agent 3: US (solo)
  → US must decide independently (superpower)

Agent 7: RU (solo)
  → Russia deliberates in isolation (information asymmetry)
```

**Why this grouping?**
- **Strategic coherence**: Countries in same group share threat model
- **Realistic**: Allies coordinate (NATO, Baltic bloc, Nordic union)
- **Parallelism**: 8 agents = manageable timeout (3-5 min)
- **Information asymmetry**: Russia doesn't see NATO debate (game rules enforcement)

---

## Decision 10: Public Opinion Gates

### Problem
Players could escalate infinitely (50 wars, all nuclear).

### Solution: War support constraints

```
War Support < 30%
  → NO military action

War Support 30-50%
  → Defensive operations only

War Support 50-70%
  → Offensive ops allowed, no foreign deployment

War Support > 70%
  → Full military operations + foreign troops
```

**Why?**
- Realistic (democracies can't sustain unpopular wars)
- Strategic depth (manage public opinion as resource)
- Prevents degenerate (infinite offensive escalation)
- Constrains NATO (not every country will support expansion)

---

## Summary: Design Philosophy

1. **Multi-agent realism** - Countries have internal politics
2. **Parallel independence** - Prevent artificial consensus through batching
3. **Cascading effects** - Actions have long-term consequences
4. **Deterministic resolution** - Reproducible, debuggable outcomes
5. **Game master arbitration** - Enforce military and political realism
6. **Static deployment** - Zero-maintenance public viewer
7. **YAML extensibility** - Non-programmers can create scenarios
8. **Information asymmetry** - Different countries see different worlds
9. **Public opinion constraints** - War support as strategic resource
10. **Narrative consistency** - Headlines explain why events happen

**Result:** Research framework for studying emergent behavior in constrained multi-agent systems, not a polished product.

---

**Next: See GAME_MECHANICS.md for combat formulas and escalation rules.**
