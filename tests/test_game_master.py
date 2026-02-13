"""Comprehensive unit tests for engine/game_master.py.

Tests cover all pure unit testable functions and LLM-dependent methods with MockBackend.
"""

import pytest
import json

from engine.game_master import GameMaster
from engine.world_state import WorldState, MilitaryUnit


# ======================================================================
# Mock Backend for testing LLM-dependent methods
# ======================================================================

class MockBackend:
    """A mock LLM backend that returns pre-crafted responses."""

    def __init__(self, response="{}"):
        self.response = response
        self.last_system_prompt = None
        self.last_messages = None

    supports_parallel = False

    async def generate(self, system_prompt="", messages=None, temperature=0.7, max_tokens=None):
        """Store the inputs and return the mocked response."""
        self.last_system_prompt = system_prompt
        self.last_messages = messages
        return self.response

    async def close(self):
        """No-op close for mock."""
        pass


# ======================================================================
# Test _validate_resolution (most critical function)
# ======================================================================

class TestValidateResolution:
    """Tests for GameMaster._validate_resolution method."""

    def setup_method(self):
        """Create a GameMaster instance for testing."""
        self.gm = GameMaster(
            backend=MockBackend(),
            scenario_config={"name": "test_scenario"}
        )

    def test_missing_narrative_sets_default(self):
        """Test that missing narrative field gets a default value."""
        parsed = {"world_state_updates": {}}
        result = self.gm._validate_resolution(parsed)
        assert "narrative" in result
        assert result["narrative"] == "The round concluded with various actions unfolding across the theater of operations."

    def test_empty_narrative_sets_default(self):
        """Test that empty narrative string gets a default value."""
        parsed = {"narrative": "", "world_state_updates": {}}
        result = self.gm._validate_resolution(parsed)
        assert result["narrative"] == "The round concluded with various actions unfolding across the theater of operations."

    def test_whitespace_narrative_sets_default(self):
        """Test that whitespace-only narrative gets a default value."""
        parsed = {"narrative": "   \n  ", "world_state_updates": {}}
        result = self.gm._validate_resolution(parsed)
        assert result["narrative"] == "The round concluded with various actions unfolding across the theater of operations."

    def test_non_string_narrative_sets_default(self):
        """Test that non-string narrative gets a default value."""
        parsed = {"narrative": 123, "world_state_updates": {}}
        result = self.gm._validate_resolution(parsed)
        assert result["narrative"] == "The round concluded with various actions unfolding across the theater of operations."

    def test_missing_world_state_updates_sets_empty_dict(self):
        """Test that missing world_state_updates gets an empty dict."""
        parsed = {"narrative": "Something happened"}
        result = self.gm._validate_resolution(parsed)
        assert "world_state_updates" in result
        assert result["world_state_updates"] == {}

    def test_non_dict_world_state_updates_sets_empty_dict(self):
        """Test that non-dict world_state_updates gets replaced with empty dict."""
        parsed = {"narrative": "Something happened", "world_state_updates": []}
        result = self.gm._validate_resolution(parsed)
        assert result["world_state_updates"] == {}

    def test_missing_events_sets_empty_list(self):
        """Test that missing events field gets an empty list."""
        parsed = {"narrative": "Something happened", "world_state_updates": {}}
        result = self.gm._validate_resolution(parsed)
        assert "events" in result
        assert result["events"] == []

    def test_non_list_events_sets_empty_list(self):
        """Test that non-list events field gets replaced with empty list."""
        parsed = {
            "narrative": "Something happened",
            "world_state_updates": {},
            "events": "not a list"
        }
        result = self.gm._validate_resolution(parsed)
        assert result["events"] == []

    def test_missing_headlines_sets_empty_list(self):
        """Test that missing headlines field gets an empty list."""
        parsed = {"narrative": "Something happened", "world_state_updates": {}}
        result = self.gm._validate_resolution(parsed)
        assert "headlines" in result
        assert result["headlines"] == []

    def test_non_list_headlines_sets_empty_list(self):
        """Test that non-list headlines field gets replaced with empty list."""
        parsed = {
            "narrative": "Something happened",
            "world_state_updates": {},
            "headlines": {"title": "wrong type"}
        }
        result = self.gm._validate_resolution(parsed)
        assert result["headlines"] == []

    def test_missing_surprises_sets_empty_list(self):
        """Test that missing surprises field gets an empty list."""
        parsed = {"narrative": "Something happened", "world_state_updates": {}}
        result = self.gm._validate_resolution(parsed)
        assert "surprises" in result
        assert result["surprises"] == []

    def test_empty_parsed_dict(self):
        """Test that completely empty dict gets all defaults."""
        parsed = {}
        result = self.gm._validate_resolution(parsed)
        assert result["narrative"] == "The round concluded with various actions unfolding across the theater of operations."
        assert result["world_state_updates"] == {}
        assert result["events"] == []
        assert result["headlines"] == []
        assert result["surprises"] == []

    def test_military_unit_non_dict_removed(self):
        """Test that non-dict military unit entries are removed."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "readiness": 5},
                    "not a dict",
                    {"name": "Unit 2", "strength": 8},
                    123,
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        assert len(result["world_state_updates"]["military_units_update"]) == 2
        assert result["world_state_updates"]["military_units_update"][0]["name"] == "Unit 1"
        assert result["world_state_updates"]["military_units_update"][1]["name"] == "Unit 2"

    def test_military_unit_missing_name_removed(self):
        """Test that military units without name field are removed."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "readiness": 5},
                    {"location": "Suwalki", "readiness": 8},  # missing name
                    {"name": "Unit 2", "strength": 8},
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        assert len(result["world_state_updates"]["military_units_update"]) == 2
        assert result["world_state_updates"]["military_units_update"][0]["name"] == "Unit 1"
        assert result["world_state_updates"]["military_units_update"][1]["name"] == "Unit 2"

    def test_military_unit_non_numeric_readiness_removed(self):
        """Test that non-numeric readiness field is removed from unit."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "readiness": "high", "strength": 7}
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        unit = result["world_state_updates"]["military_units_update"][0]
        assert "readiness" not in unit
        assert unit["strength"] == 7

    def test_military_unit_readiness_clamped_to_1_10(self):
        """Test that readiness values are clamped to 1-10 range."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "readiness": 0},
                    {"name": "Unit 2", "readiness": 15},
                    {"name": "Unit 3", "readiness": 5.7},  # float should convert to int
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        units = result["world_state_updates"]["military_units_update"]
        assert units[0]["readiness"] == 1  # clamped from 0
        assert units[1]["readiness"] == 10  # clamped from 15
        assert units[2]["readiness"] == 5  # converted from 5.7

    def test_military_unit_strength_clamped_to_1_10(self):
        """Test that strength values are clamped to 1-10 range."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "strength": -5},
                    {"name": "Unit 2", "strength": 100},
                    {"name": "Unit 3", "strength": 3},
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        units = result["world_state_updates"]["military_units_update"]
        assert units[0]["strength"] == 1  # clamped from -5
        assert units[1]["strength"] == 10  # clamped from 100
        assert units[2]["strength"] == 3  # unchanged

    def test_military_unit_supply_level_clamped_to_1_10(self):
        """Test that supply_level values are clamped to 1-10 range."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "supply_level": 0},
                    {"name": "Unit 2", "supply_level": 20},
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        units = result["world_state_updates"]["military_units_update"]
        assert units[0]["supply_level"] == 1  # clamped from 0
        assert units[1]["supply_level"] == 10  # clamped from 20

    def test_military_unit_morale_clamped_to_1_10(self):
        """Test that morale values are clamped to 1-10 range."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "morale": -10},
                    {"name": "Unit 2", "morale": 50},
                    {"name": "Unit 3", "morale": 7},
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        units = result["world_state_updates"]["military_units_update"]
        assert units[0]["morale"] == 1  # clamped from -10
        assert units[1]["morale"] == 10  # clamped from 50
        assert units[2]["morale"] == 7  # unchanged

    def test_military_unit_casualties_clamped_to_zero_minimum(self):
        """Test that casualties cannot be negative."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "casualties": -50},
                    {"name": "Unit 2", "casualties": 100},
                    {"name": "Unit 3", "casualties": 0},
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        units = result["world_state_updates"]["military_units_update"]
        assert units[0]["casualties"] == 0  # clamped from -50
        assert units[1]["casualties"] == 100  # unchanged
        assert units[2]["casualties"] == 0  # unchanged

    def test_military_unit_non_numeric_fields_removed(self):
        """Test that all non-numeric stats are removed from unit."""
        parsed = {
            "narrative": "Battle ensued",
            "world_state_updates": {
                "military_units_update": [
                    {
                        "name": "Unit 1",
                        "readiness": "very high",
                        "strength": [1, 2, 3],
                        "supply_level": {"level": 5},
                        "morale": None,
                        "casualties": "many",
                    }
                ]
            }
        }
        result = self.gm._validate_resolution(parsed)
        unit = result["world_state_updates"]["military_units_update"][0]
        assert "readiness" not in unit
        assert "strength" not in unit
        assert "supply_level" not in unit
        assert "morale" not in unit
        assert "casualties" not in unit
        assert unit["name"] == "Unit 1"  # name is preserved

    def test_public_opinion_non_dict_entry_removed(self):
        """Test that non-dict public opinion entries are removed."""
        parsed = {
            "narrative": "Public reacts",
            "world_state_updates": {
                "public_opinion": {
                    "USA": {"war_support": 50, "government_approval": 60},
                    "Russia": "not a dict",
                    "Poland": {"war_support": 70, "government_approval": 55},
                }
            }
        }
        result = self.gm._validate_resolution(parsed)
        po = result["world_state_updates"]["public_opinion"]
        assert "USA" in po
        assert "Russia" not in po
        assert "Poland" in po

    def test_public_opinion_war_support_clamped_to_0_100(self):
        """Test that war_support values are clamped to 0-100 range."""
        parsed = {
            "narrative": "Public reacts",
            "world_state_updates": {
                "public_opinion": {
                    "USA": {"war_support": -10},
                    "Russia": {"war_support": 150},
                    "Poland": {"war_support": 50},
                }
            }
        }
        result = self.gm._validate_resolution(parsed)
        po = result["world_state_updates"]["public_opinion"]
        assert po["USA"]["war_support"] == 0  # clamped from -10
        assert po["Russia"]["war_support"] == 100  # clamped from 150
        assert po["Poland"]["war_support"] == 50  # unchanged

    def test_public_opinion_government_approval_clamped_to_0_100(self):
        """Test that government_approval values are clamped to 0-100 range."""
        parsed = {
            "narrative": "Public reacts",
            "world_state_updates": {
                "public_opinion": {
                    "USA": {"government_approval": -50},
                    "Russia": {"government_approval": 200},
                    "Poland": {"government_approval": 75},
                }
            }
        }
        result = self.gm._validate_resolution(parsed)
        po = result["world_state_updates"]["public_opinion"]
        assert po["USA"]["government_approval"] == 0  # clamped from -50
        assert po["Russia"]["government_approval"] == 100  # clamped from 200
        assert po["Poland"]["government_approval"] == 75  # unchanged

    def test_public_opinion_non_numeric_values_removed(self):
        """Test that non-numeric public opinion values are removed."""
        parsed = {
            "narrative": "Public reacts",
            "world_state_updates": {
                "public_opinion": {
                    "USA": {
                        "war_support": "very high",
                        "government_approval": [70]
                    }
                }
            }
        }
        result = self.gm._validate_resolution(parsed)
        po = result["world_state_updates"]["public_opinion"]["USA"]
        assert "war_support" not in po
        assert "government_approval" not in po

    def test_valid_resolution_passes_unchanged(self):
        """Test that a completely valid resolution passes through unchanged."""
        parsed = {
            "narrative": "A tense standoff continued in the Suwalki Gap.",
            "world_state_updates": {
                "game_time": "Day 2, 14:00",
                "military_units_update": [
                    {
                        "name": "1st Armored Division",
                        "location": "Suwalki",
                        "readiness": 8,
                        "strength": 9,
                        "casualties": 5,
                        "supply_level": 7,
                        "morale": 8
                    }
                ],
                "public_opinion": {
                    "USA": {"war_support": 45, "government_approval": 52}
                },
                "nato_alert_level": "high"
            },
            "events": ["Russia reinforced positions", "NATO deployed air assets"],
            "headlines": ["Tensions rise in Baltic region"],
            "surprises": ["Cyber attack on Polish power grid"]
        }
        result = self.gm._validate_resolution(parsed)

        # Should be identical to input
        assert result["narrative"] == parsed["narrative"]
        assert result["world_state_updates"]["game_time"] == "Day 2, 14:00"
        assert len(result["world_state_updates"]["military_units_update"]) == 1
        unit = result["world_state_updates"]["military_units_update"][0]
        assert unit["readiness"] == 8
        assert unit["strength"] == 9
        assert unit["casualties"] == 5
        assert unit["supply_level"] == 7
        assert unit["morale"] == 8
        assert result["world_state_updates"]["public_opinion"]["USA"]["war_support"] == 45
        assert len(result["events"]) == 2
        assert len(result["headlines"]) == 1
        assert len(result["surprises"]) == 1


