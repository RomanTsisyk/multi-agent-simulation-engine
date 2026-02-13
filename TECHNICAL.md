# WarGame Technical Documentation

**Comprehensive architecture guide for developers, contributors, and researchers.**

---

## 🏗️ System Architecture

### High-Level Overview

```
┌──────────────┐
│   User CLI   │  python run.py play
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│      Game Engine (game.py)           │  ← Main orchestrator
│  ┌────────────────────────────────┐  │
│  │ Round Loop                     │  │
│  │ 1. Briefing (WorldState →     │  │
│  │              Countries)        │  │
│  │ 2. Deliberation (Countries     │  │
│  │                  → Decisions)  │  │
│  │ 3. Resolution (GM → Updates)   │  │
│  │ 4. Apply Updates (WorldState)  │  │
│  │ 5. Check End Conditions        │  │
│  └────────────────────────────────┘  │
└────┬─────────────────────────────────┘
     │
     ├──► GameMaster (GM Agent)  ──► LLM Backend (Ollama/DeepSeek)
     │
     ├──► Country Agents (×20)   ──► Faction Agents (×2-4 each)
     │
     └──► WorldState (Global State)
```

---

## 🧩 Core Components

### 1. Game Engine (`engine/game.py`)

**Responsibility**: Main game loop orchestration

**Key Methods**:
- `run_round()`: Execute one complete round
- `_deliberate_sequential()`: Process countries one-by-one (Ollama)
- `_deliberate_parallel()`: Process countries concurrently (DeepSeek API)
- `check_end_conditions()`: Evaluate victory/catastrophe conditions
- `_update_corridor_control()`: Infer territorial control from GM narrative

**State Management**:
```python
class Game:
    world_state: WorldState          # Global state
    countries: dict[str, Country]    # Country agents
    game_master: GameMaster          # GM agent
    backend: LLMBackend              # LLM provider
    _diplomatic_inbox: list[dict]    # Cross-country messages
```

**Design Pattern**: Orchestrator pattern - delegates to agents but controls flow

---

### 2. WorldState (`engine/world_state.py`)

**Responsibility**: Global state container + mutation logic

**Data Structure**:
```python
@dataclass
class WorldState:
    # Metadata
    round_number: int
    game_time: str  # "Day 2, 12:00"

    # Military
    military_units: list[MilitaryUnit]
    military_alerts: dict[str, str]  # country → alert_level

    # Economic
    markets: dict[str, Any]  # oil_price, euro_usd, etc.
    sanctions: list[dict]
    trade_disruptions: list[str]

    # Diplomatic
    diplomatic_relations: dict[str, dict[str, int]]  # -10 to +10
    treaties_invoked: list[str]
    un_resolutions: list[str]

    # NATO
    nato_alert_level: str
    nato_consensus: dict[str, str]  # country → position

    # Territorial
    corridor_control: str  # russian, nato, contested

    # Nuclear (FIX 2026-02-13)
    nuclear_posture: dict[str, str]  # peacetime → elevated → launch_ready
    nuclear_detonations: list[dict]  # Actual use (game-ending)

    # Public opinion
    public_opinion: dict[str, dict]  # war_support, government_approval

    # Humanitarian
    refugee_flows: list[dict]
    humanitarian_crisis_level: dict[str, int]

    # Cyber
    cyber_operations: list[dict]
    infrastructure_status: dict[str, dict[str, int]]

    # Narrative
    recent_events: list[str]
    media_headlines: list[str]
```

**Cascading Effects** (`_apply_cascading_effects()`):
Automatically applies second-order consequences:
1. Oil price → public opinion (high prices reduce war support)
2. Sanctions → gas prices (Russia sanctions raise EU gas costs)
3. Supply degradation (units without supply lose readiness)
4. Casualties → morale → strength (losses degrade unit effectiveness)
5. Infrastructure damage → government approval
6. Refugee burden → host country approval
7. Nuclear escalation → peer auto-escalation
8. NATO alert → member mobilization
9. Nuclear de-escalation (when provocations cease)

**Design Pattern**: Data class with behavior (CQRS-like: commands via `apply_updates()`, queries via `to_briefing()`)

