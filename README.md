# WarGame: Suwalki Gap Crisis Simulation

## Overview

Multi-agent AI geopolitical wargame simulating a Suwalki Gap crisis between NATO and Russia. 20 countries, 30 internal factions, each powered by a local LLM running via Ollama. Every country has its own AI-driven decision-making process with internal faction debates, private intelligence, and autonomous action selection.

Based on real wargame scenarios and defense research: Die Welt/Hamburg 2026 tabletop exercise, RAND Corporation Baltic studies, NATO Steadfast Defender 2024, and Polish WINTER-20 exercises.

## Requirements

- **macOS** (tested on Mac Studio M2 Ultra 64GB)
- **Python 3.12+**
- **Ollama** (for local LLM inference)
- **~20GB free disk space** (for the AI model download)
- **Recommended: 64GB+ RAM** (for the 32B parameter model)

## Quick Start

Step-by-step setup:

```bash
# 1. Clone or copy the project
git clone <repo-url> && cd WarGame

# 2. Install Ollama
brew install ollama
# OR download from https://ollama.com/download

# 3. Start the Ollama server (in a separate terminal)
ollama serve

# 4. Pull the model (~20GB download, takes ~20 min on first run)
ollama pull deepseek-r1:32b

# 5. Create a Python virtual environment
python3 -m venv .venv

# 6. Install Python dependencies
.venv/bin/pip install -r requirements.txt

# 7. Run a quick test (4 countries, 2 rounds)
.venv/bin/python3 run.py --rounds 2 --countries PL RU US DE

# 8. Run the full game (20 countries, 10 rounds)
.venv/bin/python3 run.py
```

## Alternative: setup.sh

A convenience script that checks prerequisites, installs dependencies, and pulls the model:

```bash
chmod +x setup.sh && ./setup.sh
```

## CLI Options

```
--config PATH       Custom config file (default: config.yaml)
--rounds N          Override number of rounds
--backend NAME      "ollama" or "deepseek"
--model NAME        Override model (e.g. "llama3.3:70b", "qwen3:32b")
--countries XX YY   Only include specific countries by code
```

Available country codes: `PL` `RU` `US` `DE` `FR` `CN` `UA` `GB` `TR` `JP` `FI` `LT` `LV` `EE` `SE` `BY` `IN` `SA` `IL` `RS`

Examples:

```bash
# Quick 4-country test
.venv/bin/python3 run.py --rounds 2 --countries PL RU US DE

# Key NATO vs Russia players
.venv/bin/python3 run.py --rounds 5 --countries PL RU US DE FR GB LT

# Full game with a different model
.venv/bin/python3 run.py --model qwen3:32b

# Use DeepSeek cloud API
DEEPSEEK_API_KEY=your_key .venv/bin/python3 run.py --backend deepseek
```

## Project Structure

```
WarGame/
├── config.yaml              # Main configuration (backend, model, debate settings)
├── run.py                   # Entry point -- loads config, builds game, runs loop
├── setup.sh                 # One-step setup script
├── requirements.txt         # Python dependencies (aiohttp, pyyaml)
│
├── engine/                  # Core simulation engine
│   ├── game.py              # Main game loop (round orchestration)
│   ├── game_master.py       # GM agent (briefings, action resolution, narrative)
│   ├── world_state.py       # World model (military units, markets, public opinion)
│   └── round_logger.py      # JSON logging for each round
│
├── agents/                  # AI agent framework
│   ├── base.py              # Base agent class (LLM interaction)
│   ├── country.py           # Country agent (deliberation, decision-making)
│   └── faction.py           # Faction agent (internal debate positions)
│
├── backends/                # LLM backend adapters
│   ├── base.py              # Abstract backend interface
│   ├── ollama_backend.py    # Ollama local inference backend
│   └── deepseek_backend.py  # DeepSeek cloud API backend
│
├── countries/               # Country definition files (20 YAML files)
│   ├── poland.yaml          # Each file: name, code, alliances, factions,
│   ├── russia.yaml          #   military/economic strength, geographic relevance,
│   ├── usa.yaml             #   faction personalities, priorities, and red lines
│   └── ...                  #
│
├── scenarios/               # Scenario definitions
│   └── suwalki_gap.yaml     # Crisis scenario, initial event, world state
│
├── viewer/                  # Browser-based game viewer
│   └── index.html           # Dark-themed viewer for round-by-round replay
│
└── logs/                    # Game output (created at runtime)
    └── game_YYYYMMDD_HHMMSS/  # One directory per game session
        ├── round_01.json       # Full round data (debates, decisions, world state)
        ├── round_02.json
        └── ...
```

## How It Works

Each round follows a structured pipeline:

1. **GM Situation Briefing** -- The Game Master AI generates a narrative briefing describing the current state of the crisis, recent events, and intelligence reports.