# ======================================================================
# Test _validate_intel
# ======================================================================

class TestValidateIntel:
    """Tests for GameMaster._validate_intel method."""

    def setup_method(self):
        """Create a GameMaster instance for testing."""
        self.gm = GameMaster(
            backend=MockBackend(),
            scenario_config={"name": "test_scenario"}
        )

    def test_missing_intel_briefing_sets_default(self):
        """Test that missing intel_briefing field gets a default value."""
        parsed = {"items": []}
        result = self.gm._validate_intel(parsed)
        assert "intel_briefing" in result
        assert result["intel_briefing"] == "Intelligence briefing unavailable at this time."

    def test_non_string_intel_briefing_sets_default(self):
        """Test that non-string intel_briefing gets a default value."""
        parsed = {"intel_briefing": 123, "items": []}
        result = self.gm._validate_intel(parsed)
        assert result["intel_briefing"] == "Intelligence briefing unavailable at this time."

    def test_missing_items_sets_empty_list(self):
        """Test that missing items field gets an empty list."""
        parsed = {"intel_briefing": "Classified briefing"}
        result = self.gm._validate_intel(parsed)
        assert "items" in result
        assert result["items"] == []

    def test_non_list_items_sets_empty_list(self):
        """Test that non-list items field gets replaced with empty list."""
        parsed = {"intel_briefing": "Classified briefing", "items": "not a list"}
        result = self.gm._validate_intel(parsed)
        assert result["items"] == []

    def test_non_dict_items_skipped(self):
        """Test that non-dict items are filtered out."""
        parsed = {
            "intel_briefing": "Classified briefing",
            "items": [
                {"type": "sigint", "content": "Intercepted communication"},
                "not a dict",
                {"type": "humint", "content": "Agent report"},
                123,
                None,
            ]
        }
        result = self.gm._validate_intel(parsed)
        assert len(result["items"]) == 2
        assert result["items"][0]["type"] == "sigint"
        assert result["items"][1]["type"] == "humint"

    def test_items_missing_type_skipped(self):
        """Test that items missing 'type' field are filtered out."""
        parsed = {
            "intel_briefing": "Classified briefing",
            "items": [
                {"type": "sigint", "content": "Intercepted communication"},
                {"content": "Missing type field"},  # missing type
                {"type": "humint", "content": "Agent report"},
            ]
        }
        result = self.gm._validate_intel(parsed)
        assert len(result["items"]) == 2
        assert result["items"][0]["type"] == "sigint"
        assert result["items"][1]["type"] == "humint"

    def test_items_missing_content_skipped(self):
        """Test that items missing 'content' field are filtered out."""
        parsed = {
            "intel_briefing": "Classified briefing",
            "items": [
                {"type": "sigint", "content": "Intercepted communication"},
                {"type": "osint"},  # missing content
                {"type": "humint", "content": "Agent report"},
            ]
        }
        result = self.gm._validate_intel(parsed)
        assert len(result["items"]) == 2
        assert result["items"][0]["content"] == "Intercepted communication"
        assert result["items"][1]["content"] == "Agent report"

    def test_valid_items_preserved(self):
        """Test that valid items with all fields are preserved."""
        parsed = {
            "intel_briefing": "Classified briefing",
            "items": [
                {
                    "type": "sigint",
                    "content": "Intercepted radio traffic",
                    "confidence": "high",
                    "reliability": "A",
                    "caveat": "Source may be compromised"
                },
                {
                    "type": "humint",
                    "content": "Asset reports troop movements",
                    "confidence": "medium",
                    "reliability": "B",
                    "caveat": "Unconfirmed"
                }
            ]
        }
        result = self.gm._validate_intel(parsed)
        assert len(result["items"]) == 2

        # Check all fields preserved
        item1 = result["items"][0]
        assert item1["type"] == "sigint"
        assert item1["content"] == "Intercepted radio traffic"
        assert item1["confidence"] == "high"
        assert item1["reliability"] == "A"
        assert item1["caveat"] == "Source may be compromised"

        item2 = result["items"][1]
        assert item2["type"] == "humint"
        assert item2["confidence"] == "medium"

    def test_empty_parsed_dict(self):
        """Test that empty dict gets all defaults."""
        parsed = {}
        result = self.gm._validate_intel(parsed)
        assert result["intel_briefing"] == "Intelligence briefing unavailable at this time."
        assert result["items"] == []


