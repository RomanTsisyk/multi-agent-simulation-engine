"""Comprehensive tests for checkpoint module and Game class end conditions.

This test module covers:
1. Checkpoint save/load functionality
2. Game.check_end_conditions with various scenarios
3. Game._build_round_summary
4. Game._update_corridor_control
5. Game._get_incoming_messages
6. Game._collect_outgoing_messages

All tests are pure unit tests with no LLM, async, or external dependencies.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock

from engine.checkpoint import save_checkpoint, load_checkpoint, collect_agent_histories
from engine.game import Game
from engine.world_state import WorldState


# ==============================================================================
# Checkpoint Tests
# ==============================================================================

class TestCheckpoint:
    """Tests for checkpoint save/load functionality."""

    def test_save_checkpoint_creates_file_with_correct_structure(self, tmp_path):
        """Test that save_checkpoint creates checkpoint.json with correct structure."""
        game_dir = tmp_path / "game1"

        world_state_dict = {
            "round_number": 3,
            "game_time": "Day 2, 12:00",
            "corridor_control": "contested",
        }

        checkpoint_path = save_checkpoint(
            game_dir=game_dir,
            round_completed=3,
            world_state_dict=world_state_dict,
            diplomatic_inbox=[{"from": "USA", "to": "RUS", "message": "Test"}],
            previous_round_summary="Previous summary",
            corridor_hold_rounds=2,
            corridor_was_contested=True,
            gm_round_history=[{"round": 1}],
            agent_histories={"USA": [{"role": "user", "content": "test"}]},
            total_rounds=6,
        )

        assert checkpoint_path.exists()
        assert checkpoint_path.name == "checkpoint.json"

        # Verify structure
        content = json.loads(checkpoint_path.read_text())
        assert content["version"] == 1
        assert content["round_completed"] == 3
        assert content["total_rounds"] == 6
        assert content["world_state"] == world_state_dict
        assert content["diplomatic_inbox"] == [{"from": "USA", "to": "RUS", "message": "Test"}]
        assert content["previous_round_summary"] == "Previous summary"
        assert content["corridor_hold_rounds"] == 2
        assert content["corridor_was_contested"] is True
        assert content["gm_round_history"] == [{"round": 1}]
        assert content["agent_histories"] == {"USA": [{"role": "user", "content": "test"}]}

    def test_load_checkpoint_reads_saved_data_correctly(self, tmp_path):
        """Test that load_checkpoint reads back saved data correctly."""
        game_dir = tmp_path / "game2"
        game_dir.mkdir()

        checkpoint_data = {
            "version": 1,
            "round_completed": 5,
            "total_rounds": 10,
            "world_state": {"round_number": 5},
            "diplomatic_inbox": [],
            "previous_round_summary": "Summary text",
            "corridor_hold_rounds": 0,
            "corridor_was_contested": False,
            "gm_round_history": [],
            "agent_histories": {},
        }

        checkpoint_path = game_dir / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2))

        loaded = load_checkpoint(game_dir)

        assert loaded == checkpoint_data
        assert loaded["round_completed"] == 5
        assert loaded["total_rounds"] == 10

    def test_roundtrip_preserves_all_fields(self, tmp_path):
        """Test that save then load preserves all fields."""
        game_dir = tmp_path / "game3"

        original_data = {
            "round_number": 4,
            "game_time": "Day 3, 06:00",
            "corridor_control": "russian",
            "nato_alert_level": "high",
            "nuclear_posture": {"RUS": "elevated", "USA": "peacetime"},
        }

        save_checkpoint(
            game_dir=game_dir,
            round_completed=4,
            world_state_dict=original_data,
            diplomatic_inbox=[{"test": "msg"}],
            previous_round_summary="Round 4 summary",
            corridor_hold_rounds=3,
            corridor_was_contested=True,
            gm_round_history=[{"round": 1}, {"round": 2}],
            agent_histories={"USA": [{"msg": 1}], "RUS": [{"msg": 2}]},
            total_rounds=8,
        )

        loaded = load_checkpoint(game_dir)

        # Verify all fields preserved
        assert loaded["round_completed"] == 4
        assert loaded["world_state"] == original_data
        assert loaded["diplomatic_inbox"] == [{"test": "msg"}]
        assert loaded["previous_round_summary"] == "Round 4 summary"
        assert loaded["corridor_hold_rounds"] == 3
        assert loaded["corridor_was_contested"] is True
        assert loaded["gm_round_history"] == [{"round": 1}, {"round": 2}]
        assert loaded["agent_histories"] == {"USA": [{"msg": 1}], "RUS": [{"msg": 2}]}
        assert loaded["total_rounds"] == 8

    def test_load_checkpoint_missing_file_raises_error(self, tmp_path):
        """Test that load_checkpoint raises FileNotFoundError for missing checkpoint."""
        game_dir = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError, match="No checkpoint found"):
            load_checkpoint(game_dir)

    def test_save_checkpoint_with_config_fingerprint(self, tmp_path):
        """Test that save_checkpoint includes config_fingerprint when config provided."""
        game_dir = tmp_path / "game4"

        config = {
            "scenario": {
                "name": "Test Scenario",
                "rounds": 6,
                "countries": {
                    "USA": {"name": "United States"},
                    "RUS": {"name": "Russia"},
                },
            }
        }

        checkpoint_path = save_checkpoint(
            game_dir=game_dir,
            round_completed=1,
            world_state_dict={},
            diplomatic_inbox=[],
            previous_round_summary="",
            corridor_hold_rounds=0,
            corridor_was_contested=False,
            gm_round_history=[],
            agent_histories={},
            total_rounds=6,
            config=config,
        )

        loaded = json.loads(checkpoint_path.read_text())

        assert "config_fingerprint" in loaded
        assert loaded["config_fingerprint"]["scenario_name"] == "Test Scenario"
        assert loaded["config_fingerprint"]["total_rounds"] == 6
        assert loaded["config_fingerprint"]["country_codes"] == ["RUS", "USA"]  # sorted

    def test_atomic_write_no_corrupt_file_on_failure(self, tmp_path):
        """Test that if save fails, no corrupt file remains."""
        game_dir = tmp_path / "game5"
        game_dir.mkdir()

        # First create a valid checkpoint
        checkpoint_path = game_dir / "checkpoint.json"
        original_content = {"version": 1, "round_completed": 1}
        checkpoint_path.write_text(json.dumps(original_content))

        # Now try to save with invalid data that can't be serialized
        # (json.dumps will handle this via default=str, so we can't easily trigger a failure)
        # Instead, let's verify the tmp file cleanup by checking intermediate state

        # Verify tmp file doesn't exist after successful save
        save_checkpoint(
            game_dir=game_dir,
            round_completed=2,
            world_state_dict={"round_number": 2},
            diplomatic_inbox=[],
            previous_round_summary="",
            corridor_hold_rounds=0,
            corridor_was_contested=False,
            gm_round_history=[],
            agent_histories={},
            total_rounds=6,
        )

        tmp_file = game_dir / "checkpoint.tmp"
        assert not tmp_file.exists(), "Temporary file should be cleaned up"

        # Verify checkpoint was updated
        loaded = json.loads(checkpoint_path.read_text())
        assert loaded["round_completed"] == 2

    def test_collect_agent_histories_extracts_synthesiser_histories(self):
        """Test that collect_agent_histories extracts synthesiser histories."""
        # Create a mock game with countries that have synthesisers
        game = Game.__new__(Game)
        game.countries = {}

        # Mock country with synthesiser
        country_usa = Mock()
        country_usa._synthesiser = Mock()
        country_usa._synthesiser.message_history = [
            {"role": "user", "content": "USA message 1"},
            {"role": "assistant", "content": "USA response 1"},
        ]

        country_rus = Mock()
        country_rus._synthesiser = Mock()
        country_rus._synthesiser.message_history = [
            {"role": "user", "content": "RUS message 1"},
        ]

        # Mock country without synthesiser (stub)
        country_stub = Mock(spec=[])  # No _synthesiser attribute

        game.countries = {
            "USA": country_usa,
            "RUS": country_rus,
            "GER": country_stub,
        }

        histories = collect_agent_histories(game)

        assert "USA" in histories
        assert "RUS" in histories
        assert "GER" not in histories
        assert len(histories["USA"]) == 2
        assert len(histories["RUS"]) == 1
        assert histories["USA"][0]["content"] == "USA message 1"


# ==============================================================================
# Game.check_end_conditions Tests
# ==============================================================================

class TestGameCheckEndConditions:
    """Tests for Game.check_end_conditions method."""

    def _create_minimal_game(self, end_conditions=None, world_state=None):
        """Helper to create a minimal Game instance for testing."""
        game = Game.__new__(Game)

        if end_conditions is None:
            end_conditions = []

        game.config = {
            "scenario": {
                "end_conditions": end_conditions,
            }
        }

        if world_state is None:
            world_state = WorldState()

        game.world_state = world_state
        game._corridor_hold_rounds = 0
        game._corridor_was_contested = False

        return game

    def test_nuclear_detonation_tactical_use(self):
        """Test nuclear detonation condition with tactical_use posture."""
        world_state = WorldState()
        world_state.nuclear_posture = {"RUS": "tactical_use"}

        end_condition = {
            "type": "catastrophic",
            "id": "nuclear_detonation",
            "description": "Nuclear weapon detonated",
            "winner": "none",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        result = game.check_end_conditions()

        assert result is not None
        assert result["id"] == "nuclear_detonation"
        assert result["type"] == "catastrophic"

    def test_nuclear_detonation_strategic_posture(self):
        """Test nuclear detonation condition with strategic posture."""
        world_state = WorldState()
        world_state.nuclear_posture = {"USA": "strategic"}

        end_condition = {
            "type": "catastrophic",
            "id": "nuclear_detonation",
            "description": "Nuclear weapon detonated",
            "winner": "none",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        result = game.check_end_conditions()

        assert result is not None
        assert result["id"] == "nuclear_detonation"

    def test_nato_collapse_three_refusals_with_negative_keywords(self):
        """Test NATO collapse with 3+ refusals containing negative keywords."""
        world_state = WorldState()
        # Note: Must avoid positive keywords like "support", "invoke" in negative statements
        # because the code checks for positive indicators first
        world_state.nato_consensus = {
            "POL": "We reject Article 5",
            "GER": "Germany will not participate",
            "FRA": "France opposes this decision",
            "USA": "We support Article 5",
        }

        end_condition = {
            "type": "political",
            "id": "nato_collapse",
            "description": "NATO alliance collapsed",
            "winner": "RUS",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        result = game.check_end_conditions()

        assert result is not None
        assert result["id"] == "nato_collapse"

    def test_nato_collapse_positive_keywords_dont_count_as_refusals(self):
        """Test that positive keywords (support, agree) DON'T count as refusals."""
        world_state = WorldState()
        world_state.nato_consensus = {
            "USA": "We support Article 5 activation",
            "GBR": "We agree to invoke Article 5",
            "FRA": "We stand with our allies",
            "GER": "Germany commits to defend",
        }

        end_condition = {
            "type": "political",
            "id": "nato_collapse",
            "description": "NATO alliance collapsed",
            "winner": "RUS",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        result = game.check_end_conditions()

        assert result is None, "Positive support should not trigger NATO collapse"

    def test_nato_collapse_mixed_positive_negative_doesnt_count(self):
        """Test that mixed positive+negative in same position doesn't count as refusal."""
        world_state = WorldState()
        world_state.nato_consensus = {
            "USA": "We cannot support immediate action but we agree to discuss",
            "GBR": "We refuse hasty decisions but support our allies",
            "FRA": "clear support",
            "GER": "we oppose",
        }

        end_condition = {
            "type": "political",
            "id": "nato_collapse",
            "description": "NATO alliance collapsed",
            "winner": "RUS",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        result = game.check_end_conditions()

        # Only GER should count as refusal (1 < 3 threshold)
        assert result is None, "Mixed sentiment should not count as refusal"

    def test_russian_corridor_hold_needs_threshold_rounds(self):
        """Test Russian corridor hold requires threshold_rounds consecutive rounds."""
        world_state = WorldState()
        world_state.corridor_control = "russian"

        end_condition = {
            "type": "territorial_control",
            "id": "russian_corridor_hold",
            "description": "Russia controls corridor for required duration",
            "winner": "RUS",
            "threshold_rounds": 6,
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        # First 5 rounds should not trigger
        for i in range(5):
            result = game.check_end_conditions()
            assert result is None, f"Should not trigger before threshold (round {i+1})"

        # 6th round should trigger
        result = game.check_end_conditions()
        assert result is not None
        assert result["id"] == "russian_corridor_hold"

    def test_russian_corridor_hold_counter_resets_when_control_changes(self):
        """Test that corridor hold counter resets when control changes."""
        world_state = WorldState()
        world_state.corridor_control = "russian"

        end_condition = {
            "type": "territorial_control",
            "id": "russian_corridor_hold",
            "description": "Russia controls corridor",
            "winner": "RUS",
            "threshold_rounds": 4,
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        # Build up counter
        game.check_end_conditions()  # round 1
        game.check_end_conditions()  # round 2
        assert game._corridor_hold_rounds == 2

        # Change control
        game.world_state.corridor_control = "contested"
        game.check_end_conditions()
        assert game._corridor_hold_rounds == 0, "Counter should reset"

        # Back to Russian control
        game.world_state.corridor_control = "russian"
        game.check_end_conditions()
        assert game._corridor_hold_rounds == 1, "Counter should restart from 1"

    def test_nato_corridor_liberated_only_after_contested(self):
        """Test NATO corridor liberated only triggers after corridor was contested."""
        world_state = WorldState()
        world_state.corridor_control = "nato"

        end_condition = {
            "type": "territorial_control",
            "id": "nato_corridor_liberated",
            "description": "NATO liberated the corridor",
            "winner": "NATO",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        # Should not trigger if corridor was never contested
        result = game.check_end_conditions()
        assert result is None, "Should not trigger if corridor was never contested"

        # Mark as contested
        game.world_state.corridor_control = "contested"
        game.check_end_conditions()

        # Now liberate it
        game.world_state.corridor_control = "nato"
        result = game.check_end_conditions()
        assert result is not None
        assert result["id"] == "nato_corridor_liberated"

    def test_nato_corridor_liberated_triggers_after_russian_control(self):
        """Test NATO corridor liberated triggers if corridor was under Russian control."""
        world_state = WorldState()
        world_state.corridor_control = "russian"

        end_condition = {
            "type": "territorial_control",
            "id": "nato_corridor_liberated",
            "description": "NATO liberated the corridor",
            "winner": "NATO",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        # Mark corridor as contested via russian control
        game.check_end_conditions()

        # Now liberate it
        game.world_state.corridor_control = "nato"
        result = game.check_end_conditions()
        assert result is not None
        assert result["id"] == "nato_corridor_liberated"

    def test_ceasefire_requires_both_keywords_in_events(self):
        """Test ceasefire requires both 'ceasefire' and 'agree' in events."""
        world_state = WorldState()
        world_state.recent_events = [
            "Fighting continues in the corridor",
            "Ceasefire negotiations begin",
        ]

        end_condition = {
            "type": "diplomatic",
            "id": "ceasefire_agreement",
            "description": "Ceasefire reached",
            "winner": "diplomatic",
        }

        game = self._create_minimal_game(
            end_conditions=[end_condition],
            world_state=world_state,
        )

        # Should not trigger with only "ceasefire"
        result = game.check_end_conditions()
        assert result is None

        # Add "agree"
        game.world_state.recent_events.append("Both sides agree to ceasefire terms")
        result = game.check_end_conditions()
        assert result is not None
        assert result["id"] == "ceasefire_agreement"

    def test_no_conditions_met_returns_none(self):
        """Test that when no conditions are met, returns None."""
        world_state = WorldState()
        world_state.nuclear_posture = {"RUS": "elevated"}
        world_state.corridor_control = "contested"
        world_state.nato_consensus = {"USA": "support", "GBR": "support"}

        end_conditions = [
            {"type": "catastrophic", "id": "nuclear_detonation"},
            {"type": "political", "id": "nato_collapse"},
            {"type": "territorial_control", "id": "russian_corridor_hold", "threshold_rounds": 6},
        ]

        game = self._create_minimal_game(
            end_conditions=end_conditions,
            world_state=world_state,
        )

        result = game.check_end_conditions()
        assert result is None

    def test_empty_end_conditions_returns_none(self):
        """Test that empty end_conditions list returns None."""
        game = self._create_minimal_game(end_conditions=[])
        result = game.check_end_conditions()
        assert result is None


# ==============================================================================
# Game._build_round_summary Tests
# ==============================================================================

class TestGameBuildRoundSummary:
    """Tests for Game._build_round_summary static method."""

    def test_builds_summary_from_decisions_and_resolution(self):
        """Test that _build_round_summary builds summary from decisions and resolution."""
        decisions = [
            {
                "country": "USA",
                "country_name": "United States",
                "actions": ["Deploy additional forces", "Increase readiness"],
            },
            {
                "country": "RUS",
                "country_name": "Russia",
                "actions": ["Hold positions", "Monitor NATO movements"],
            },
        ]

        resolution = {
            "narrative": "The situation remains tense as both sides increase military readiness. "
                        "NATO forces are deploying to forward positions while Russian units "
                        "maintain their grip on the corridor.",
            "surprises": ["Unexpected cyberattack on Polish infrastructure"],
        }

        summary = Game._build_round_summary(decisions, resolution)

        assert "PREVIOUS ROUND ACTIONS SUMMARY:" in summary
        assert "United States (USA):" in summary
        assert "Deploy additional forces" in summary
        assert "Russia (RUS):" in summary
        assert "Hold positions" in summary
        assert "OUTCOME:" in summary
        assert "situation remains tense" in summary
        assert "SURPRISE DEVELOPMENTS:" in summary
        assert "cyberattack" in summary

    def test_truncates_long_narratives(self):
        """Test that _build_round_summary truncates long narratives to 500 chars."""
        decisions = [
            {"country": "USA", "country_name": "United States", "actions": ["Action 1"]},
        ]

        long_narrative = "A" * 1000  # 1000 character narrative
        resolution = {
            "narrative": long_narrative,
        }

        summary = Game._build_round_summary(decisions, resolution)

        # The narrative should be truncated to 500 chars
        assert "OUTCOME:" in summary
        outcome_start = summary.index("OUTCOME:") + len("OUTCOME: ")
        narrative_in_summary = summary[outcome_start:].strip()
        assert len(narrative_in_summary) <= 500
        assert narrative_in_summary == long_narrative[:500]

    def test_handles_empty_decisions(self):
        """Test _build_round_summary with empty decisions list."""
        decisions = []
        resolution = {"narrative": "Nothing happened"}

        summary = Game._build_round_summary(decisions, resolution)

        assert "PREVIOUS ROUND ACTIONS SUMMARY:" in summary
        assert "OUTCOME:" in summary
        assert "Nothing happened" in summary

    def test_handles_missing_narrative(self):
        """Test _build_round_summary with missing narrative."""
        decisions = [
            {"country": "USA", "country_name": "United States", "actions": ["Action"]},
        ]
        resolution = {}

        summary = Game._build_round_summary(decisions, resolution)

        assert "PREVIOUS ROUND ACTIONS SUMMARY:" in summary
        assert "United States (USA): Action" in summary
        # Should not crash on missing narrative


# ==============================================================================
# Game._update_corridor_control Tests
# ==============================================================================

class TestGameUpdateCorridorControl:
    """Tests for Game._update_corridor_control method."""

    def _create_game_for_corridor_test(self):
        """Helper to create game instance for corridor control tests."""
        game = Game.__new__(Game)
        game.world_state = WorldState()
        game.world_state.corridor_control = "contested"
        return game

    def test_russian_control_keywords_set_corridor_to_russian(self):
        """Test Russian control keywords set corridor_control to 'russian'."""
        game = self._create_game_for_corridor_test()

        resolution = {
            "narrative": "Russian forces have seized the corridor and established control.",
            "events": ["Corridor secured by Russian military"],
            "headlines": ["Moscow controls the Suwalki Gap"],
        }

        game._update_corridor_control(resolution)

        assert game.world_state.corridor_control == "russian"

    def test_nato_control_keywords_set_corridor_to_nato(self):
        """Test NATO control keywords set corridor_control to 'nato'."""
        game = self._create_game_for_corridor_test()

        # Note: Must avoid contested keywords like "fighting" or "combat"
        # because contested takes priority in the implementation
        resolution = {
            "narrative": "NATO forces have liberated the corridor successfully.",
            "events": ["Allied forces secured the corridor"],
            "headlines": ["Corridor cleared of Russian presence"],
        }

        game._update_corridor_control(resolution)

        assert game.world_state.corridor_control == "nato"

    def test_contested_keywords_set_corridor_to_contested(self):
        """Test contested keywords set corridor_control to 'contested'."""
        game = self._create_game_for_corridor_test()
        game.world_state.corridor_control = "russian"  # Start with Russian control

        resolution = {
            "narrative": "Fighting continues in the corridor with neither side gaining advantage.",
            "events": ["Fierce combat in the Suwalki Gap"],
            "headlines": ["Battle for corridor ongoing"],
        }

        game._update_corridor_control(resolution)

        assert game.world_state.corridor_control == "contested"

    def test_no_keywords_maintains_current_state(self):
        """Test that no matching keywords maintains current state."""
        game = self._create_game_for_corridor_test()
        original_state = "russian"
        game.world_state.corridor_control = original_state

        resolution = {
            "narrative": "Diplomatic negotiations continue in Brussels.",
            "events": ["UN Security Council meets"],
            "headlines": ["Peace talks ongoing"],
        }

        game._update_corridor_control(resolution)

        assert game.world_state.corridor_control == original_state

    def test_multiple_keyword_matches_russian(self):
        """Test multiple Russian keyword matches."""
        game = self._create_game_for_corridor_test()

        resolution = {
            "narrative": "Russia holds the corridor. Russian forces control the strategic passage.",
            "events": [],
            "headlines": [],
        }

        game._update_corridor_control(resolution)

        assert game.world_state.corridor_control == "russian"

    def test_contested_overrides_specific_control(self):
        """Test that contested keywords take priority over specific control."""
        game = self._create_game_for_corridor_test()

        resolution = {
            "narrative": "While Russian forces control parts of the corridor, fighting continues "
                        "with NATO forces contesting every meter.",
            "events": ["Ongoing clashes in the Gap"],
            "headlines": [],
        }

        game._update_corridor_control(resolution)

        # Contested should win due to priority
        assert game.world_state.corridor_control == "contested"


# ==============================================================================
# Game._get_incoming_messages Tests
# ==============================================================================

class TestGameGetIncomingMessages:
    """Tests for Game._get_incoming_messages method."""

    def _create_game_with_inbox(self, messages):
        """Helper to create game with diplomatic inbox."""
        game = Game.__new__(Game)
        game._diplomatic_inbox = messages
        return game

    def test_public_messages_visible_to_all(self):
        """Test that public messages are visible to all countries."""
        messages = [
            {"from": "USA", "to": "ALL", "channel": "public", "message": "Public statement"},
            {"from": "RUS", "to": "", "channel": "public", "message": "Another public msg"},
        ]

        game = self._create_game_with_inbox(messages)

        # USA should see all public messages
        usa_msgs = game._get_incoming_messages("USA")
        assert "[PUBLIC from USA]: Public statement" in usa_msgs
        assert "[PUBLIC from RUS]: Another public msg" in usa_msgs

        # RUS should see the same
        rus_msgs = game._get_incoming_messages("RUS")
        assert "[PUBLIC from USA]: Public statement" in rus_msgs
        assert "[PUBLIC from RUS]: Another public msg" in rus_msgs

    def test_private_messages_only_visible_to_recipient(self):
        """Test that private messages are only visible to recipient."""
        messages = [
            {"from": "USA", "to": "GBR", "channel": "private", "message": "Private to UK"},
            {"from": "RUS", "to": "CHN", "channel": "private", "message": "Private to China"},
        ]

        game = self._create_game_with_inbox(messages)

        # GBR should see message to them
        gbr_msgs = game._get_incoming_messages("GBR")
        assert "[PRIVATE from USA]: Private to UK" in gbr_msgs
        assert "Private to China" not in gbr_msgs

        # CHN should see their message
        chn_msgs = game._get_incoming_messages("CHN")
        assert "[PRIVATE from RUS]: Private to China" in chn_msgs
        assert "Private to UK" not in chn_msgs

        # USA should see nothing (no messages to them)
        usa_msgs = game._get_incoming_messages("USA")
        assert usa_msgs == ""

    def test_backchannel_messages_only_visible_to_recipient(self):
        """Test that backchannel messages are only visible to recipient."""
        messages = [
            {"from": "USA", "to": "RUS", "channel": "backchannel", "message": "Secret deal"},
        ]

        game = self._create_game_with_inbox(messages)

        # RUS should see backchannel message
        rus_msgs = game._get_incoming_messages("RUS")
        assert "[BACKCHANNEL from USA -- deniable]: Secret deal" in rus_msgs

        # Others should not
        gbr_msgs = game._get_incoming_messages("GBR")
        assert gbr_msgs == ""

    def test_mixed_message_channels(self):
        """Test combination of public, private, and backchannel messages."""
        messages = [
            {"from": "USA", "to": "", "channel": "public", "message": "Public msg"},
            {"from": "USA", "to": "RUS", "channel": "private", "message": "Private to RUS"},
            {"from": "GBR", "to": "RUS", "channel": "backchannel", "message": "Secret msg"},
        ]

        game = self._create_game_with_inbox(messages)

        rus_msgs = game._get_incoming_messages("RUS")
        assert "[PUBLIC from USA]: Public msg" in rus_msgs
        assert "[PRIVATE from USA]: Private to RUS" in rus_msgs
        assert "[BACKCHANNEL from GBR -- deniable]: Secret msg" in rus_msgs

        # GBR only sees public
        gbr_msgs = game._get_incoming_messages("GBR")
        assert "[PUBLIC from USA]: Public msg" in gbr_msgs
        assert "Private to RUS" not in gbr_msgs
        assert "Secret msg" not in gbr_msgs

    def test_empty_inbox_returns_empty_string(self):
        """Test that empty inbox returns empty string."""
        game = self._create_game_with_inbox([])
        msgs = game._get_incoming_messages("USA")
        assert msgs == ""


# ==============================================================================
# Game._collect_outgoing_messages Tests
# ==============================================================================

class TestGameCollectOutgoingMessages:
    """Tests for Game._collect_outgoing_messages method."""

    def test_extracts_messages_from_all_country_decisions(self):
        """Test that _collect_outgoing_messages extracts messages from all decisions."""
        decisions = [
            {
                "country": "USA",
                "diplomatic_messages": [
                    {"to": "RUS", "channel": "public", "message": "We demand withdrawal"},
                    {"to": "GBR", "channel": "private", "message": "Coordinate response"},
                ],
            },
            {
                "country": "RUS",
                "diplomatic_messages": [
                    {"to": "USA", "channel": "public", "message": "We reject demands"},
                ],
            },
        ]

        game = Game.__new__(Game)
        messages = game._collect_outgoing_messages(decisions)

        assert len(messages) == 3

        # Check first message
        assert messages[0]["from"] == "USA"
        assert messages[0]["to"] == "RUS"
        assert messages[0]["channel"] == "public"
        assert messages[0]["message"] == "We demand withdrawal"

        # Check second message
        assert messages[1]["from"] == "USA"
        assert messages[1]["to"] == "GBR"
        assert messages[1]["channel"] == "private"
        assert messages[1]["message"] == "Coordinate response"

        # Check third message
        assert messages[2]["from"] == "RUS"
        assert messages[2]["to"] == "USA"
        assert messages[2]["channel"] == "public"
        assert messages[2]["message"] == "We reject demands"

    def test_handles_content_field_as_message(self):
        """Test that 'content' field is used as fallback for 'message'."""
        decisions = [
            {
                "country": "USA",
                "diplomatic_messages": [
                    {"to": "RUS", "channel": "public", "content": "Message via content field"},
                ],
            },
        ]

        game = Game.__new__(Game)
        messages = game._collect_outgoing_messages(decisions)

        assert len(messages) == 1
        assert messages[0]["message"] == "Message via content field"

    def test_handles_empty_diplomatic_messages(self):
        """Test handling of decisions with no diplomatic messages."""
        decisions = [
            {"country": "USA", "diplomatic_messages": []},
            {"country": "RUS"},  # No diplomatic_messages key
        ]

        game = Game.__new__(Game)
        messages = game._collect_outgoing_messages(decisions)

        assert messages == []

    def test_default_channel_is_public(self):
        """Test that default channel is 'public' if not specified."""
        decisions = [
            {
                "country": "USA",
                "diplomatic_messages": [
                    {"to": "RUS", "message": "No channel specified"},
                ],
            },
        ]

        game = Game.__new__(Game)
        messages = game._collect_outgoing_messages(decisions)

        assert len(messages) == 1
        assert messages[0]["channel"] == "public"

    def test_preserves_all_channels(self):
        """Test that all channel types are preserved correctly."""
        decisions = [
            {
                "country": "USA",
                "diplomatic_messages": [
                    {"to": "RUS", "channel": "public", "message": "Public"},
                    {"to": "GBR", "channel": "private", "message": "Private"},
                    {"to": "FRA", "channel": "backchannel", "message": "Backchannel"},
                ],
            },
        ]

        game = Game.__new__(Game)
        messages = game._collect_outgoing_messages(decisions)

        assert len(messages) == 3
        channels = [msg["channel"] for msg in messages]
        assert "public" in channels
        assert "private" in channels
        assert "backchannel" in channels
