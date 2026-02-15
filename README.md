# Multi-Agent Simulation Engine (WarGame)

**Experimental distributed multi-agent reasoning framework for geopolitical crisis modeling.**

An open-source system that orchestrates multiple AI agents to simulate complex international scenarios. Each country contains 2-4 faction agents that internally debate policy, then synthesize unified decisions. The system resolves conflicts deterministically and tracks cascading effects across military, economic, and political dimensions.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🔬 What This Is

A research framework for studying emergent behavior in multi-agent systems under resource constraints and incomplete information. The system:

- **Orchestrates 8 parallel agents** (batched by strategic interest)
- **Enforces narrative consistency** through game master arbitration
- **Applies cascading effects** (oil prices → war support, casualties → morale)
- **Tracks 66 countries** with asymmetric capabilities and faction diversity
- **Generates deterministic outcomes** using combat formulas and public opinion gates

Primary test scenario: **Suwalki Gap Crisis** (Baltic escalation chain).

---

## 🏗️ Architecture

```
Country Agents (parallel)
    ↓
Faction Debates (3 rounds each)
    ↓
Game Master Resolution
    ↓
World State Updates (cascading effects)
    ↓
Checkpoint (JSON logs)
    ↓
Static Web Viewer (no backend)
```

**For detailed architecture, see [ARCHITECTURE.md](analysis/ARCHITECTURE.md)**

---

## ⚡ Quick Start

### Prerequisites

- Python 3.12+
- Ollama (local LLM) or DeepSeek API key
- 64GB RAM for deepseek-r1:32b

### Installation

```bash
git clone https://github.com/RomanTsisyk/multi-agent-simulation-engine.git
cd multi-agent-simulation-engine

pip install -r requirements.txt
ollama pull deepseek-r1:32b  # Or use DeepSeek API
python run.py preflight
```

### Run Simulation

```bash
# Quick (4 countries, 3 rounds)
python run.py play --preset quick

# Medium (10 countries, 5 rounds)
python run.py play --preset medium

# Full (20 countries, 10 rounds)
python run.py play --preset full
```

### View Results

**Live Demo** (5 pre-recorded games):
```
https://roman-tsisyk.com/viewer_static_demo/production.html
```

**Local Analytics**:
```bash
python run.py view logs/game_TIMESTAMP/
```

---

## 📊 Demo Viewer

No backend required. Static HTML/JS viewer with:
- Real-time charts (oil prices, nuclear posture, war support, military balance)
- Country decision logs with faction reasoning
- Combat results and cascading effects
- Full JSON state export

Runs on GitHub Pages via `/viewer_static_demo/`.

---

## 🎮 Game Mechanics

- **Combat formula**: Strength × Readiness × Force multipliers
- **Nuclear escalation**: peacetime → elevated → dispersal → launch_ready
- **Public opinion gates**: War support determines military action legality
- **Cascading effects**: Oil price shocks, sanctions impact, refugee flows

**See [GAME_MECHANICS.md](analysis/GAME_MECHANICS.md) for full specifications.**

---

## 🔧 Documentation

- **[ARCHITECTURE.md](analysis/ARCHITECTURE.md)** - System design and component overview
- **[DESIGN.md](analysis/DESIGN.md)** - Architectural decision rationale
- **[TECHNICAL.md](analysis/TECHNICAL.md)** - Implementation details and API reference
- **[GAME_MECHANICS.md](analysis/GAME_MECHANICS.md)** - Combat formulas, escalation ladder, cascading effects
- **[CLAUDE.md](CLAUDE.md)** - Claude Code runner protocol

---

## 📁 File Structure

```
engine/
  ├── game.py              # Round orchestration
  ├── world_state.py       # State management
  ├── game_master.py       # Combat resolution
  └── checkpoint.py        # Save/load
agents/
  ├── country.py           # Country orchestration
  └── faction.py           # Faction debates
backends/
  ├── ollama_backend.py
  └── deepseek_backend.py
scenarios/                 # YAML scenario definitions
countries/                 # YAML country configs (66)
viewer_static_demo/        # Web viewer + demo data
claude_runner/             # Claude Code integration
tests/                     # Unit test suite
```

---

## 🚀 Development

### Testing

```bash
pip install pytest pytest-asyncio pytest-cov
pytest --cov=engine,agents,backends
```

### Code Style

```bash
ruff check .
mypy engine/ agents/ backends/
```

### Configuration

Edit `config.yaml`:
```yaml
game:
  scenario: "suwalki"
  num_countries: 20
  max_rounds: 10

backend:
  type: "deepseek"
  model: "deepseek-r1:32b"
  max_concurrent: 10
```

---

## 🧠 Agent System

Each country contains independent faction agents that debate before deciding:

1. **Initial Position** - Faction states opening argument
2. **Rebuttal** - Respond to other factions
3. **Synthesis** - Move toward consensus

**Faction Types**: Hawk, Dove, Diplomat, Military Realist, Pragmatist

Weight by phase (escalation vs negotiation). See countries/*.yaml for examples.

---

## 🎯 Design Principles

- **Multi-agent reasoning** over monolithic decisions
- **Asymmetric capabilities** (not all countries equal)
- **Narrative consistency** enforced by game master
- **Deterministic resolution** (reproducible outcomes)
- **Cascading effects** (not isolated decisions)
- **Static deployment** (no backend required)

---

## 📈 Performance

| Scenario | Countries | Rounds | LLM Calls | Time |
|----------|-----------|--------|-----------|------|
| Quick | 4 | 3 | 60 | ~15 min |
| Medium | 10 | 5 | 150 | ~45 min |
| Full | 20 | 10 | 600 | ~3 hours |

Backend comparison:
- **Ollama (local)**: Free, slow, privacy-preserving
- **DeepSeek API**: Fast, $0.50-3/game, parallel queries

---

## 🧪 Testing & Reproducibility

Games are deterministic given same LLM and seed. All game logs saved as JSON:

```
logs/game_20260215_123456/
├── round_001.json
├── round_002.json
└── ...
```

Each round contains:
- World state before/after
- All country decisions
- Combat results
- Headlines & surprises

Fully analyzable post-hoc without re-running simulation.

---

## 📖 Citation

If using this framework for research:

```bibtex
@software{wargame2026,
  author = {Tsisyk, Roman},
  title = {Multi-Agent Simulation Engine (WarGame)},
  year = {2026},
  url = {https://github.com/RomanTsisyk/multi-agent-simulation-engine}
}
```

---

## 📜 License

MIT License - see LICENSE file.

---

## 🤝 Contributing

Priority areas:
- New scenarios (Taiwan Strait, Arctic sovereignty)
- Missing countries (Taiwan, Hungary, Romania configs)
- Test coverage expansion
- Backend optimization (inference batching)

---

**Built with OpenAI/Anthropic APIs, Ollama, and community feedback.**
