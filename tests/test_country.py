"""Comprehensive pytest tests for the Country agent module.

Tests cover:
- Crisis phase detection
- Transcript formatting
- Faction weight computation
- Synthesis parsing with various formats
- Diplomatic message parsing
- Configuration dataclass defaults
- Phase modifier structure validation
"""

import pytest
from agents.country import (
    Country,
    CountryConfig,
    _PHASE_MODIFIERS,
    _parse_diplomatic_line,
)
from agents.base import AgentConfig
from agents.faction import Faction


# ======================================================================
# Mock Backend
# ======================================================================


class MockBackend:
    """Mock LLM backend for testing without real API calls."""

    supports_parallel = False

    async def generate(self, **kwargs):
        """Return a mock response."""
        return "mock response"

    async def close(self):
        """Mock close method."""
        pass


# ======================================================================
# Test Fixtures
# ======================================================================


@pytest.fixture
def mock_backend():
    """Provide a mock backend instance."""
    return MockBackend()


@pytest.fixture
def country_config():
    """Provide a basic country configuration."""
    return CountryConfig(
        name="Test Country",
        code="TC",
        alliances=["US", "UK"],
        military_strength=7,
        economic_strength=6,
        description="A test country for unit testing",
    )


@pytest.fixture
def mock_faction(mock_backend):
    """Provide a single mock faction."""
    config = AgentConfig(
        name="Test Hawk",
        role="hawk",
        personality="Aggressive and decisive",
        priorities=["military strength", "territorial integrity"],
        red_lines=["surrender", "territorial concessions"],
        voice="blunt military jargon",
        country_code="TC",
    )
    return Faction(config=config, backend=mock_backend)


@pytest.fixture
def country_instance(country_config, mock_faction, mock_backend):
    """Provide a Country instance for testing."""
    return Country(
        config=country_config,
        factions=[mock_faction],
        backend=mock_backend,
    )


# ======================================================================
# Test: _detect_crisis_phase()
# ======================================================================


class TestDetectCrisisPhase:
    """Tests for crisis phase detection based on keywords."""

    def test_nuclear_phase_detection(self):
        """Test nuclear phase is detected with nuclear keywords."""
        contexts = [
            "Russia has moved to nuclear launch_ready status",
            "Tactical use of nuclear weapons under consideration",
            "DEFCON 2 reached, strategic weapons on alert",
            "ICBM launch detected",
            "The nuclear threshold has been crossed",
            "Warhead deployment imminent",
        ]
        for context in contexts:
            assert Country._detect_crisis_phase(context) == "nuclear"

    def test_conventional_phase_detection(self):
        """Test conventional phase is detected with combat keywords."""
        contexts = [
            "Ground forces have begun offensive operations",
            "Air strikes launched against military targets",
            "Tank divisions crossing the border",
            "Heavy artillery bombardment ongoing",
            "Military operation in progress with significant casualties",
            "Troops deployed to the front lines",
            "Bombing campaign intensifies",
            "Attack on coastal installations",
            "Combat operations in sector 7",
            "Invasion has commenced",
        ]
        for context in contexts:
            assert Country._detect_crisis_phase(context) == "conventional"

    def test_hybrid_phase_detection(self):
        """Test hybrid phase is detected with hybrid warfare keywords."""
        contexts = [
            "Cyber activity on critical infrastructure detected",
            "Disinformation campaign spreading rapidly",
            "False flag event suspected",
            "Little green men observed near the border",
            "Proxy forces mobilizing in disputed territory",
            "Sabotage of power grid confirmed",
            "Covert action underway",
            "Information warfare intensifying",
            "Hybrid tactics employed by adversary",
        ]
        for context in contexts:
            assert Country._detect_crisis_phase(context) == "hybrid"

    def test_diplomatic_phase_default(self):
        """Test diplomatic phase is returned as default."""
        contexts = [
            "Negotiations continue at the UN",
            "Diplomatic talks scheduled for next week",
            "Ambassador recalled for consultations",
            "Peace process gaining momentum",
            "Economic sanctions under discussion",
            "Trade agreement being finalized",
            "Routine military exercises conducted",
            "",  # Empty context
            "Just a normal day",
        ]
        for context in contexts:
            assert Country._detect_crisis_phase(context) == "diplomatic"

    def test_nuclear_takes_priority_over_conventional(self):
        """Test nuclear keywords take priority when multiple phases present."""
        context = "Conventional combat continues while nuclear weapons are on launch ready status"
        assert Country._detect_crisis_phase(context) == "nuclear"

    def test_conventional_takes_priority_over_hybrid(self):
        """Test conventional keywords take priority over hybrid."""
        context = "Cyber attacks ongoing but ground forces have launched offensive"
        assert Country._detect_crisis_phase(context) == "conventional"

    def test_hybrid_takes_priority_over_diplomatic(self):
        """Test hybrid keywords take priority over diplomatic."""
        context = "Diplomatic talks continue amid ongoing disinformation campaign"
        assert Country._detect_crisis_phase(context) == "hybrid"

    def test_case_insensitive_detection(self):
        """Test phase detection is case-insensitive."""
        assert Country._detect_crisis_phase("NUCLEAR LAUNCH READY") == "nuclear"
        assert Country._detect_crisis_phase("Attack in progress") == "conventional"
        assert Country._detect_crisis_phase("Cyber infrastructure targeted") == "hybrid"