2. **Private Intelligence** -- Each country receives tailored intelligence based on its alliances, geographic position, and capabilities. NATO members share certain intel; Russia and its allies see a different picture.

3. **Internal Faction Debate** (3 rounds) -- Each country's factions argue internally:
   - **Round 1: Position** -- Each faction states its recommended course of action.
   - **Round 2: Argument** -- Factions respond to each other, challenging assumptions and defending positions.
   - **Round 3: Synthesis** -- Factions attempt to find common ground or acknowledge irreconcilable differences.

4. **Unified Decision** -- The country agent synthesizes the faction debate into a single national decision, selecting concrete actions (diplomatic, military, economic, intelligence).

5. **Action Resolution** -- The Game Master resolves all 20 countries' actions simultaneously, determining outcomes, cascading effects, and narrative consequences. The world state updates: military units move, markets shift, public opinion changes, alliances strengthen or fracture.

6. **Logging** -- Every step is saved as structured JSON to `logs/game_YYYYMMDD_HHMMSS/`, including the full text of every faction debate, every decision, and every GM resolution.

Countries are processed sequentially because the local Ollama backend handles one request at a time. The DeepSeek cloud backend can parallelize API calls for faster execution.

## Viewing Results

Game logs are saved as JSON files in `logs/game_YYYYMMDD_HHMMSS/`.

**Using the built-in viewer:**

1. Open `viewer/index.html` in any modern browser.
2. Load the round JSON files to see debates, decisions, and world state changes.

**Using a local file server (for loading JSON files):**

```bash
.venv/bin/python3 -m http.server 8080 --directory logs/
```

Then navigate to `http://localhost:8080` and select a game session.

**Direct JSON inspection:**

Each `round_XX.json` file contains the complete round data: GM briefing, per-country faction debates, national decisions, action resolutions, and updated world state.

## Configuration

The `config.yaml` file controls the simulation:

```yaml
game:
  name: "Suwalki Gap Crisis"
  scenario: "scenarios/suwalki_gap.yaml"
  rounds: 10                          # Number of game rounds
  countries_dir: "countries"
  logs_dir: "logs"

llm:
  backend: "ollama"                   # "ollama" or "deepseek"

  ollama:
    base_url: "http://localhost:11434"
    model: "deepseek-r1:32b"
    temperature: 0.7                  # Higher = more creative/unpredictable
    timeout: 300                      # Seconds per LLM call

  deepseek:
    base_url: "https://api.deepseek.com/v1"
    model: "deepseek-reasoner"
    temperature: 0.7

debate:
  rounds: 3                           # Internal faction debate rounds
  max_tokens_per_response: 500        # Token limit per faction response

game_master:
  max_tokens: 2000                    # GM gets more tokens for resolution
```

## Using Different Models

| Model | RAM Needed | Quality | Speed | Command |
|---|---|---|---|---|
| `deepseek-r1:32b` | ~24GB | Best reasoning | 15-22 tok/s | `ollama pull deepseek-r1:32b` |
| `qwen3:32b` | ~24GB | Good general | 15-22 tok/s | `ollama pull qwen3:32b` |
| `llama3.3:70b-q4` | ~48GB | Great quality | 8-12 tok/s | `ollama pull llama3.3:70b` |
| `deepseek-r1:14b` | ~12GB | Decent | 25-35 tok/s | `ollama pull deepseek-r1:14b` |

To use a different model:

```bash
# Via CLI flag
.venv/bin/python3 run.py --model qwen3:32b

# Or edit config.yaml
# llm.ollama.model: "qwen3:32b"
```

## Using DeepSeek API (Cloud)

For much faster execution using the DeepSeek cloud API:

```bash
# Set your API key
export DEEPSEEK_API_KEY=your_api_key_here

# Run with the cloud backend
.venv/bin/python3 run.py --backend deepseek
```

- **Cost:** approximately $2-3 for a full 10-round, 20-country game.
- **Speed:** significantly faster than local inference thanks to parallel API calls.
- **Model:** uses `deepseek-reasoner` (or `deepseek-chat`) on DeepSeek's servers.