# ======================================================================
# Test record_round_summary
# ======================================================================

class TestRecordRoundSummary:
    """Tests for GameMaster.record_round_summary method."""

    def setup_method(self):
        """Create a GameMaster instance for testing."""
        self.gm = GameMaster(
            backend=MockBackend(),
            scenario_config={"name": "test_scenario"}
        )

    def test_stores_summary_in_history(self):
        """Test that summary is stored in _round_history."""
        self.gm.record_round_summary(
            round_num=1,
            briefing_summary="Initial situation tense",
            key_decisions=["NATO mobilized", "Russia reinforced"],
            resolution_summary="Standoff continues"
        )

        assert len(self.gm._round_history) == 1
        summary = self.gm._round_history[0]
        assert summary["round"] == 1
        assert summary["briefing_summary"] == "Initial situation tense"
        assert summary["key_decisions"] == ["NATO mobilized", "Russia reinforced"]
        assert summary["resolution_summary"] == "Standoff continues"

    def test_contains_correct_fields(self):
        """Test that stored summary has all required fields."""
        self.gm.record_round_summary(
            round_num=2,
            briefing_summary="Tensions escalate",
            key_decisions=["Air strikes launched"],
            resolution_summary="Limited engagement"
        )

        summary = self.gm._round_history[0]
        assert "round" in summary
        assert "briefing_summary" in summary
        assert "key_decisions" in summary
        assert "resolution_summary" in summary

    def test_trims_to_max_5_entries(self):
        """Test that history is trimmed to last 5 rounds."""
        # Add 7 rounds
        for i in range(1, 8):
            self.gm.record_round_summary(
                round_num=i,
                briefing_summary=f"Round {i} summary",
                key_decisions=[f"Decision {i}"],
                resolution_summary=f"Resolution {i}"
            )

        # Should only keep last 5
        assert len(self.gm._round_history) == 5

        # Check that it kept rounds 3-7
        assert self.gm._round_history[0]["round"] == 3
        assert self.gm._round_history[1]["round"] == 4
        assert self.gm._round_history[2]["round"] == 5
        assert self.gm._round_history[3]["round"] == 6
        assert self.gm._round_history[4]["round"] == 7

    def test_multiple_summaries_appended(self):
        """Test that multiple summaries are appended in order."""
        self.gm.record_round_summary(1, "Brief 1", ["Dec 1"], "Res 1")
        self.gm.record_round_summary(2, "Brief 2", ["Dec 2"], "Res 2")
        self.gm.record_round_summary(3, "Brief 3", ["Dec 3"], "Res 3")

        assert len(self.gm._round_history) == 3
        assert self.gm._round_history[0]["round"] == 1
        assert self.gm._round_history[1]["round"] == 2
        assert self.gm._round_history[2]["round"] == 3