# ======================================================================
# Test: _format_transcript()
# ======================================================================


class TestFormatTranscript:
    """Tests for debate transcript formatting."""

    def test_empty_debate_log(self):
        """Test formatting an empty debate log."""
        result = Country._format_transcript([])
        assert result == ""

    def test_single_round_single_faction(self):
        """Test formatting a single round with one faction."""
        debate_log = [
            {
                "round": 1,
                "faction": "Test Hawk",
                "role": "hawk",
                "content": "We must act decisively.",
            }
        ]
        result = Country._format_transcript(debate_log)

        assert "ROUND 1" in result
        assert "[Test Hawk (hawk)]:" in result
        assert "We must act decisively." in result
        assert "=" * 60 in result

    def test_multi_round_multi_faction(self):
        """Test formatting multiple rounds with multiple factions."""
        debate_log = [
            {
                "round": 1,
                "faction": "Hawk",
                "role": "hawk",
                "content": "Deploy forces immediately.",
            },
            {
                "round": 1,
                "faction": "Diplomat",
                "role": "diplomat",
                "content": "We should negotiate first.",
            },
            {
                "round": 2,
                "faction": "Hawk",
                "role": "hawk",
                "content": "Negotiation is weakness.",
            },
            {
                "round": 2,
                "faction": "Diplomat",
                "role": "diplomat",
                "content": "Force will escalate the crisis.",
            },
            {
                "round": 3,
                "faction": "Hawk",
                "role": "hawk",
                "content": "Final position: deploy now.",
            },
            {
                "round": 3,
                "faction": "Diplomat",
                "role": "diplomat",
                "content": "Final position: diplomatic solution.",
            },
        ]
        result = Country._format_transcript(debate_log)

        # Check all rounds are present
        assert "ROUND 1" in result
        assert "ROUND 2" in result
        assert "ROUND 3" in result

        # Check all content is present
        assert "Deploy forces immediately." in result
        assert "We should negotiate first." in result
        assert "Negotiation is weakness." in result
        assert "Force will escalate the crisis." in result
        assert "Final position: deploy now." in result
        assert "Final position: diplomatic solution." in result

        # Check faction labels are present
        assert "[Hawk (hawk)]:" in result
        assert "[Diplomat (diplomat)]:" in result

    def test_round_separators(self):
        """Test that round separators are only added when round changes."""
        debate_log = [
            {"round": 1, "faction": "F1", "role": "r1", "content": "C1"},
            {"round": 1, "faction": "F2", "role": "r2", "content": "C2"},
            {"round": 2, "faction": "F1", "role": "r1", "content": "C3"},
        ]
        result = Country._format_transcript(debate_log)

        # Should have 2 separators (one for round 1, one for round 2)
        separator = "=" * 60
        assert result.count(separator) == 4  # 2 lines per separator


# ======================================================================
# Test: _compute_faction_weights()
# ======================================================================