---

### 3. Country Agent (`agents/country.py`)

**Responsibility**: Orchestrate internal faction debate → synthesize decision

**Deliberation Flow**:
```
1. Receive briefing from WorldState
2. Conduct 3-round faction debate:
   Round 1: Each faction states initial position
   Round 2: Factions argue/rebut each other
   Round 3: Factions give final statements
3. Synthesis: Weighted average of faction positions
4. Generate structured decision (actions, diplomatic messages)
```

**Faction Weighting by Crisis Phase**:
```python
def _compute_faction_weights(self, crisis_phase: str):
    # crisis_phase: diplomatic, hybrid, conventional, nuclear

    weights = {}
    for faction in self.factions:
        base_weight = 1.0

        if crisis_phase == "diplomatic":
            if faction.role == "diplomat": base_weight *= 2.0
            if faction.role == "hawk": base_weight *= 0.7

        elif crisis_phase == "conventional":
            if faction.role == "military_realist": base_weight *= 3.0
            if faction.role == "dove": base_weight *= 0.5

        elif crisis_phase == "nuclear":
            if faction.role == "pragmatist": base_weight *= 2.5
            if faction.role == "hawk": base_weight *= 0.3  # Suppress hawks near nuclear

        weights[faction.name] = base_weight

    return weights
```

**Output Format** (JSON):
```json
{
  "country": "PL",
  "decision": "Launch counterattack with 11th Cavalry Division",
  "actions": [
    "Military mobilization order: 11th Cav to Suwalki",
    "Invoke NATO Article 5",
    "Request US 2nd Cavalry support"
  ],
  "diplomatic_messages": [
    {
      "to": "US",
      "channel": "private",
      "message": "We need your public commitment to Article 5 NOW"
    }
  ],
  "rationale": "President's position won due to time pressure and 1939 historical parallels"
}
```

**Design Pattern**: Agent pattern (autonomous decision-making)

---

### 4. Faction Agent (`agents/faction.py`)

**Responsibility**: Represent one political faction within a country

**Personality-Driven Prompts**:
```python
system_prompt = f"""
You are the {self.name} faction in {country_name}.

Your role: {self.role}  # hawk, dove, diplomat, military_realist, etc.

Your personality:
{self.personality}  # Multi-paragraph character description

Your priorities (in order):
{self.priorities}  # List of goals

Your red lines (will not cross):
{self.red_lines}  # List of unacceptable outcomes

Given the current situation, what is your position on the decision at hand?
Argue from YOUR perspective, not a neutral view.
"""
```

**Debate Rounds**:
- **Round 1**: Generate initial position (250-500 tokens)
- **Round 2**: Read other factions' positions, generate rebuttal (250-500 tokens)
- **Round 3**: Read rebuttals, generate final statement (250-500 tokens)

**Example Output** (Round 1):
```
As President of Poland, I cannot overstate the urgency of this moment.
History teaches us - 1939, when we waited for French and British help
that came too late. Every hour Russian forces dig in makes liberation
exponentially harder. Article 5 is not a suggestion, it's a GUARANTEE.
Germany's hesitation is unconscionable. I propose immediate counterattack
with 11th Cavalry Division, supported by US 2nd Cavalry when they arrive.
If NATO won't defend us, we defend ourselves.
```

**Design Pattern**: Actor model (each faction is independent agent)

---

### 5. Game Master (`engine/game_master.py`)

**Responsibility**: Resolve all country actions → world state updates

**Input**: List of country decisions

**Output**: Resolution (JSON)
```json
{
  "narrative": "Poland's 11th Cavalry Division clashes with Russian forces...",
  "events": [
    "Polish counterattack begins at 06:00",
    "Russia reinforces with BTG-14 from Kaliningrad",
    "Germany announces internal debate on Article 5"
  ],
  "headlines": [
    "BREAKING: Poland attacks Russian positions in Suwalki",
    "NATO emergency meeting called"
  ],
  "world_state_updates": {
    "military_units_update": [
      {"name": "polish_11th_cav", "readiness": 8, "casualties": 45}
    ],
    "corridor_control": "contested",  # FIX: Explicit structured field
    "public_opinion": {
      "PL": {"war_support": 87, "government_approval": 75}
    }
  }
}
```