Get an API key at [https://platform.deepseek.com](https://platform.deepseek.com).

## Countries and Factions

The simulation includes 20 countries, each with 1-3 AI-driven internal factions that debate before producing a unified national decision.

### NATO / Western Bloc

| Country | Code | Factions | Nuclear |
|---|---|---|---|
| **Poland** | `PL` | President & MON (hawk), Prime Minister & MSZ (diplomat), General Staff (military realist) | No |
| **United States** | `US` | White House / NSC (pragmatist), Pentagon & EUCOM (military realist) | Yes |
| **Germany** | `DE` | Chancellor & BKA (pragmatist), Bundeswehr Leadership (military realist) | No |
| **France** | `FR` | Elysee Palace (pragmatist), Military / Etat-Major (military realist) | Yes |
| **United Kingdom** | `GB` | Prime Minister & FCDO (hawk), Military / Defence Staff (military realist) | Yes |
| **Lithuania** | `LT` | President & National Defence Council (hawk) | No |
| **Latvia** | `LV` | President & Cabinet (hawk) | No |
| **Estonia** | `EE` | President & Government (hawk) | No |
| **Finland** | `FI` | President & Security Committee (hawk) | No |
| **Sweden** | `SE` | Prime Minister & Government (diplomat) | No |

### Russia and Allies

| Country | Code | Factions | Nuclear |
|---|---|---|---|
| **Russia** | `RU` | Kremlin (hardliner), General Staff (military realist), FSB (wildcard) | Yes |
| **Belarus** | `BY` | Lukashenko & Presidential Administration (pragmatist) | No |
| **Serbia** | `RS` | President & Security Services (wildcard) | No |

### Non-Aligned / Global Players

| Country | Code | Factions | Nuclear |
|---|---|---|---|
| **China** | `CN` | CCP Central Committee / Xi Jinping (pragmatist), PLA (military realist) | Yes |
| **Ukraine** | `UA` | President & National Security Council (hawk), Armed Forces / ZSU (military realist) | No |
| **Turkey** | `TR` | President Erdogan & AKP Inner Circle (wildcard) | No |
| **Japan** | `JP` | Prime Minister & National Security Secretariat (diplomat) | No |
| **India** | `IN` | Prime Minister & Ministry of External Affairs (pragmatist) | Yes |
| **Saudi Arabia** | `SA` | Crown Prince MBS & Royal Court (pragmatist) | No |
| **Israel** | `IL` | Prime Minister & Security Cabinet (pragmatist) | Yes |

**Faction roles explained:**
- **Hawk** -- Favors strong, immediate action; low tolerance for ambiguity.
- **Diplomat** -- Prioritizes negotiation, coalition-building, and de-escalation.
- **Pragmatist** -- Weighs costs and benefits; transactional decision-making.
- **Military realist** -- Focuses on operational capability, readiness, and tactical feasibility.
- **Hardliner** -- Committed to maximalist objectives; views compromise as weakness.
- **Wildcard** -- Unpredictable; may act on ideology, opportunism, or domestic pressure.

## Estimated Run Times

| Configuration | Countries | Rounds | Time (Ollama) | Cost |
|---|---|---|---|---|
| Quick test | 4 | 2 | ~15 min | $0 (local) |
| Medium | 7 key players | 5 | ~1.5 hrs | $0 (local) |
| Full game | 20 | 10 | ~3 hrs | $0 (local) |
| DeepSeek API | 20 | 10 | ~15 min | ~$2-3 |

Times measured with `deepseek-r1:32b` on a Mac Studio M2 Ultra (64GB RAM). Actual times depend on hardware, model size, and token limits.

## Customization

**Add a new country:**
Create a new YAML file in `countries/` following the existing format. Include `name`, `code`, `alliances`, `military_strength`, `economic_strength`, `nuclear`, `geographic_relevance`, and one or more `factions` with `name`, `role`, `personality`, and `priorities`.

**Modify the scenario:**
Edit `scenarios/suwalki_gap.yaml` to change the crisis description, background, initial event, or initial world state (military positions, economic conditions, public opinion).

**Adjust faction personalities:**
Edit the `personality` and `priorities` fields in any country YAML to change how that faction argues and what it values.

**Create a new scenario:**
Copy `scenarios/suwalki_gap.yaml`, modify the crisis setting, and point `config.yaml` at the new file:
```yaml
game:
  scenario: "scenarios/your_new_scenario.yaml"
```

**Change debate depth:**
In `config.yaml`, adjust `debate.rounds` (default: 3) and `debate.max_tokens_per_response` (default: 500) to make faction debates shorter or longer.

## Based on Real Research

This simulation draws from actual wargame exercises and defense studies:

- **Die Welt / Hamburg Wargame (February 2026)** -- Civilian participants simulating NATO decision-making found Russia could hold NATO territory for 3 days before a coherent alliance response materialized.
- **RAND Corporation (2014-2016)** -- Multiple studies concluded that Russia could reach the Baltic state capitals in 36-60 hours, and that NATO would need months to assemble a credible counterforce.
- **Polish WINTER-20 Exercise (2021)** -- Poland's own wargame showed Polish frontline forces being destroyed within 5 days in a high-intensity conflict scenario.
- **NATO Steadfast Defender 2024** -- The largest NATO exercise since the Cold War (90,000 troops across 31 nations), specifically designed to rehearse reinforcement of the Baltic region and the Suwalki corridor.

The Suwalki Gap -- a 65km land corridor between Poland and Lithuania, flanked by Russian Kaliningrad and Belarus -- is widely considered NATO's most vulnerable point and the most likely flashpoint for a direct NATO-Russia confrontation.

## License

MIT