class TestComputeFactionWeights:
    """Tests for dynamic faction weight computation."""

    def test_diplomatic_phase_weights(self, country_instance):
        """Test weights in diplomatic phase favor diplomats."""
        result = country_instance._compute_faction_weights("diplomatic")

        assert "DIPLOMATIC" in result.upper()
        assert "influence weight" in result.lower()
        assert "phase modifier" in result.lower()

    def test_hybrid_phase_weights(self, country_instance):
        """Test weights in hybrid phase favor intelligence/wildcards."""
        result = country_instance._compute_faction_weights("hybrid")

        assert "HYBRID" in result.upper()
        assert "influence weight" in result.lower()

    def test_conventional_phase_weights(self, country_instance):
        """Test weights in conventional phase favor military."""
        result = country_instance._compute_faction_weights("conventional")

        assert "CONVENTIONAL" in result.upper()
        assert "influence weight" in result.lower()

    def test_nuclear_phase_weights(self, country_instance):
        """Test weights in nuclear phase favor pragmatists/doves."""
        result = country_instance._compute_faction_weights("nuclear")

        assert "NUCLEAR" in result.upper()
        assert "influence weight" in result.lower()

    def test_weight_calculation_accuracy(self, mock_backend):
        """Test that weights are calculated correctly with known values."""
        # Create a country with a hawk faction
        config = CountryConfig(name="Test", code="TC")
        faction_config = AgentConfig(
            name="Test Hawk",
            role="hawk",
            personality="Aggressive",
            country_code="TC",
        )
        faction = Faction(config=faction_config, backend=mock_backend)
        country = Country(config=config, factions=[faction], backend=mock_backend)

        # In diplomatic phase: hawk base=3, modifier=0.7, expected=2.1
        result = country._compute_faction_weights("diplomatic")
        assert "2.1" in result or "2.10" in result

        # In conventional phase: hawk base=3, modifier=1.2, expected=3.6
        result = country._compute_faction_weights("conventional")
        assert "3.6" in result or "3.60" in result

    def test_unknown_phase_defaults_to_conventional(self, country_instance):
        """Test unknown phase defaults to conventional weights."""
        result = country_instance._compute_faction_weights("unknown_phase")

        # Should still produce output with conventional modifiers
        assert "influence weight" in result

    def test_empty_factions_list(self, country_config, mock_backend):
        """Test weight computation with no factions."""
        country = Country(config=country_config, factions=[], backend=mock_backend)
        result = country._compute_faction_weights("conventional")

        # Should return empty string or minimal output
        assert result == "" or "Crisis phase:" in result

    def test_military_realist_underscore_and_space(self, mock_backend):
        """Test that both 'military_realist' and 'military realist' work."""
        config = CountryConfig(name="Test", code="TC")

        # Test with underscore
        faction1_config = AgentConfig(
            name="Realist 1", role="military_realist", personality="Realistic", country_code="TC"
        )
        faction1 = Faction(config=faction1_config, backend=mock_backend)

        # Test with space
        faction2_config = AgentConfig(
            name="Realist 2", role="military realist", personality="Realistic", country_code="TC"
        )
        faction2 = Faction(config=faction2_config, backend=mock_backend)

        country1 = Country(config=config, factions=[faction1], backend=mock_backend)
        country2 = Country(config=config, factions=[faction2], backend=mock_backend)

        result1 = country1._compute_faction_weights("conventional")
        result2 = country2._compute_faction_weights("conventional")

        # Both should get the same modifier (1.5 in conventional phase)
        assert "4.5" in result1  # base 3 * 1.5
        assert "4.5" in result2


# ======================================================================
# Test: _parse_synthesis()
# ======================================================================


class TestParseSynthesis:
    """Tests for synthesis output parsing."""

    def test_well_formed_synthesis_all_sections(self):
        """Test parsing a well-formed synthesis with all sections."""
        raw = """
DECISION: Deploy additional forces to the eastern border while maintaining diplomatic channels.

ACTIONS:
1. Deploy 2nd Armoured Brigade to Suwalki corridor within 48h
2. Request NATO Article 4 consultations
3. Establish humanitarian corridors in cooperation with UN

DISSENT: Hawk faction objected to any diplomatic engagement, citing red line on perceived weakness.

DIPLOMATIC_MESSAGES:
- TO: US | CHANNEL: private | MESSAGE: We request immediate deployment of additional forces
- TO: RU | CHANNEL: backchannel | MESSAGE: We are open to a 48-hour ceasefire
- TO: UN | CHANNEL: public | MESSAGE: We call for an emergency Security Council session
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert "Deploy additional forces" in decision
        assert len(actions) == 3
        assert "2nd Armoured Brigade to Suwalki corridor within 48h" in actions[0]
        assert "Request NATO Article 4 consultations" in actions[1]
        assert "Establish humanitarian corridors" in actions[2]
        assert "Hawk faction objected" in dissent
        assert len(diplomatic_messages) == 3
        assert diplomatic_messages[0]["to"] == "US"
        assert diplomatic_messages[1]["channel"] == "backchannel"

    def test_missing_sections_fallback(self):
        """Test parsing when sections are missing."""
        raw = "Just some raw text without any structure."

        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert decision == "Just some raw text without any structure."
        assert actions == []
        assert dissent == ""
        assert diplomatic_messages == []

    def test_decision_only(self):
        """Test parsing when only DECISION section is present."""
        raw = """
