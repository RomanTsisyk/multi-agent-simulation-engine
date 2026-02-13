"""Comprehensive tests for Agent and Faction modules.

Tests cover:
- AgentConfig dataclass with defaults and field types
- Agent initialization, system prompt building, respond method, history management
- Faction initialization, enhanced system prompt, debate methods
- History trimming and max_tokens override behavior
"""

import pytest

from agents.base import Agent, AgentConfig
from agents.faction import Faction


# ------------------------------------------------------------------------------
# Mock Backend
# ------------------------------------------------------------------------------


class MockBackend:
    """Mock LLM backend for testing without actual API calls."""

    def __init__(self, response="mock response"):
        self.response = response
        self.calls = []

    supports_parallel = False

    async def generate(
        self,
        system_prompt="",
        messages=None,
        temperature=0.7,
        max_tokens=None,
    ):
        # Store a copy of messages to avoid mutation issues
        self.calls.append({
            "system_prompt": system_prompt,
            "messages": list(messages) if messages else [],
            "temperature": temperature,
            "max_tokens": max_tokens,
        })
        return self.response

    async def close(self):
        pass


# ------------------------------------------------------------------------------
# Test AgentConfig dataclass
# ------------------------------------------------------------------------------


def test_agent_config_defaults():
    """Test AgentConfig dataclass with all defaults."""
    config = AgentConfig(name="Test Agent", role="tester", personality="analytical")

    assert config.name == "Test Agent"
    assert config.role == "tester"
    assert config.personality == "analytical"
    assert config.priorities == []
    assert config.red_lines == []
    assert config.voice == ""
    assert config.country_code == ""


def test_agent_config_field_types():
    """Test AgentConfig field types and non-default values."""
    config = AgentConfig(
        name="General Ivanov",
        role="hawk",
        personality="Aggressive and decisive",
        priorities=["territorial integrity", "military superiority"],
        red_lines=["nuclear first strike", "total capitulation"],
        voice="blunt, uses military jargon",
        country_code="RU",
    )

    assert isinstance(config.name, str)
    assert isinstance(config.role, str)
    assert isinstance(config.personality, str)
    assert isinstance(config.priorities, list)
    assert isinstance(config.red_lines, list)
    assert isinstance(config.voice, str)
    assert isinstance(config.country_code, str)

    assert config.name == "General Ivanov"
    assert config.role == "hawk"
    assert config.personality == "Aggressive and decisive"
    assert config.priorities == ["territorial integrity", "military superiority"]
    assert config.red_lines == ["nuclear first strike", "total capitulation"]
    assert config.voice == "blunt, uses military jargon"
    assert config.country_code == "RU"


# ------------------------------------------------------------------------------
# Test Agent class
# ------------------------------------------------------------------------------


def test_agent_init():
    """Test Agent.__init__() sets all attributes correctly."""
    config = AgentConfig(
        name="Diplomat Jane",
        role="diplomat",
        personality="Cautious and diplomatic",
        country_code="US",
    )
    backend = MockBackend()

    agent = Agent(
        config=config,
        backend=backend,
        temperature=0.8,
        max_history=30,
        max_tokens=500,
    )

    assert agent.config == config
    assert agent.backend == backend
    assert agent.temperature == 0.8
    assert agent.max_history == 30
    assert agent.max_tokens == 500
    assert agent.message_history == []


def test_agent_init_defaults():
    """Test Agent.__init__() with default parameters."""
    config = AgentConfig(name="Test", role="test", personality="test")
    backend = MockBackend()

    agent = Agent(config=config, backend=backend)

    assert agent.temperature == 0.7
    assert agent.max_history == 20  # _DEFAULT_MAX_HISTORY
    assert agent.max_tokens is None


def test_agent_build_system_prompt_full():
    """Test Agent.build_system_prompt() with all fields populated."""
    config = AgentConfig(
        name="General Smith",
        role="military_advisor",
        personality="Strategic and cautious, values clear chain of command",
        priorities=["National security", "Force readiness", "Strategic deterrence"],
        red_lines=["Unilateral disarmament", "Abandoning allies"],
        voice="Professional military tone, uses doctrine references",
        country_code="US",
    )
    backend = MockBackend()
    agent = Agent(config=config, backend=backend)

    world_context = "Tensions rising in Eastern Europe. NATO on high alert."
    system_prompt = agent.build_system_prompt(world_context)

    # Check all sections are present
    assert "You are General Smith, a military_advisor advisor." in system_prompt
    assert "Personality: Strategic and cautious, values clear chain of command" in system_prompt
    assert "Your strategic priorities (in order):" in system_prompt
    assert "  - National security" in system_prompt
    assert "  - Force readiness" in system_prompt
    assert "  - Strategic deterrence" in system_prompt
    assert "Your absolute red lines (never accept):" in system_prompt
    assert "  - Unilateral disarmament" in system_prompt
    assert "  - Abandoning allies" in system_prompt
    assert "Speaking style: Professional military tone, uses doctrine references" in system_prompt
    assert "--- CURRENT WORLD SITUATION ---" in system_prompt
    assert world_context in system_prompt