# ======================================================================
# Test _build_history_context
# ======================================================================

class TestBuildHistoryContext:
    """Tests for GameMaster._build_history_context method."""

    def setup_method(self):
        """Create a GameMaster instance for testing."""
        self.gm = GameMaster(
            backend=MockBackend(),
            scenario_config={"name": "test_scenario"}
        )

    def test_empty_history_returns_empty_string(self):
        """Test that empty history returns empty string."""
        result = self.gm._build_history_context()
        assert result == ""

    def test_formats_single_round_correctly(self):
        """Test that a single round is formatted correctly."""
        self.gm.record_round_summary(
            round_num=1,
            briefing_summary="Initial brief",
            key_decisions=["Deploy troops", "Impose sanctions"],
            resolution_summary="First round completed"
        )

        result = self.gm._build_history_context()

        assert "PREVIOUS ROUNDS SUMMARY:" in result
        assert "Round 1:" in result
        assert "First round completed" in result
        assert "Deploy troops; Impose sanctions" in result

    def test_respects_max_rounds_limit(self):
        """Test that max_rounds parameter limits output."""
        # Add 5 rounds
        for i in range(1, 6):
            self.gm.record_round_summary(
                round_num=i,
                briefing_summary=f"Brief {i}",
                key_decisions=[f"Decision {i}"],
                resolution_summary=f"Resolution {i}"
            )

        # Request only last 2 rounds
        result = self.gm._build_history_context(max_rounds=2)

        assert "Round 4:" in result
        assert "Round 5:" in result
        assert "Round 3:" not in result
        assert "Round 2:" not in result
        assert "Round 1:" not in result

    def test_truncates_key_decisions_to_3(self):
        """Test that key_decisions are truncated to first 3 items."""
        self.gm.record_round_summary(
            round_num=1,
            briefing_summary="Brief",
            key_decisions=["Dec1", "Dec2", "Dec3", "Dec4", "Dec5"],
            resolution_summary="Resolution"
        )

        result = self.gm._build_history_context()

        # Should only include first 3 decisions
        assert "Dec1; Dec2; Dec3" in result
        assert "Dec4" not in result
        assert "Dec5" not in result

    def test_handles_no_decisions(self):
        """Test handling of empty key_decisions list."""
        self.gm.record_round_summary(
            round_num=1,
            briefing_summary="Brief",
            key_decisions=[],
            resolution_summary="Resolution"
        )

        result = self.gm._build_history_context()

        assert "No major actions" in result

    def test_multiple_rounds_formatted_correctly(self):
        """Test that multiple rounds are formatted correctly."""
        self.gm.record_round_summary(1, "Brief1", ["Dec1"], "Res1")
        self.gm.record_round_summary(2, "Brief2", ["Dec2"], "Res2")
        self.gm.record_round_summary(3, "Brief3", ["Dec3"], "Res3")

        result = self.gm._build_history_context()

        assert "Round 1: Res1" in result
        assert "Round 2: Res2" in result
        assert "Round 3: Res3" in result

        # Check order
        idx1 = result.index("Round 1:")
        idx2 = result.index("Round 2:")
        idx3 = result.index("Round 3:")
        assert idx1 < idx2 < idx3

    def test_includes_blank_line_at_end(self):
        """Test that formatted history ends with blank line."""
        self.gm.record_round_summary(1, "Brief", ["Dec"], "Res")
        result = self.gm._build_history_context()
        # The function adds an empty string to lines, which creates a single newline at end
        assert result.endswith("\n")