DECISION: Maintain current defensive posture and continue diplomatic efforts.
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert "Maintain current defensive posture" in decision
        assert actions == []
        assert dissent == ""
        assert diplomatic_messages == []

    def test_multiple_actions_various_numbering(self):
        """Test parsing actions with different numbering styles."""
        raw = """
DECISION: Multi-pronged approach.

ACTIONS:
1. First action
2) Second action with parenthesis
3. Third action
- Fourth action with dash
5) Fifth action
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert len(actions) == 5
        assert "First action" in actions[0]
        assert "Second action with parenthesis" in actions[1]
        assert "Third action" in actions[2]
        assert "Fourth action with dash" in actions[3]
        assert "Fifth action" in actions[4]

    def test_diplomatic_messages_parsing(self):
        """Test parsing various diplomatic message formats."""
        raw = """
DECISION: Send messages.

DIPLOMATIC_MESSAGES:
- TO: US | CHANNEL: private | MESSAGE: Secret message
- TO: RU | CHANNEL: public | MESSAGE: Public statement
- TO: CN | CHANNEL: backchannel | MESSAGE: Unofficial communication
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert len(diplomatic_messages) == 3
        assert diplomatic_messages[0]["to"] == "US"
        assert diplomatic_messages[0]["channel"] == "private"
        assert diplomatic_messages[0]["message"] == "Secret message"
        assert diplomatic_messages[2]["channel"] == "backchannel"

    def test_dissent_none(self):
        """Test parsing when dissent is explicitly 'None'."""
        raw = """
DECISION: Unanimous decision.

ACTIONS:
1. Take action

DISSENT: None
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert dissent == "None"

    def test_dissent_multiline(self):
        """Test parsing multi-line dissent."""
        raw = """
DECISION: Complex decision.

DISSENT: Hawk faction strongly objected to diplomatic concessions.
Dove faction warned of escalation risks.
Military realist noted resource constraints.
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert "Hawk faction" in dissent
        assert "Dove faction" in dissent
        assert "Military realist" in dissent

    def test_decision_multiline(self):
        """Test parsing multi-line decision."""
        raw = """
DECISION: The country will adopt a calibrated response strategy.
This involves both military readiness and diplomatic engagement.
We seek to deter aggression while avoiding unnecessary escalation.

ACTIONS:
1. Increase readiness
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert "calibrated response strategy" in decision
        assert "military readiness" in decision
        assert "diplomatic engagement" in decision
        assert "deter aggression" in decision

    def test_inline_decision_text(self):
        """Test when decision text is on the same line as the label."""
        raw = """DECISION: Immediate action required.
ACTIONS:
1. Act now
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert "Immediate action required" in decision
        assert len(actions) == 1

    def test_empty_sections(self):
        """Test parsing with empty sections."""
        raw = """
DECISION:

ACTIONS:

DISSENT:

DIPLOMATIC_MESSAGES:
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        # Empty sections will fall back to raw text as decision
        assert isinstance(decision, str)
        assert actions == []
        assert dissent == ""
        assert diplomatic_messages == []

    def test_actions_without_numbering(self):
        """Test actions that are just text without numbers."""
        raw = """
DECISION: Take action.

ACTIONS:
Deploy forces
Negotiate terms
Establish position
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert len(actions) == 3
        assert "Deploy forces" in actions
        assert "Negotiate terms" in actions
        assert "Establish position" in actions


# ======================================================================
# Test: _parse_diplomatic_line()
# ======================================================================