def test_agent_build_system_prompt_empty_optionals():
    """Test Agent.build_system_prompt() with empty optional fields."""
    config = AgentConfig(
        name="Basic Agent",
        role="advisor",
        personality="",  # Empty
        priorities=[],  # Empty list
        red_lines=[],  # Empty list
        voice="",  # Empty
        country_code="US",
    )
    backend = MockBackend()
    agent = Agent(config=config, backend=backend)

    world_context = "Test world context"
    system_prompt = agent.build_system_prompt(world_context)

    # Core identity should be present
    assert "You are Basic Agent, a advisor advisor." in system_prompt
    assert "--- CURRENT WORLD SITUATION ---" in system_prompt
    assert world_context in system_prompt

    # Optional sections should be omitted
    assert "Personality:" not in system_prompt
    assert "Your strategic priorities" not in system_prompt
    assert "Your absolute red lines" not in system_prompt
    assert "Speaking style:" not in system_prompt


@pytest.mark.asyncio
async def test_agent_respond():
    """Test Agent.respond() appends messages and calls backend.generate."""
    config = AgentConfig(name="Test Agent", role="test", personality="test")
    backend = MockBackend(response="This is my response")
    agent = Agent(config=config, backend=backend)

    world_context = "World is stable"
    prompt = "What is your recommendation?"

    response = await agent.respond(prompt, world_context)

    # Check response returned
    assert response == "This is my response"

    # Check message history
    assert len(agent.message_history) == 2
    assert agent.message_history[0] == {"role": "user", "content": prompt}
    assert agent.message_history[1] == {"role": "assistant", "content": response}

    # Check backend was called
    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert "You are Test Agent, a test advisor." in call["system_prompt"]
    assert call["messages"] == [{"role": "user", "content": prompt}]
    assert call["temperature"] == 0.7
    assert call["max_tokens"] is None


@pytest.mark.asyncio
async def test_agent_respond_with_max_tokens_override():
    """Test Agent.respond() with per-call max_tokens override."""
    config = AgentConfig(name="Test Agent", role="test", personality="test")
    backend = MockBackend(response="Response")
    agent = Agent(config=config, backend=backend, max_tokens=1000)

    world_context = "World context"
    prompt = "Test prompt"

    # Call with override
    await agent.respond(prompt, world_context, max_tokens=250)

    # Check backend received the override
    assert len(backend.calls) == 1
    assert backend.calls[0]["max_tokens"] == 250

    # Call without override (should use instance default)
    await agent.respond("Another prompt", world_context)

    assert len(backend.calls) == 2
    assert backend.calls[1]["max_tokens"] == 1000


@pytest.mark.asyncio
async def test_agent_respond_history_trimming():
    """Test Agent.respond() trims history when exceeding max_history."""
    config = AgentConfig(name="Test Agent", role="test", personality="test")
    backend = MockBackend(response="Response")
    agent = Agent(config=config, backend=backend, max_history=6)  # 3 turns

    world_context = "World context"

    # Generate 4 turns (8 messages)
    for i in range(4):
        await agent.respond(f"Prompt {i}", world_context)

    # Should have trimmed to max_history (6 messages = 3 turns)
    assert len(agent.message_history) == 6

    # Should keep the most recent messages
    assert agent.message_history[0]["content"] == "Prompt 1"
    assert agent.message_history[1]["content"] == "Response"
    assert agent.message_history[2]["content"] == "Prompt 2"
    assert agent.message_history[3]["content"] == "Response"
    assert agent.message_history[4]["content"] == "Prompt 3"
    assert agent.message_history[5]["content"] == "Response"