# ======================================================================
# Test LLM-dependent methods with MockBackend
# ======================================================================

class TestGenerateSituationBriefing:
    """Tests for GameMaster.generate_situation_briefing with MockBackend."""

    @pytest.mark.asyncio
    async def test_parses_json_response(self):
        """Test that JSON response is parsed correctly."""
        mock_response = json.dumps({
            "briefing": "The situation in the Suwalki Gap remains tense as forces face off."
        })
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})
        ws = WorldState(round_number=1)

        result = await gm.generate_situation_briefing(ws, round_num=1)

        assert result == "The situation in the Suwalki Gap remains tense as forces face off."

    @pytest.mark.asyncio
    async def test_previous_round_summary_injected(self):
        """Test that previous_round_summary is added to prompt."""
        mock_response = json.dumps({"briefing": "Updated situation"})
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})
        ws = WorldState(round_number=2)

        previous_summary = "Previous round saw escalation"
        await gm.generate_situation_briefing(
            ws,
            round_num=2,
            previous_round_summary=previous_summary
        )

        # Check that the summary was included in the prompt
        prompt = backend.last_messages[0]["content"]
        assert previous_summary in prompt
        assert "IMPORTANT: The briefing must reflect what CHANGED" in prompt

    @pytest.mark.asyncio
    async def test_history_context_included(self):
        """Test that round history is included in prompt."""
        mock_response = json.dumps({"briefing": "Situation briefing"})
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})

        # Add some history
        gm.record_round_summary(1, "Brief1", ["Dec1"], "Res1")
        gm.record_round_summary(2, "Brief2", ["Dec2"], "Res2")

        ws = WorldState(round_number=3)
        await gm.generate_situation_briefing(ws, round_num=3)

        prompt = backend.last_messages[0]["content"]
        assert "PREVIOUS ROUNDS SUMMARY:" in prompt
        assert "Round 1:" in prompt
        assert "Round 2:" in prompt