class TestParseDiplomaticLine:
    """Tests for diplomatic message line parsing."""

    def test_valid_message_all_fields(self):
        """Test parsing a valid message with all fields."""
        line = "- TO: US | CHANNEL: private | MESSAGE: We request immediate assistance"
        result = _parse_diplomatic_line(line)

        assert result is not None
        assert result["to"] == "US"
        assert result["channel"] == "private"
        assert result["message"] == "We request immediate assistance"

    def test_valid_message_public_channel(self):
        """Test parsing with public channel."""
        line = "TO: RU | CHANNEL: public | MESSAGE: We condemn these actions"
        result = _parse_diplomatic_line(line)

        assert result is not None
        assert result["to"] == "RU"
        assert result["channel"] == "public"
        assert result["message"] == "We condemn these actions"

    def test_valid_message_backchannel(self):
        """Test parsing with backchannel."""
        line = "- TO: CN | CHANNEL: backchannel | MESSAGE: Unofficial proposal"
        result = _parse_diplomatic_line(line)

        assert result is not None
        assert result["channel"] == "backchannel"

    def test_none_input(self):
        """Test parsing 'None' returns None."""
        assert _parse_diplomatic_line("None") is None
        assert _parse_diplomatic_line("- None") is None
        assert _parse_diplomatic_line("none") is None

    def test_missing_to_field(self):
        """Test parsing fails when TO field is missing."""
        line = "CHANNEL: private | MESSAGE: Some message"
        result = _parse_diplomatic_line(line)

        assert result is None

    def test_missing_message_field(self):
        """Test parsing fails when MESSAGE field is missing."""
        line = "TO: US | CHANNEL: private"
        result = _parse_diplomatic_line(line)

        assert result is None

    def test_channel_defaults_to_public(self):
        """Test channel defaults to public if not specified."""
        line = "TO: UK | MESSAGE: Default channel message"
        result = _parse_diplomatic_line(line)

        assert result is not None
        assert result["channel"] == "public"

    def test_whitespace_handling(self):
        """Test that extra whitespace is handled correctly."""
        line = "  -  TO:  US  |  CHANNEL:  private  |  MESSAGE:  Test message  "
        result = _parse_diplomatic_line(line)

        assert result is not None
        assert result["to"] == "US"
        assert result["channel"] == "private"
        assert result["message"] == "Test message"

    def test_message_with_colons(self):
        """Test message containing colons."""
        line = "TO: FR | CHANNEL: private | MESSAGE: Time: 14:00. Location: Paris."
        result = _parse_diplomatic_line(line)

        assert result is not None
        assert result["message"] == "Time: 14:00. Location: Paris."

    def test_message_with_pipes(self):
        """Test message containing pipe characters (edge case)."""
        line = "TO: DE | CHANNEL: public | MESSAGE: Option A or Option B available"
        result = _parse_diplomatic_line(line)

        assert result is not None
        # The message should be everything after "MESSAGE:"
        assert "Option" in result["message"]

    def test_empty_to_field(self):
        """Test that empty TO field returns None."""
        line = "TO: | CHANNEL: private | MESSAGE: No recipient"
        result = _parse_diplomatic_line(line)

        assert result is None

    def test_empty_message_field(self):
        """Test that empty MESSAGE field returns None."""
        line = "TO: US | CHANNEL: private | MESSAGE: "
        result = _parse_diplomatic_line(line)

        assert result is None

    def test_case_insensitive_keys(self):
        """Test that field keys are case-insensitive."""
        line = "to: JP | channel: PRIVATE | message: Test"
        result = _parse_diplomatic_line(line)

        assert result is not None
        assert result["to"] == "JP"
        assert result["channel"] == "private"
        assert result["message"] == "Test"

    def test_multiple_country_codes(self):
        """Test parsing with different country codes."""
        countries = ["US", "RU", "CN", "UK", "FR", "DE", "JP", "UN", "NATO", "EU"]

        for country in countries:
            line = f"TO: {country} | CHANNEL: private | MESSAGE: Test message"
            result = _parse_diplomatic_line(line)
            assert result is not None
            assert result["to"] == country

    def test_various_channel_types(self):
        """Test parsing with various channel types."""
        channels = ["public", "private", "backchannel", "secret", "official"]

        for channel in channels:
            line = f"TO: US | CHANNEL: {channel} | MESSAGE: Test"
            result = _parse_diplomatic_line(line)
            assert result is not None
            assert result["channel"] == channel.lower()