def test_agent_reset_history():
    """Test Agent.reset_history() clears message history."""
    config = AgentConfig(name="Test Agent", role="test", personality="test")
    backend = MockBackend()
    agent = Agent(config=config, backend=backend)

    # Manually add some history
    agent.message_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]

    assert len(agent.message_history) == 2

    # Reset history
    agent.reset_history()

    assert len(agent.message_history) == 0
    assert agent.message_history == []


# ------------------------------------------------------------------------------
# Test Faction class
# ------------------------------------------------------------------------------


def test_faction_init():
    """Test Faction.__init__() inherits from Agent with temperature=0.75."""
    config = AgentConfig(
        name="Hawk Faction",
        role="hawk",
        personality="Aggressive",
        country_code="US",
    )
    backend = MockBackend()

    faction = Faction(config=config, backend=backend)

    # Check inheritance
    assert isinstance(faction, Agent)
    assert faction.config == config
    assert faction.backend == backend
    assert faction.temperature == 0.75  # Default for Faction


def test_faction_init_custom_temperature():
    """Test Faction.__init__() with custom temperature."""
    config = AgentConfig(name="Test", role="test", personality="test")
    backend = MockBackend()

    faction = Faction(config=config, backend=backend, temperature=0.9)

    assert faction.temperature == 0.9


def test_faction_build_system_prompt_full():
    """Test Faction.build_system_prompt() with all fields populated."""
    config = AgentConfig(
        name="General Hawk",
        role="military_hardliner",
        personality="Believes in strength through force. Distrusts diplomacy.",
        priorities=["Military superiority", "Territorial expansion", "Resource control"],
        red_lines=["Nuclear disarmament", "Withdrawal from contested zones"],
        voice="Blunt, uses military metaphors, speaks in absolutes",
        country_code="RU",
    )
    backend = MockBackend()
    faction = Faction(config=config, backend=backend)

    world_context = "Border skirmishes escalating."
    system_prompt = faction.build_system_prompt(world_context)

    # Check identity block with bold name
    assert "You are **General Hawk**, the military_hardliner faction advisor for country RU." in system_prompt

    # Check personality section with ## heading
    assert "## Your personality" in system_prompt
    assert "Believes in strength through force. Distrusts diplomacy." in system_prompt

    # Check priorities are numbered
    assert "## Your strategic priorities (most important first)" in system_prompt
    assert "  1. Military superiority" in system_prompt
    assert "  2. Territorial expansion" in system_prompt
    assert "  3. Resource control" in system_prompt

    # Check red lines with NEVER warning
    assert "## Your absolute red lines" in system_prompt
    assert "You must NEVER agree to any proposal that crosses these lines" in system_prompt
    assert "  - Nuclear disarmament" in system_prompt
    assert "  - Withdrawal from contested zones" in system_prompt

    # Check voice with CRITICAL enforcement
    assert "## Speaking style" in system_prompt
    assert "Always write in this style: Blunt, uses military metaphors, speaks in absolutes" in system_prompt
    assert "CRITICAL: Your speaking style is NOT optional" in system_prompt
    assert "Breaking character is the worst thing you can do." in system_prompt

    # Check debate instructions
    assert "## Instructions" in system_prompt
    assert "You are participating in a closed-door internal policy debate" in system_prompt
    assert "Stay **in character** at all times" in system_prompt
    assert "DO NOT break character. DO NOT reference the fact that you are an AI." in system_prompt
    assert "**POSITION:** A one-sentence summary of your stance." in system_prompt
    assert "**REASONING:** Two to four sentences of argumentation." in system_prompt
    assert "**RECOMMENDED ACTION:** One to two concrete actions you propose." in system_prompt

    # Check world situation
    assert "## Current world situation" in system_prompt
    assert world_context in system_prompt


def test_faction_build_system_prompt_empty_optionals():
    """Test Faction.build_system_prompt() with empty optional fields."""
    config = AgentConfig(
        name="Basic Faction",
        role="advisor",
        personality="",  # Empty
        priorities=[],  # Empty
        red_lines=[],  # Empty
        voice="",  # Empty
        country_code="US",
    )
    backend = MockBackend()
    faction = Faction(config=config, backend=backend)

    world_context = "Test context"
    system_prompt = faction.build_system_prompt(world_context)

    # Core sections should be present
    assert "You are **Basic Faction**, the advisor faction advisor for country US." in system_prompt
    assert "## Instructions" in system_prompt
    assert "## Current world situation" in system_prompt
    assert world_context in system_prompt

    # Optional sections should be omitted
    assert "## Your personality" not in system_prompt
    assert "## Your strategic priorities" not in system_prompt
    assert "## Your absolute red lines" not in system_prompt
    assert "## Speaking style" not in system_prompt