**Validation** (`_validate_resolution()`):
- Clamps numeric values to valid ranges (strength 1-10, readiness 1-10)
- Removes invalid units
- Ensures required fields present
- Logs warnings but doesn't fail (graceful degradation)

**Design Pattern**: Mediator pattern (resolves conflicts between agents)

---

## 🤖 LLM Integration

### Backend Abstraction

```python
class LLMBackend(ABC):
    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Generate LLM response."""
        pass

    @property
    @abstractmethod
    def supports_parallel(self) -> bool:
        """Whether backend can handle concurrent requests."""
        pass
```

### Ollama Backend (`backends/ollama_backend.py`)

**Characteristics**:
- Local execution (privacy, no API costs)
- Sequential only (`supports_parallel = False`)
- Slower (10-30s per call on M2 Ultra)
- No rate limiting needed

**HTTP Communication**:
```python
async with session.post(
    f"{self.base_url}/api/chat",
    json={
        "model": self.model_name,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": self.num_ctx,  # Context window
            "num_predict": max_tokens,
        }
    },
    timeout=ClientTimeout(total=self.timeout)
) as resp:
    data = await resp.json()
    return data["message"]["content"]
```

**Retry Logic**: Exponential backoff on 5xx errors, max 3 attempts

---

### DeepSeek Backend (`backends/deepseek_backend.py`)

**Characteristics**:
- Cloud API (requires API key)
- Parallel execution (`supports_parallel = True`, semaphore-limited)
- Faster (2-5s per call)
- Costs ~$0.001/1K tokens

**Concurrent Control**:
```python
self._semaphore = asyncio.Semaphore(self.max_concurrent)  # Default: 10

async def generate(...):
    async with self._semaphore:  # Limit to 10 simultaneous calls
        # Make API call
```

**API Format** (OpenAI-compatible):
```python
payload = {
    "model": "deepseek-reasoner",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ],
    "temperature": temperature,
    "max_tokens": max_tokens
}
headers = {"Authorization": f"Bearer {self.api_key}"}
```

---

### JSON Parsing (`utils/json_parser.py`)

**Challenge**: LLMs frequently produce malformed JSON

**Robustness Strategies**:
1. **Markdown fence removal**: Strip ```json...```
2. **Thinking block removal**: Strip <think>...</think>
3. **Brace matching**: Extract {first_brace...matching_last_brace}
4. **Trailing comma removal**: Fix common syntax errors
5. **Single quote replacement**: Replace 'key' with "key"
6. **Fallback wrapper**: Return {_raw: text} on total failure

**Example**:
```python
llm_output = '''
<think>I should respond with structured data</think>
Here's my decision:
```json
{
  "actions": ["attack", "defend",],
  'priority': 'high',
}
```
'''

# Parser extracts and fixes:
# 1. Remove <think> block
# 2. Extract JSON from markdown fence
# 3. Remove trailing comma after "defend"
# 4. Replace 'priority' with "priority"
# Result: {"actions": ["attack", "defend"], "priority": "high"}
```

---

## 🎲 Game Mechanics Deep Dive

### Nuclear Escalation Ladder (Fixed 2026-02-13)

**Before Fix**: `tactical_use` was both a posture AND game-ending condition
**After Fix**: Separated posture from actual use

**Posture Levels** (readiness, NOT use):
1. **peacetime**: Normal operations
2. **elevated**: Increased monitoring, alert levels raised
3. **dispersal**: Forces dispersed, command posts activated
4. **launch_ready**: Weapons armed, authorization codes active

**Actual Detonations** (tracked separately):
```python
nuclear_detonations: list[dict] = [
    {
        "country": "RU",
        "type": "tactical",  # or "strategic"
        "target": "Suwalki corridor",
        "yield_kt": 10,  # kilotons
        "round": 5
    }
]
```

**Game ends** ONLY when `len(nuclear_detonations) > 0`

**Auto-Escalation Logic**:
- If any country reaches `dispersal` or higher, all nuclear states escalate one level
- De-escalation occurs after 3 rounds with no provocations
- Prevents runaway escalation while maintaining tension