class TestResolveActions:
    """Tests for GameMaster.resolve_actions with MockBackend."""

    @pytest.mark.asyncio
    async def test_parses_and_validates_response(self):
        """Test that JSON response is parsed and validated."""
        mock_response = json.dumps({
            "narrative": "Forces engaged in the gap",
            "world_state_updates": {
                "game_time": "Day 2, 06:00"
            },
            "events": ["Event 1"],
            "headlines": ["Headline 1"],
            "surprises": []
        })
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})
        ws = WorldState(round_number=1)

        result = await gm.resolve_actions(ws, all_country_decisions=[])

        assert result["narrative"] == "Forces engaged in the gap"
        assert result["world_state_updates"]["game_time"] == "Day 2, 06:00"
        assert len(result["events"]) == 1
        assert len(result["headlines"]) == 1
        assert len(result["surprises"]) == 0

    @pytest.mark.asyncio
    async def test_validation_applied_to_parsed_result(self):
        """Test that validation fixes invalid responses."""
        # Missing narrative, invalid military unit
        mock_response = json.dumps({
            "world_state_updates": {
                "military_units_update": [
                    {"name": "Unit 1", "readiness": 15},  # Will be clamped to 10
                    {"location": "Unknown"},  # Missing name, will be removed
                ]
            },
            "events": [],
            "headlines": []
        })
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})
        ws = WorldState(round_number=1)

        result = await gm.resolve_actions(ws, all_country_decisions=[])

        # Narrative should have default
        assert result["narrative"] == "The round concluded with various actions unfolding across the theater of operations."

        # Invalid unit removed, valid unit clamped
        units = result["world_state_updates"]["military_units_update"]
        assert len(units) == 1
        assert units[0]["name"] == "Unit 1"
        assert units[0]["readiness"] == 10  # clamped

    @pytest.mark.asyncio
    async def test_history_context_included_in_resolution(self):
        """Test that round history is included in resolution prompt."""
        mock_response = json.dumps({
            "narrative": "Resolution narrative",
            "world_state_updates": {},
            "events": [],
            "headlines": [],
            "surprises": []
        })
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})

        # Add history
        gm.record_round_summary(1, "Brief1", ["Dec1"], "Res1")

        ws = WorldState(round_number=2)
        decisions = [{"country": "USA", "actions": ["Deploy forces"]}]

        await gm.resolve_actions(ws, all_country_decisions=decisions)

        prompt = backend.last_messages[0]["content"]
        assert "PREVIOUS ROUNDS SUMMARY:" in prompt
        assert "Round 1:" in prompt