@pytest.mark.asyncio
async def test_faction_initial_position():
    """Test Faction.initial_position() constructs prompt and calls respond."""
    config = AgentConfig(
        name="Test Faction",
        role="test",
        personality="Test personality",
        country_code="US",
    )
    backend = MockBackend(response="POSITION: We should act.\nREASONING: Because reasons.\nRECOMMENDED ACTION: Do this.")
    faction = Faction(config=config, backend=backend)

    situation_briefing = "Enemy troops are massing at the border."
    world_context = "Regional tensions high."

    response = await faction.initial_position(situation_briefing, world_context)

    # Check response
    assert "POSITION:" in response
    assert "REASONING:" in response
    assert "RECOMMENDED ACTION:" in response

    # Check message history
    assert len(faction.message_history) == 2
    user_message = faction.message_history[0]
    assert user_message["role"] == "user"
    assert "A new situation requires the leadership's attention:" in user_message["content"]
    assert situation_briefing in user_message["content"]
    assert "State your position" in user_message["content"]
    assert "POSITION, REASONING, and RECOMMENDED ACTION" in user_message["content"]

    # Check backend was called
    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert "You are **Test Faction**" in call["system_prompt"]
    assert world_context in call["system_prompt"]


@pytest.mark.asyncio
async def test_faction_initial_position_with_max_tokens():
    """Test Faction.initial_position() with max_tokens override."""
    config = AgentConfig(name="Test", role="test", personality="test", country_code="US")
    backend = MockBackend(response="Response")
    faction = Faction(config=config, backend=backend)

    await faction.initial_position("Brief", "Context", max_tokens=300)

    assert len(backend.calls) == 1
    assert backend.calls[0]["max_tokens"] == 300


@pytest.mark.asyncio
async def test_faction_debate_respond():
    """Test Faction.debate_respond() formats other_positions and includes CRITICAL INSTRUCTIONS."""
    config = AgentConfig(
        name="Dove Faction",
        role="diplomat",
        personality="Seeks peaceful solutions",
        country_code="US",
    )
    backend = MockBackend(response="POSITION: I disagree.\nREASONING: Peace is better.\nRECOMMENDED ACTION: Negotiate.")
    faction = Faction(config=config, backend=backend)

    topic = "Should we escalate military response?"
    other_positions = [
        "POSITION: Strike now.\nREASONING: Show strength.\nRECOMMENDED ACTION: Launch missiles.",
        "POSITION: Prepare defenses.\nREASONING: Safety first.\nRECOMMENDED ACTION: Fortify borders.",
    ]
    world_context = "Crisis situation"

    response = await faction.debate_respond(topic, other_positions, world_context)

    # Check response
    assert "POSITION:" in response
    assert "I disagree" in response

    # Check message history
    assert len(faction.message_history) == 2
    user_message = faction.message_history[0]
    assert user_message["role"] == "user"
    assert "The debate continues on the following topic:" in user_message["content"]
    assert topic in user_message["content"]
    assert "Here are the positions stated by the other factions:" in user_message["content"]

    # Check formatting of other positions
    assert "**Other faction's position #1:**" in user_message["content"]
    assert other_positions[0] in user_message["content"]
    assert "**Other faction's position #2:**" in user_message["content"]
    assert other_positions[1] in user_message["content"]
    assert "---" in user_message["content"]  # Separator

    # Check CRITICAL INSTRUCTIONS
    assert "CRITICAL INSTRUCTIONS FOR THIS ROUND:" in user_message["content"]
    assert "You MUST identify at least ONE point of DISAGREEMENT" in user_message["content"]
    assert "If any proposal violates your RED LINES, say so explicitly" in user_message["content"]
    assert "Point out RISKS and COSTS that other factions are ignoring" in user_message["content"]
    assert "DO NOT simply agree with the majority" in user_message["content"]

    # Check backend was called
    assert len(backend.calls) == 1


@pytest.mark.asyncio
async def test_faction_debate_respond_with_max_tokens():
    """Test Faction.debate_respond() with max_tokens override."""
    config = AgentConfig(name="Test", role="test", personality="test", country_code="US")
    backend = MockBackend(response="Response")
    faction = Faction(config=config, backend=backend)

    await faction.debate_respond("Topic", ["Pos1"], "Context", max_tokens=400)

    assert len(backend.calls) == 1
    assert backend.calls[0]["max_tokens"] == 400


