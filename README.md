# WarGame: LLM-Powered Geopolitical Simulation

**A sophisticated multi-agent wargaming system where AI-powered factions debate internal policy before making decisions.**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 What Is This?

WarGame simulates geopolitical crises using Large Language Models (LLMs) to drive realistic decision-making. Unlike traditional wargames where countries make monolithic choices, **each country contains multiple AI-powered factions** (hawks, doves, diplomats, military realists) that:

1. **Debate internally** over 3 rounds (initial position → rebuttal → synthesis)
2. **Argue with each other** citing historical precedents and strategic concerns
3. **Synthesize** a unified decision weighted by faction influence

This creates **emergent, narrative-driven gameplay** where political dynamics matter as much as military strength.

### Key Features

- **🎭 Multi-Faction Debates**: Each country has 2-4 factions with distinct personalities and priorities
- **🌍 66 Countries Modeled**: From major powers (US, Russia, China) to regional actors (Poland, Turkey, Baltic states)
- **⚛️ Nuclear Escalation Ladder**: Realistic posture levels (peacetime → elevated → launch_ready)
- **🎲 Cascading Effects**: Oil prices affect public opinion, casualties reduce morale, sanctions trigger economic responses
- **📊 Rich Analytics**: Post-game analysis with turning points, faction influence charts, and timeline visualization
- **🔧 Extensible**: YAML-based scenarios and country configs, pluggable LLM backends (Ollama, DeepSeek)

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **Ollama** (for local LLM) or **DeepSeek API key** (for cloud LLM)
- **64GB RAM recommended** for deepseek-r1:32b model

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/wargame.git
cd wargame

# Install Python dependencies
pip install -r requirements.txt

# Install Ollama (macOS/Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Pull AI model (20GB download, takes 10-30 minutes)
ollama pull deepseek-r1:32b

# Verify installation
python run.py preflight
```

### Run Your First Game

```bash
# Quick game (4 countries, 3 rounds, ~15 minutes)
python run.py play --preset quick

# Medium game (10 countries, 5 rounds, ~45 minutes)
python run.py play --preset medium

# Full game (20 countries, 10 rounds, ~3 hours)
python run.py play --preset full
```

### View Results

```bash
# Start web viewer
python serve.py

# Open browser to http://localhost:8080
# Select your game from the list
```

---

## 📖 How It Works

### Game Loop

```
Round Start → Countries Deliberate → GM Resolves → Update World State → Check End Conditions
                      ↓
        Faction Debate (3 rounds) → Synthesis → Decision
```

### Example: Poland's Internal Debate

**Round 1 - Initial Positions**
- **President (Hawk)**: "We must attack NOW. Every hour strengthens Russian positions. 1939 taught us appeasement fails!"
- **PM (Diplomat)**: "Fracturing NATO is worse than losing the corridor. We need Article 5 consensus."
- **General Staff (Realist)**: "Force ratio is 1.4:1 against us. We need 24h for US reinforcements."

**Round 2 - Rebuttals**
- President: "General, we won't GET 24 hours. Russia will dig in."
- PM: "President, unilateral action means Germany blocks Article 5."
- General: "PM, Germany already hesitates. Diplomacy buys nothing."

**Round 3 - Synthesis**
Poland chooses PM's approach: Diplomatic pressure + 48h ultimatum + covert mobilization.

**Result**: Decision is shaped by faction weights (President=3.0, PM=2.0, General=2.5 in conventional war phase).

---

## 🗂️ Scenarios

### Included Scenario: Suwalki Gap Crisis

**Premise**: Russia seizes the Suwalki corridor (Poland-Lithuania border), cutting off Baltic states from NATO. Poland must decide whether to counter-attack, invoke Article 5, or negotiate.

**Victory Conditions**:
- **Russian Victory**: Hold corridor for 6 rounds (3 days)
- **NATO Victory**: Liberate corridor
- **Diplomatic Resolution**: Negotiated ceasefire
- **Catastrophic**: Nuclear weapon detonation

**Key Actors**: Poland, Russia, USA, Germany, UK, France, Lithuania, Latvia, Estonia, Belarus, China (observer)

---

## ⚙️ Configuration

### YAML-Based Scenarios

Create custom scenarios in `scenarios/` directory:

```yaml
name: "Taiwan Strait Crisis 2027"
description: "China announces 72h reunification deadline..."

participants:
  - US
  - CN
  - TW
  - JP

initial_state:
  corridor_control: "contested"  # or "russian", "nato"
  nuclear_posture:
    US: "elevated"
    CN: "peacetime"

victory_conditions:
  - id: "chinese_victory"
    type: "territorial"
    description: "China controls Taiwan"
    threshold_rounds: 10
```

### Country Configurations

Each country in `countries/` has:

```yaml
name: "Poland"
code: "PL"
military_strength: 5  # 1-10 scale
economic_strength: 6
nuclear: false