class TestGeneratePrivateIntel:
    """Tests for GameMaster.generate_private_intel with MockBackend."""

    @pytest.mark.asyncio
    async def test_parses_and_validates_intel(self):
        """Test that intel response is parsed and validated."""
        mock_response = json.dumps({
            "intel_briefing": "Classified intelligence report",
            "items": [
                {
                    "type": "sigint",
                    "content": "Intercepted communication",
                    "confidence": "high"
                }
            ]
        })
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})
        ws = WorldState()

        result = await gm.generate_private_intel(ws, country_code="USA")

        assert "Classified intelligence report" in result
        assert "SIGINT" in result
        assert "Intercepted communication" in result

    @pytest.mark.asyncio
    async def test_validation_applied_to_intel(self):
        """Test that intel validation filters invalid items."""
        mock_response = json.dumps({
            "intel_briefing": "Briefing text",
            "items": [
                {"type": "sigint", "content": "Valid item"},
                {"type": "humint"},  # Missing content, will be filtered
                "not a dict",  # Will be filtered
            ]
        })
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})
        ws = WorldState()

        result = await gm.generate_private_intel(ws, country_code="Poland")

        # Should only include valid item
        assert "Valid item" in result
        # Should not crash and should include briefing text
        assert "Briefing text" in result

    @pytest.mark.asyncio
    async def test_formats_intel_items_correctly(self):
        """Test that intel items are formatted in the output."""
        mock_response = json.dumps({
            "intel_briefing": "Top secret briefing",
            "items": [
                {
                    "type": "sigint",
                    "content": "Enemy communication intercepted",
                    "confidence": "high",
                    "reliability": "A",
                    "caveat": "Source may be compromised"
                },
                {
                    "type": "humint",
                    "content": "Agent reports movement",
                    "confidence": "medium",
                    "reliability": "B"
                }
            ],
            "intelligence_gaps": ["Unknown troop positions", "Enemy intentions unclear"]
        })
        backend = MockBackend(response=mock_response)
        gm = GameMaster(backend=backend, scenario_config={})
        ws = WorldState()

        result = await gm.generate_private_intel(ws, country_code="NATO")

        # Check formatting
        assert "Top secret briefing" in result
        assert "INTELLIGENCE ITEMS:" in result
        assert "[SIGINT | Reliability: A | Confidence: HIGH]" in result
        assert "Enemy communication intercepted" in result
        assert "CAVEAT: Source may be compromised" in result
        assert "[HUMINT | Reliability: B | Confidence: MEDIUM]" in result
        assert "Agent reports movement" in result
        assert "INTELLIGENCE GAPS (what we do NOT know):" in result
        assert "Unknown troop positions" in result
        assert "Enemy intentions unclear" in result


# ======================================================================
# Run tests
# ======================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