---

### Corridor Control Detection (Fixed 2026-02-13)

**Before Fix**: Simple substring matching (`"seized" in text`)
**After Fix**: Regex with word boundaries + confidence scoring

**Detection Priority**:
1. **Explicit field** (if GM provides): `world_state_updates.corridor_control = "nato"`
2. **Text analysis** (fallback): Regex patterns with confidence weights

**Pattern Examples**:
```python
# High confidence (weight 1.0)
r'\brussian\s+(forces\s+)?control\b.*\b(corridor|suwalki)'

# Medium confidence (weight 0.8)
r'\bcorridor\s+secured\b.*\brussia'

# Contested (weight 1.0)
r'\b(fighting|combat|battle)\s+(continues|ongoing)\b.*\bcorridor'
```

**Threshold**: Require minimum confidence 0.7 to change state

---

### Cascading Effects Examples

**1. Oil Price → Public Opinion**
```python
oil_price = world_state.markets.get("oil_price", 85)
if oil_price >= 120:
    threshold = ((oil_price - 100) // 20) * 20  # Round to 20, 40, 60...
    if threshold not in self._oil_penalty_applied:
        penalty = min(5, (oil_price - 100) // 20)
        for country in self.public_opinion:
            self.public_opinion[country]["war_support"] -= penalty * 3
        self._oil_penalty_applied.add(threshold)
```

**2. Casualties → Morale → Strength**
```python
for unit in self.military_units:
    if unit.casualties >= 2:
        total_penalty = unit.casualties // 2  # 2 casualties = -1 morale
        new_penalty = total_penalty - unit._last_casualty_morale_applied

        if new_penalty > 0:
            unit.morale = max(1, unit.morale - new_penalty)
            unit._last_casualty_morale_applied = total_penalty

        # Low morale reduces effective strength
        if unit.morale <= 3:
            strength_reduction = unit.casualties // 2
            unit.strength = max(1, unit.strength - strength_reduction)
```

**3. Nuclear Auto-Escalation**
```python
max_posture_idx = max(
    _NUCLEAR_LEVELS.index(posture)
    for posture in self.nuclear_posture.values()
)

if max_posture_idx >= 2:  # Someone at dispersal or higher
    for country, posture in self.nuclear_posture.items():
        current_idx = _NUCLEAR_LEVELS.index(posture)
        min_idx = min(current_idx + 1, max_posture_idx - 1, len(_NUCLEAR_LEVELS) - 1)
        if min_idx > current_idx:
            self.nuclear_posture[country] = _NUCLEAR_LEVELS[min_idx]
```

---

## 🧪 Testing Strategy

### Test Pyramid

```
          /\
         /  \   E2E Tests (1-2 full games with mock LLM)
        /────\
       /      \  Integration Tests (game loop, GM + countries)
      /────────\
     /          \ Unit Tests (WorldState, JSON parser, utilities)
    /────────────\
```

### Mock LLM Backend

```python
class MockLLMBackend(LLMBackend):
    def __init__(self, responses: dict[str, str]):
        self.responses = responses  # {prompt_substring: json_response}
        self.call_count = 0

    async def generate(self, system_prompt, messages, **kwargs):
        self.call_count += 1
        for key, response in self.responses.items():
            if key in system_prompt:
                return response
        return '{"actions": ["default_action"]}'

    @property
    def supports_parallel(self) -> bool:
        return True
```

**Usage**:
```python
mock_backend = MockLLMBackend({
    "President": '{"position": "attack now", "priority": 1}',
    "General": '{"position": "wait 24h", "priority": 2}',
})

country = Country(config, backend=mock_backend)
decision = await country.deliberate(briefing)
```

---

## 🔌 Extension Points

### 1. Adding New Scenarios

Create YAML in `scenarios/`:

```yaml
name: "Your Scenario Name"
participants: [US, CN, ...]
initial_state:
  # Set initial world state
victory_conditions:
  - id: "your_victory_id"
    type: "territorial|diplomatic|catastrophic"
    description: "..."
```

### 2. Adding New Countries

Create YAML in `countries/`:

```yaml
name: "Taiwan"
code: "TW"
military_strength: 6
factions:
  - name: "President's Office"
    role: "hawk"
    personality: "..."
    priorities: [...]
    red_lines: [...]
```

### 3. Adding New LLM Backend

Implement `LLMBackend` interface:

```python
class CustomBackend(LLMBackend):
    async def generate(self, system_prompt, messages, **kwargs):
        # Your LLM API integration
        pass

    @property
    def supports_parallel(self) -> bool:
        return True  # or False
```

Register in `backends/__init__.py`

### 4. Adding New Victory Conditions

Edit scenario YAML + add detection logic in `game.py`:

```python
if ctype == "custom" and cid == "your_condition_id":
    # Check your condition
    if your_logic_here:
        return cond
```

### 5. Adding New Cascading Effects

Add to `WorldState._apply_cascading_effects()`:

```python
# Your new effect
if world_state.your_trigger:
    # Apply consequence
    world_state.your_field += delta
```

---

## 📊 Performance Optimization

### Profiling Hotspots

**Measured on M2 Ultra, 20-country game**:
- LLM calls: 95% of total time
- WorldState mutations: 3%
- JSON parsing: 1%
- Everything else: 1%

**Conclusion**: Optimize LLM usage, not code

### Optimization Strategies

1. **Parallel Execution** (5-10x speedup):
   ```bash
   # Use DeepSeek API with parallel mode
   python run.py play --backend deepseek
   ```

   Set in `config.yaml`:
   ```yaml
   deepseek:
     max_concurrent: 10  # Process 10 countries simultaneously
   ```

2. **Reduce Debate Rounds** (3x speedup, lower quality):
   ```yaml
   debate_rounds: 2  # Instead of 3
   ```

3. **Smaller Model** (2x speedup, lower quality):
   ```bash
   ollama pull deepseek-r1:8b  # Instead of 32b
   ```

4. **Fewer Countries** (linear speedup):
   ```bash
   python run.py play --preset quick  # 4 countries instead of 20
   ```

5. **Caching** (future work):
   - Cache faction positions for identical briefings
   - Cache GM resolutions for identical action sets
   - Estimated 20-30% speedup

---

## 🐛 Debugging Tips

### 1. Enable Verbose Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. Inspect LLM Prompts

```python
# In country.py or faction.py
print(f"PROMPT:\n{system_prompt}\n{user_message}")
```

### 3. Validate JSON Responses

```python
# In json_parser.py
if parsed_json is None:
    print(f"PARSE FAILED: {llm_output}")
```

### 4. Check WorldState After Each Round

```python
# In game.py, after apply_updates()
print(self.world_state.to_dict())
```

### 5. Use Checkpoint Resume

```bash
# Game crashed at Round 5? Resume:
python run.py resume --game game_001
```

---

## 🚀 Deployment Considerations

### Local Deployment (Current)

**Pros**:
- Free (no API costs)
- Private (data never leaves machine)
- No rate limits

**Cons**:
- Slow (sequential processing)
- Requires 64GB RAM
- macOS/Linux only (Ollama limitation)

---

### Cloud Deployment (Recommended for Production)

**Stack**:
```
Docker Container
├── Python 3.12
├── aiohttp, pyyaml
├── DeepSeek API client (no Ollama needed)
└── nginx (for viewer)
```

**Environment Variables**:
```bash
DEEPSEEK_API_KEY=your_key_here
BACKEND=deepseek
MAX_CONCURRENT=10
```

**Estimated Cost**:
- Small game (4 countries, 3 rounds): $0.50
- Medium game (10 countries, 5 rounds): $1.50
- Full game (20 countries, 10 rounds): $3-5

---

## 📚 Further Reading

- **RAND Corporation**: "Reinforcing Deterrence on NATO's Eastern Flank"
- **Academic**: "Crisis Escalation Dynamics in Multi-Agent Systems"
- **LLM Theory**: "Prompt Engineering for Roleplay Agents"
- **Wargaming**: "Professional Wargaming: A Guide" (PAX Sims)

---

**Document Version**: 1.0
**Last Updated**: 2026-02-13
**Maintainers**: WarGame Development Team