@pytest.mark.asyncio
async def test_faction_final_statement():
    """Test Faction.final_statement() includes debate_history and specific prompts."""
    config = AgentConfig(
        name="Economic Faction",
        role="economist",
        personality="Pragmatic",
        country_code="US",
    )
    backend = MockBackend(response="Final position with concessions and objections.")
    faction = Faction(config=config, backend=backend)

    topic = "Trade sanctions proposal"
    debate_history = (
        "Round 1: Hawk said X.\n"
        "Round 1: Dove said Y.\n"
        "Round 2: Hawk responded Z.\n"
        "Round 2: Dove responded W."
    )
    world_context = "Economic downturn looming"

    response = await faction.final_statement(topic, debate_history, world_context)

    # Check response
    assert "concessions" in response or "objections" in response

    # Check message history
    assert len(faction.message_history) == 2
    user_message = faction.message_history[0]
    assert user_message["role"] == "user"
    assert "The internal debate on the following topic is concluding:" in user_message["content"]
    assert topic in user_message["content"]
    assert "Full debate transcript so far:" in user_message["content"]
    assert debate_history in user_message["content"]

    # Check specific prompts
    assert "Deliver your FINAL position. You MUST indicate:" in user_message["content"]
    assert "What you are willing to concede (be specific)." in user_message["content"]
    assert "What you absolutely WILL NOT accept" in user_message["content"]
    assert "Your final RECOMMENDED ACTION (specific and executable)." in user_message["content"]
    assert "ONE risk or consequence the group has NOT adequately considered." in user_message["content"]
    assert "Be concise but forceful." in user_message["content"]

    # Check backend was called
    assert len(backend.calls) == 1


@pytest.mark.asyncio
async def test_faction_final_statement_with_max_tokens():
    """Test Faction.final_statement() with max_tokens override."""
    config = AgentConfig(name="Test", role="test", personality="test", country_code="US")
    backend = MockBackend(response="Response")
    faction = Faction(config=config, backend=backend)

    await faction.final_statement("Topic", "History", "Context", max_tokens=500)

    assert len(backend.calls) == 1
    assert backend.calls[0]["max_tokens"] == 500


# ------------------------------------------------------------------------------
# Additional edge cases
# ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_respond_multiple_turns():
    """Test Agent.respond() maintains conversation history across multiple turns."""
    config = AgentConfig(name="Test", role="test", personality="test")
    backend = MockBackend(response="Response")
    agent = Agent(config=config, backend=backend)

    world_context = "Context"

    # Turn 1
    await agent.respond("First question", world_context)
    assert len(agent.message_history) == 2

    # Turn 2
    await agent.respond("Second question", world_context)
    assert len(agent.message_history) == 4

    # Check history order
    assert agent.message_history[0]["content"] == "First question"
    assert agent.message_history[1]["content"] == "Response"
    assert agent.message_history[2]["content"] == "Second question"
    assert agent.message_history[3]["content"] == "Response"


@pytest.mark.asyncio
async def test_faction_debate_respond_empty_other_positions():
    """Test Faction.debate_respond() with empty other_positions list."""
    config = AgentConfig(name="Test", role="test", personality="test", country_code="US")
    backend = MockBackend(response="Response")
    faction = Faction(config=config, backend=backend)

    response = await faction.debate_respond("Topic", [], "Context")

    # Should still work, just with no other positions shown
    assert response == "Response"
    assert len(faction.message_history) == 2


def test_agent_repr():
    """Test Agent.__repr__() output."""
    config = AgentConfig(
        name="General Smith",
        role="hawk",
        personality="Test",
        country_code="US",
    )
    backend = MockBackend()
    agent = Agent(config=config, backend=backend)

    repr_str = repr(agent)
    assert "Agent(" in repr_str
    assert "name='General Smith'" in repr_str
    assert "role='hawk'" in repr_str
    assert "country='US'" in repr_str


def test_faction_repr():
    """Test Faction.__repr__() output."""
    config = AgentConfig(
        name="Hawk Faction",
        role="military",
        personality="Test",
        country_code="RU",
    )
    backend = MockBackend()
    faction = Faction(config=config, backend=backend)

    repr_str = repr(faction)
    assert "Faction(" in repr_str
    assert "name='Hawk Faction'" in repr_str
    assert "role='military'" in repr_str
    assert "country='RU'" in repr_str