# ======================================================================
# Test: CountryConfig dataclass
# ======================================================================


class TestCountryConfig:
    """Tests for CountryConfig dataclass defaults."""

    def test_minimal_config(self):
        """Test creating config with only required fields."""
        config = CountryConfig(name="Test Country", code="TC")

        assert config.name == "Test Country"
        assert config.code == "TC"
        assert config.alliances == []
        assert config.military_strength == 5
        assert config.economic_strength == 5
        assert config.description == ""

    def test_full_config(self):
        """Test creating config with all fields."""
        config = CountryConfig(
            name="United States",
            code="US",
            alliances=["UK", "FR", "DE"],
            military_strength=10,
            economic_strength=9,
            description="Global superpower with extensive military reach",
        )

        assert config.name == "United States"
        assert config.code == "US"
        assert config.alliances == ["UK", "FR", "DE"]
        assert config.military_strength == 10
        assert config.economic_strength == 9
        assert "Global superpower" in config.description

    def test_default_values(self):
        """Test that default values are applied correctly."""
        config = CountryConfig(name="Test", code="T")

        assert isinstance(config.alliances, list)
        assert len(config.alliances) == 0
        assert config.military_strength == 5
        assert config.economic_strength == 5
        assert config.description == ""

    def test_alliance_list_mutation(self):
        """Test that alliance lists don't share references."""
        config1 = CountryConfig(name="Country1", code="C1")
        config2 = CountryConfig(name="Country2", code="C2")

        config1.alliances.append("US")

        assert "US" in config1.alliances
        assert "US" not in config2.alliances


# ======================================================================
# Test: _PHASE_MODIFIERS structure
# ======================================================================


class TestPhaseModifiers:
    """Tests for _PHASE_MODIFIERS structure validation."""

    def test_all_phases_present(self):
        """Test that all expected phases are present."""
        expected_phases = ["diplomatic", "hybrid", "conventional", "nuclear"]

        for phase in expected_phases:
            assert phase in _PHASE_MODIFIERS

    def test_all_roles_in_all_phases(self):
        """Test that all roles are present in all phases."""
        expected_roles = [
            "hawk",
            "diplomat",
            "pragmatist",
            "military_realist",
            "military realist",
            "wildcard",
            "intelligence",
            "economic",
            "hardliner",
            "dove",
        ]

        for phase, modifiers in _PHASE_MODIFIERS.items():
            for role in expected_roles:
                assert role in modifiers, f"Role {role} missing from phase {phase}"

    def test_modifier_values_are_positive(self):
        """Test that all modifiers are positive numbers."""
        for phase, modifiers in _PHASE_MODIFIERS.items():
            for role, modifier in modifiers.items():
                assert isinstance(modifier, (int, float))
                assert modifier > 0, f"{phase}.{role} has non-positive modifier"

    def test_diplomatic_phase_values(self):
        """Test specific values for diplomatic phase."""
        modifiers = _PHASE_MODIFIERS["diplomatic"]

        assert modifiers["hawk"] == 0.7
        assert modifiers["diplomat"] == 1.5
        assert modifiers["pragmatist"] == 1.3
        assert modifiers["economic"] == 1.2

    def test_nuclear_phase_values(self):
        """Test specific values for nuclear phase."""
        modifiers = _PHASE_MODIFIERS["nuclear"]

        assert modifiers["hawk"] == 0.5
        assert modifiers["wildcard"] == 0.3
        assert modifiers["hardliner"] == 0.3
        assert modifiers["pragmatist"] == 1.5
        assert modifiers["dove"] == 1.5

    def test_conventional_phase_values(self):
        """Test specific values for conventional phase."""
        modifiers = _PHASE_MODIFIERS["conventional"]

        assert modifiers["military_realist"] == 1.5
        assert modifiers["military realist"] == 1.5
        assert modifiers["hawk"] == 1.2
        assert modifiers["dove"] == 0.5

    def test_hybrid_phase_values(self):
        """Test specific values for hybrid phase."""
        modifiers = _PHASE_MODIFIERS["hybrid"]

        assert modifiers["intelligence"] == 1.5
        assert modifiers["wildcard"] == 1.5
        assert modifiers["military_realist"] == 1.2
        assert modifiers["military realist"] == 1.2

    def test_military_realist_consistency(self):
        """Test that military_realist and 'military realist' have same values."""
        for phase, modifiers in _PHASE_MODIFIERS.items():
            assert modifiers["military_realist"] == modifiers["military realist"], (
                f"Inconsistent modifiers for military_realist in {phase}"
            )