factions:
  - name: "President & National Security Council"
    role: "hawk"  # hawk, dove, diplomat, military_realist, pragmatist, wildcard
    personality: "References 1939 constantly, sees Russian aggression as existential threat..."
    priorities:
      - "Defend Polish territory"
      - "Invoke Article 5"
    red_lines:
      - "Will not accept Russian control of Polish soil"
```

---

## 🧪 Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=engine,agents,backends --cov-report=html

# Run specific test file
pytest tests/test_fixes.py -v
```

---

## 🔧 Architecture

```
wargame/
├── engine/           # Core game logic
│   ├── game.py       # Main game loop, orchestration
│   ├── world_state.py  # Global state management
│   ├── game_master.py  # GM agent (resolves actions)
│   └── analytics.py    # Post-game analysis
├── agents/           # AI agents
│   ├── country.py    # Country-level agent (orchestrates factions)
│   └── faction.py    # Faction-level agent (debates)
├── backends/         # LLM integrations
│   ├── ollama_backend.py    # Local Ollama
│   └── deepseek_backend.py  # Cloud DeepSeek API
├── scenarios/        # YAML scenario definitions
├── countries/        # YAML country configurations (66 files)
├── utils/            # JSON parsing, logging
└── viewer/           # Web-based game viewer
```

**See [TECHNICAL.md](analysis/TECHNICAL.md) for detailed architecture documentation.**

---

## 🎨 UI/UX Roadmap

A comprehensive UI is in development. See [UI_UX_CONCEPT.md](analysis/UI_UX_CONCEPT.md) for:

- Real-time War Room Dashboard
- Player Mode (human controls one country)
- Visual Scenario Editor
- Post-game analytics with timeline viz

**Status**: Concept complete, implementation planned for Q2 2026.

---

## 🐛 Known Issues & Fixes

Recent bug fixes (2026-02-13):

✅ **Nuclear Posture Fix**: Separated nuclear readiness from actual weapon use. Countries can now escalate to `launch_ready` without ending the game.

✅ **Corridor Control Fix**: Replaced fragile substring matching with regex word boundaries and confidence scoring.

✅ **Test Coverage**: Added pytest infrastructure and basic test suite.

**See [analysis/problems.md](analysis/problems.md) for full issue tracker.**

---

## 📊 Performance

### Typical Game Stats

- **Quick Game**: 4 countries × 3 rounds = ~60 LLM calls = 15 minutes
- **Medium Game**: 10 countries × 5 rounds = ~150 LLM calls = 45 minutes
- **Full Game**: 20 countries × 10 rounds = ~600 LLM calls = 3 hours

### LLM Backend Comparison

| Backend | Speed | Cost | Parallel | Best For |
|---------|-------|------|----------|----------|
| Ollama (local) | Slow | Free | No | Development, privacy |
| DeepSeek API | Fast | ~$3/game | Yes | Production, speed |

**Tip**: Use `--backend deepseek` with `max_concurrent: 10` in `config.yaml` for 5-10x speedup.

---

## 🤝 Contributing

Contributions welcome! Priority areas:

1. **New Scenarios**: Taiwan Strait, Arctic Sovereignty, Middle East escalation
2. **Missing Countries**: Taiwan, Hungary, Romania configs
3. **Test Coverage**: Expand from 40% to 80%
4. **UI Implementation**: React dashboard (see UI_UX_CONCEPT.md)

**Development setup**:

```bash
# Install dev dependencies
pip install -r requirements.txt pytest pytest-asyncio ruff mypy

# Run linter
ruff check .

# Run type checker
mypy engine/ agents/ backends/
```

---

## 📚 Educational Use

WarGame is designed for:

- **University Courses**: International Relations, Security Studies, Game Theory
- **Think Tanks**: Scenario planning, red team exercises
- **Policy Training**: Crisis decision-making simulations

**Licensing**: MIT License allows commercial and educational use. For bulk educational licensing, contact the maintainers.

---

## 📜 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

Inspired by:
- RAND Corporation's wargaming studies on Baltic defense
- Academic research on crisis escalation dynamics
- Professional wargaming community feedback

Built with:
- [Ollama](https://ollama.com) - Local LLM runtime
- [DeepSeek](https://www.deepseek.com) - Cloud LLM API
- [aiohttp](https://docs.aiohttp.org) - Async HTTP
- [PyYAML](https://pyyaml.org) - Config parsing

---

## 📞 Contact & Support

- **Documentation**: [TECHNICAL.md](analysis/TECHNICAL.md) for architecture details
- **Bug Reports**: [GitHub Issues](https://github.com/yourusername/wargame/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/wargame/discussions)

---

**Made with ☢️ and ☮️ by the WarGame team**
