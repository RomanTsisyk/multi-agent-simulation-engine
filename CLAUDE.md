# WarGame: Claude Code Game Runner

This project is a geopolitical wargame simulating the Suwalki Gap Crisis.
Claude Code acts as both Game Master and country deliberation engine,
replacing the Ollama/DeepSeek LLM backend.

## Quick Start

```bash
# Initialise a new game
python3 claude_runner/game_state.py init --preset suwalki-claude

# Check status
python3 claude_runner/game_state.py status --game-dir logs/game_XXXXX
```

Then say: **"Run round 1"** (or whichever round is next).

## Round Execution Protocol

When the user says "Run round N", follow these steps exactly:

### Step 1: Load World State

```bash
python3 claude_runner/game_state.py briefing --game-dir <GAME_DIR>
```

This prints the current world state briefing. Read it carefully.

### Step 2: Write Situation Briefing

As Game Master, write a 3-5 paragraph situation briefing covering:
- Current strategic situation
- Key developments from the previous round
- Escalation/de-escalation dynamics
- Decisions countries face this round

Use the GM rules from `claude_runner/prompts.py` (combat formula,
logistics, public opinion constraints).

### Step 3: Get Country Context

Load context for all 8 country batches (run in parallel where possible):

```bash
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries PL
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries LT LV EE
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries US
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries GB FR DE
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries FI SE NO DK
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries CA NL BE CZ RO
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries RU
python3 claude_runner/game_state.py country-context --game-dir <GAME_DIR> --countries BY TR HU CN
```

### Step 4: Spawn Country Deliberation Agents

Launch **8 Task agents in parallel** (use Sonnet model for speed).
Key players (US, RU, PL) get solo agents to ensure fully independent
decision-making. Allied/regional groups are batched by shared interests.

Each agent receives:
- The situation briefing from Step 2
- The country contexts from Step 3 for its batch
- The country deliberation prompt template from `claude_runner/prompts.py`

**Country batches (8 agents):**

| Agent | Countries | Rationale |
|-------|-----------|-----------|
| 1 | **PL** | Key frontline state, solo for independent decisions |
| 2 | **LT, LV, EE** | Baltic trio -- shared threat, coordinated response |
| 3 | **US** | Superpower, solo -- must decide independently of Europe |
| 4 | **GB, FR, DE** | Major European NATO / nuclear powers |
| 5 | **FI, SE, NO, DK** | Nordic bloc -- shared geography and interests |
| 6 | **CA, NL, BE, CZ, RO** | NATO contributors |
| 7 | **RU** | Primary adversary, solo -- must not leak strategy |
| 8 | **BY, TR, HU, CN** | Satellites + wildcards + observer |

**Why solo agents for US, RU, PL:**
- US and European NATO often disagree on escalation -- separate agents
  produce genuinely independent positions rather than artificial consensus
- Russia must deliberate without seeing NATO thinking (and vice versa)
- Poland as the frontline state has unique urgency that gets diluted in a group

Each agent must return a JSON array of country decisions matching this schema:

```json
[
  {
    "country": "PL",
    "country_name": "Poland",
    "actions": ["Deploy 2 additional brigades to Suwalki corridor", "..."],
    "diplomatic_messages": [{"to": "US", "channel": "private", "message": "..."}],
    "reasoning": "Brief internal reasoning"
  }
]
```

### Step 5: GM Resolution

As Game Master, read ALL country decisions from the 8 agents and produce
a resolution. Follow the GM rules strictly:
- Resolve military conflicts using the combat formula
- Check public opinion constraints before allowing offensive operations
- Apply economic consequences (oil price spikes, sanctions effects)
- Generate 2-4 headlines and 0-2 surprise developments
- Advance game clock by 12-24 hours

The resolution must be valid JSON matching the schema in
`claude_runner/prompts.py` (`GM_RESOLUTION_TEMPLATE`).

### Step 6: Apply Resolution

Save the resolution JSON to a temp file and apply it:

```bash
# Write resolution to temp file first, then:
python3 claude_runner/game_state.py apply --game-dir <GAME_DIR> --resolution /tmp/round_N_resolution.json --round N
```

This runs `WorldState.apply_updates()` which includes cascading effects:
- Oil price affects public war support
- Sanctions increase EU gas prices
- Low supply degrades unit readiness
- Casualties reduce morale and strength
- Nuclear posture auto-escalation
- Infrastructure damage affects public opinion
- Refugee flows reduce government approval
- NATO alert auto-escalation on Article 5

### Step 7: Print Round Summary

Summarise what happened for the user:
- Key military actions and outcomes
- Diplomatic developments
- Economic changes
- Public opinion shifts
- Any surprise developments
- Current corridor control status

## GM Rules Reference

### Combat Formula
```
attacker_eff = strength × (readiness/10) × air_mult × supply_mult
defender_eff = strength × (readiness/10) × terrain_mult × supply_mult
```
- air_mult: 1.3 with air superiority, 1.0 without
- terrain_mult: 1.2 for forest/urban/mountains, 1.0 otherwise
- supply_mult: 0.7 if supply_level < 3, 1.0 otherwise

### Public Opinion Gates
- war_support < 30%: NO offensive operations
- war_support < 50%: defensive only, no foreign deployments
- gov_approval < 25%: domestic crisis

### Nuclear Posture Levels
`peacetime → elevated → dispersal → launch_ready`

Nuclear detonations end the game.

## File Structure

```
claude_runner/
  __init__.py
  game_state.py    # CLI for state I/O
  prompts.py       # Prompt templates
CLAUDE.md          # This file (auto-read by Claude Code)
presets.py         # Includes suwalki-claude preset
engine/
  world_state.py   # WorldState, apply_updates(), cascading effects
  checkpoint.py    # save_checkpoint(), load_checkpoint()
  round_logger.py  # RoundLogger
```

## Rate Limit Strategy

Each round uses ~15 Claude Code messages (~300K total tokens):
- 1 briefing load + 1 GM briefing write
- 8 country context loads (can run in parallel as bash calls)
- 8 Task agents for country deliberation (parallel)
- 1 GM resolution
- 1 apply command

With Claude Max you can comfortably run 4-6 rounds per 5-hour window.
Run 1-2 rounds per session, then resume later.

## Resuming a Game

Games auto-save after each round. To resume:

```bash
python3 claude_runner/game_state.py status --game-dir logs/game_XXXXX
```

Then: "Run round N" where N = round_completed + 1.

## Viewing Results

The existing viewer works with Claude Code games:

```bash
python3 run.py view logs/game_XXXXX
```