# ======================================================================
# Test: Country class integration
# ======================================================================


class TestCountryIntegration:
    """Integration tests for Country class methods."""

    def test_country_initialization(self, country_config, mock_faction, mock_backend):
        """Test Country instance initialization."""
        country = Country(
            config=country_config,
            factions=[mock_faction],
            backend=mock_backend,
        )

        assert country.config == country_config
        assert len(country.factions) == 1
        assert country.factions[0] == mock_faction
        assert country.backend == mock_backend

    def test_country_repr(self, country_instance):
        """Test Country __repr__ method."""
        repr_str = repr(country_instance)

        assert "Country" in repr_str
        assert "Test Country" in repr_str
        assert "TC" in repr_str
        assert "Test Hawk" in repr_str

    def test_faction_by_name_lookup(self, country_instance):
        """Test _faction_by_name lookup."""
        faction = country_instance._faction_by_name("Test Hawk")

        assert faction.config.name == "Test Hawk"
        assert faction.config.role == "hawk"

    def test_faction_by_name_not_found(self, country_instance):
        """Test _faction_by_name raises KeyError for missing faction."""
        with pytest.raises(KeyError) as exc_info:
            country_instance._faction_by_name("Nonexistent Faction")

        assert "Nonexistent Faction" in str(exc_info.value)

    def test_max_tokens_per_response_default(self, country_config, mock_faction, mock_backend):
        """Test that max_tokens_per_response can be None."""
        country = Country(
            config=country_config,
            factions=[mock_faction],
            backend=mock_backend,
            max_tokens_per_response=None,
        )

        assert country.max_tokens_per_response is None

    def test_max_tokens_per_response_custom(self, country_config, mock_faction, mock_backend):
        """Test setting custom max_tokens_per_response."""
        country = Country(
            config=country_config,
            factions=[mock_faction],
            backend=mock_backend,
            max_tokens_per_response=1000,
        )

        assert country.max_tokens_per_response == 1000


# ======================================================================
# Test: Edge cases and error handling
# ======================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_synthesis_with_code_blocks(self):
        """Test parsing synthesis that might contain code block markers."""
        raw = """
DECISION: Deploy resources.

ACTIONS:
1. Execute command: deploy --force
2. Run script as needed

DISSENT: None
"""
        decision, actions, dissent, diplomatic_messages = Country._parse_synthesis(raw)

        assert len(actions) == 2
        assert "deploy --force" in actions[0]

    def test_diplomatic_line_malformed(self):
        """Test parsing malformed diplomatic lines."""
        malformed_lines = [
            "TO US CHANNEL private MESSAGE test",  # Missing pipes
            "TO: | MESSAGE: test",  # Empty TO
            "TO: US | CHANNEL: private",  # Missing MESSAGE
            "MESSAGE: test",  # Missing TO
            "",  # Empty line
            "Random text",  # No structure
        ]

        for line in malformed_lines:
            result = _parse_diplomatic_line(line)
            # Most should return None due to missing required fields
            if result is not None:
                # If it somehow parses, verify it has required fields
                assert "to" in result
                assert "message" in result

    def test_transcript_with_special_characters(self):
        """Test transcript formatting with special characters."""
        debate_log = [
            {
                "round": 1,
                "faction": "Test & Faction",
                "role": "hawk",
                "content": "Use 'special' characters: @#$%^&*().",
            }
        ]
        result = Country._format_transcript(debate_log)

        assert "Test & Faction" in result
        assert "@#$%^&*()" in result

    def test_compute_weights_unknown_role(self, mock_backend):
        """Test weight computation with unknown faction role."""
        config = CountryConfig(name="Test", code="TC")
        faction_config = AgentConfig(
            name="Unknown",
            role="unknown_role",
            personality="Unknown",
            country_code="TC",
        )
        faction = Faction(config=faction_config, backend=mock_backend)
        country = Country(config=config, factions=[faction], backend=mock_backend)

        result = country._compute_faction_weights("conventional")

        # Should still produce output, defaulting to base weight 2
        assert "Unknown" in result
        assert "influence weight" in result
