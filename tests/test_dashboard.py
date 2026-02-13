"""Comprehensive unit tests for engine/dashboard.py.

Tests cover:
- compute_escalation_level function
- GameStatus dataclass
- Dashboard initialization
- Dashboard.update method
- Dashboard._write_status method
"""

import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from engine.dashboard import (
    Dashboard,
    GameStatus,
    compute_escalation_level,
    _escalation_label,
)


class TestComputeEscalationLevel:
    """Tests for the compute_escalation_level function."""

    def test_empty_dict(self):
        """Test with empty world state dict.

        Note: corridor_control defaults to 'contested' which adds +1.
        """
        result = compute_escalation_level({})
        assert result == 1  # Default corridor_control='contested' adds +1

    def test_nato_alert_normal(self):
        """Test NATO alert level: normal.

        Note: corridor_control defaults to 'contested' which adds +1.
        """
        world_state = {"nato_alert_level": "normal"}
        result = compute_escalation_level(world_state)
        assert result == 1  # 0 (nato) + 1 (default contested corridor)

    def test_nato_alert_elevated(self):
        """Test NATO alert level: elevated."""
        world_state = {"nato_alert_level": "elevated"}
        result = compute_escalation_level(world_state)
        assert result == 2  # 1 (nato elevated) + 1 (default contested corridor)

    def test_nato_alert_high(self):
        """Test NATO alert level: high."""
        world_state = {"nato_alert_level": "high"}
        result = compute_escalation_level(world_state)
        assert result == 4  # 3 (nato high) + 1 (default contested corridor)

    def test_nato_alert_article5(self):
        """Test NATO alert level: article5."""
        world_state = {"nato_alert_level": "article5"}
        result = compute_escalation_level(world_state)
        assert result == 6  # 5 (nato article5) + 1 (default contested corridor)

    def test_nato_alert_unknown_defaults_to_zero(self):
        """Test unknown NATO alert level defaults to 0."""
        world_state = {"nato_alert_level": "unknown_level"}
        result = compute_escalation_level(world_state)
        assert result == 1  # 0 (unknown nato) + 1 (default contested corridor)

    def test_nuclear_posture_peacetime(self):
        """Test nuclear posture: peacetime."""
        world_state = {"nuclear_posture": {"Russia": "peacetime"}}
        result = compute_escalation_level(world_state)
        assert result == 1  # 0 (peacetime) + 1 (default contested corridor)

    def test_nuclear_posture_elevated(self):
        """Test nuclear posture: elevated."""
        world_state = {"nuclear_posture": {"Russia": "elevated"}}
        result = compute_escalation_level(world_state)
        assert result == 2  # 1 (elevated) + 1 (default contested corridor)

    def test_nuclear_posture_dispersal(self):
        """Test nuclear posture: dispersal."""
        world_state = {"nuclear_posture": {"Russia": "dispersal"}}
        result = compute_escalation_level(world_state)
        assert result == 3  # 2 (dispersal) + 1 (default contested corridor)

    def test_nuclear_posture_launch_ready(self):
        """Test nuclear posture: launch_ready."""
        world_state = {"nuclear_posture": {"Russia": "launch_ready"}}
        result = compute_escalation_level(world_state)
        assert result == 5  # 4 (launch_ready) + 1 (default contested corridor)

    def test_nuclear_posture_launch_ready(self):
        """Test nuclear posture: launch_ready (highest valid level)."""
        world_state = {"nuclear_posture": {"Russia": "launch_ready"}}
        result = compute_escalation_level(world_state)
        assert result == 5  # 4 (launch_ready) + 1 (default contested corridor)

    def test_nuclear_posture_invalid_ignored(self):
        """Test invalid nuclear posture values are ignored (default to 0)."""
        world_state = {"nuclear_posture": {"Russia": "tactical_use"}}
        result = compute_escalation_level(world_state)
        assert result == 1  # 0 (invalid) + 1 (default contested corridor)

    def test_nuclear_posture_multiple_powers_uses_max(self):
        """Test multiple nuclear powers - uses maximum posture score."""
        world_state = {
            "nuclear_posture": {
                "Russia": "elevated",  # 1
                "USA": "dispersal",  # 2
                "China": "launch_ready",  # 4
            }
        }
        result = compute_escalation_level(world_state)
        assert result == 5  # 4 (max launch_ready) + 1 (default contested corridor)

    def test_nuclear_posture_unknown_defaults_to_zero(self):
        """Test unknown nuclear posture defaults to 0."""
        world_state = {"nuclear_posture": {"Russia": "unknown_posture"}}
        result = compute_escalation_level(world_state)
        assert result == 1  # 0 (unknown) + 1 (default contested corridor)

    def test_corridor_control_russian(self):
        """Test corridor control: russian."""
        world_state = {"corridor_control": "russian"}
        result = compute_escalation_level(world_state)
        assert result == 1

    def test_corridor_control_contested(self):
        """Test corridor control: contested."""
        world_state = {"corridor_control": "contested"}
        result = compute_escalation_level(world_state)
        assert result == 1

    def test_corridor_control_nato(self):
        """Test corridor control: nato (no bonus)."""
        world_state = {"corridor_control": "nato"}
        result = compute_escalation_level(world_state)
        assert result == 0

    def test_nato_alert_isolated_with_nato_corridor(self):
        """Test NATO alert level isolated (with NATO corridor to avoid default)."""
        world_state = {
            "nato_alert_level": "high",
            "corridor_control": "nato",  # Explicitly set to avoid default
        }
        result = compute_escalation_level(world_state)
        assert result == 3  # Just the NATO high alert

    def test_nuclear_posture_isolated_with_nato_corridor(self):
        """Test nuclear posture isolated (with NATO corridor to avoid default)."""
        world_state = {
            "nuclear_posture": {"Russia": "dispersal"},
            "corridor_control": "nato",  # Explicitly set to avoid default
        }
        result = compute_escalation_level(world_state)
        assert result == 2  # Just the dispersal score

    def test_combined_scoring(self):
        """Test combined scoring from multiple factors."""
        world_state = {
            "nato_alert_level": "high",  # +3
            "nuclear_posture": {"Russia": "dispersal"},  # +2
            "corridor_control": "contested",  # +1
        }
        result = compute_escalation_level(world_state)
        assert result == 6

    def test_clamped_to_max_10(self):
        """Test escalation level is clamped to max of 10."""
        world_state = {
            "nato_alert_level": "article5",  # +5
            "nuclear_posture": {"Russia": "launch_ready"},  # +4
            "corridor_control": "russian",  # +1
        }
        # Total is exactly 10
        result = compute_escalation_level(world_state)
        assert result == 10

    def test_clamped_to_min_0(self):
        """Test escalation level is clamped to min of 0 (edge case)."""
        world_state = {"nato_alert_level": "normal"}
        result = compute_escalation_level(world_state)
        assert result >= 0

    def test_missing_fields_default_to_zero(self):
        """Test that missing fields in dict default to 0 contribution.

        Note: corridor_control defaults to 'contested' which adds +1.
        """
        world_state = {"some_other_field": "value"}
        result = compute_escalation_level(world_state)
        assert result == 1  # 0 (other fields) + 1 (default contested corridor)

    def test_empty_nuclear_posture_dict(self):
        """Test with empty nuclear_posture dictionary."""
        world_state = {"nuclear_posture": {}}
        result = compute_escalation_level(world_state)
        assert result == 1  # 0 (empty nuclear) + 1 (default contested corridor)


class TestEscalationLabel:
    """Tests for the _escalation_label helper function."""

    def test_level_0_normal(self):
        """Test level 0 maps to NORMAL."""
        assert _escalation_label(0) == "NORMAL"

    def test_level_1_normal(self):
        """Test level 1 maps to NORMAL."""
        assert _escalation_label(1) == "NORMAL"

    def test_level_2_elevated(self):
        """Test level 2 maps to ELEVATED."""
        assert _escalation_label(2) == "ELEVATED"

    def test_level_3_elevated(self):
        """Test level 3 maps to ELEVATED."""
        assert _escalation_label(3) == "ELEVATED"

    def test_level_4_high(self):
        """Test level 4 maps to HIGH."""
        assert _escalation_label(4) == "HIGH"

    def test_level_5_high(self):
        """Test level 5 maps to HIGH."""
        assert _escalation_label(5) == "HIGH"

    def test_level_6_severe(self):
        """Test level 6 maps to SEVERE."""
        assert _escalation_label(6) == "SEVERE"

    def test_level_7_severe(self):
        """Test level 7 maps to SEVERE."""
        assert _escalation_label(7) == "SEVERE"

    def test_level_8_critical(self):
        """Test level 8 maps to CRITICAL."""
        assert _escalation_label(8) == "CRITICAL"

    def test_level_9_critical(self):
        """Test level 9 maps to CRITICAL."""
        assert _escalation_label(9) == "CRITICAL"

    def test_level_10_nuclear(self):
        """Test level 10 maps to NUCLEAR."""
        assert _escalation_label(10) == "NUCLEAR"


class TestGameStatus:
    """Tests for the GameStatus dataclass."""

    def test_default_values(self):
        """Test GameStatus default values."""
        status = GameStatus()
        assert status.scenario_name == ""
        assert status.total_rounds == 0
        assert status.current_round == 0
        assert status.phase == "setup"
        assert status.current_country == ""
        assert status.current_country_index == 0
        assert status.total_countries == 0
        assert status.faction_index == 0
        assert status.total_factions == 0
        assert status.debate_round == 0
        assert status.escalation_level == 0
        assert status.escalation_label == "NORMAL"
        assert status.last_headlines == []
        assert status.round_times == []
        assert status.eta_seconds == 0.0
        assert status.game_start_time == 0.0
        assert status.elapsed_seconds == 0.0
        assert status.is_running is False
        assert status.error == ""

    def test_custom_values(self):
        """Test GameStatus with custom values."""
        status = GameStatus(
            scenario_name="Test Scenario",
            total_rounds=10,
            current_round=5,
            phase="deliberation",
        )
        assert status.scenario_name == "Test Scenario"
        assert status.total_rounds == 10
        assert status.current_round == 5
        assert status.phase == "deliberation"

    def test_field_types(self):
        """Test GameStatus field types."""
        status = GameStatus(
            scenario_name="Test",
            total_rounds=10,
            current_round=5,
            escalation_level=7,
            last_headlines=["Headline 1", "Headline 2"],
            round_times=[1.5, 2.3, 1.8],
            eta_seconds=45.5,
            game_start_time=1234567890.0,
            elapsed_seconds=100.5,
            is_running=True,
        )
        assert isinstance(status.scenario_name, str)
        assert isinstance(status.total_rounds, int)
        assert isinstance(status.current_round, int)
        assert isinstance(status.escalation_level, int)
        assert isinstance(status.last_headlines, list)
        assert isinstance(status.round_times, list)
        assert isinstance(status.eta_seconds, float)
        assert isinstance(status.game_start_time, float)
        assert isinstance(status.elapsed_seconds, float)
        assert isinstance(status.is_running, bool)

    def test_mutable_default_fields_are_independent(self):
        """Test that mutable default fields are independent across instances."""
        status1 = GameStatus()
        status2 = GameStatus()

        status1.last_headlines.append("Test")
        status1.round_times.append(1.5)

        assert status2.last_headlines == []
        assert status2.round_times == []


class TestDashboardInit:
    """Tests for Dashboard.__init__ method."""

    def test_init_with_all_parameters(self, tmp_path):
        """Test Dashboard initialization with all parameters."""
        game_dir = tmp_path / "game_session"
        dashboard = Dashboard(
            game_dir=game_dir,
            total_rounds=10,
            num_countries=5,
            scenario_name="Test Scenario",
        )

        assert dashboard.game_dir == game_dir
        assert dashboard.status.total_rounds == 10
        assert dashboard.status.total_countries == 5
        assert dashboard.status.scenario_name == "Test Scenario"
        assert dashboard._live is None
        assert isinstance(dashboard._has_rich, bool)

    def test_init_with_none_game_dir(self):
        """Test Dashboard initialization with None game_dir."""
        dashboard = Dashboard(game_dir=None, total_rounds=5)
        assert dashboard.game_dir is None
        assert dashboard.status.total_rounds == 5

    def test_init_with_string_game_dir(self, tmp_path):
        """Test Dashboard initialization with string game_dir."""
        game_dir_str = str(tmp_path / "game_session")
        dashboard = Dashboard(game_dir=game_dir_str)
        assert dashboard.game_dir == Path(game_dir_str)

    def test_init_with_default_values(self):
        """Test Dashboard initialization with default values."""
        dashboard = Dashboard()
        assert dashboard.game_dir is None
        assert dashboard.status.total_rounds == 10
        assert dashboard.status.total_countries == 0
        assert dashboard.status.scenario_name == ""

    def test_init_status_fields(self):
        """Test that GameStatus is properly initialized in Dashboard."""
        dashboard = Dashboard(
            total_rounds=8,
            num_countries=3,
            scenario_name="Scenario A",
        )

        assert dashboard.status.scenario_name == "Scenario A"
        assert dashboard.status.total_rounds == 8
        assert dashboard.status.total_countries == 3
        assert dashboard.status.current_round == 0
        assert dashboard.status.phase == "setup"


class TestDashboardUpdate:
    """Tests for Dashboard.update method."""

    def test_update_phase(self, tmp_path):
        """Test updating phase only."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(phase="briefing")
        assert dashboard.status.phase == "briefing"

    def test_update_round_num(self, tmp_path):
        """Test updating round_num only."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(round_num=5)
        assert dashboard.status.current_round == 5

    def test_update_country(self, tmp_path):
        """Test updating country only."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(country="Russia")
        assert dashboard.status.current_country == "Russia"

    def test_update_country_index(self, tmp_path):
        """Test updating country_index only."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(country_index=2)
        assert dashboard.status.current_country_index == 2

    def test_update_faction_index(self, tmp_path):
        """Test updating faction_index only."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(faction_index=1)
        assert dashboard.status.faction_index == 1

    def test_update_total_factions(self, tmp_path):
        """Test updating total_factions only."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(total_factions=3)
        assert dashboard.status.total_factions == 3

    def test_update_debate_round(self, tmp_path):
        """Test updating debate_round only."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(debate_round=2)
        assert dashboard.status.debate_round == 2

    def test_update_escalation_level_and_label(self, tmp_path):
        """Test updating escalation_level also updates escalation_label."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(escalation_level=8)
        assert dashboard.status.escalation_level == 8
        assert dashboard.status.escalation_label == "CRITICAL"

        dashboard.update(escalation_level=2)
        assert dashboard.status.escalation_level == 2
        assert dashboard.status.escalation_label == "ELEVATED"

    def test_update_headlines_truncates_to_last_3(self, tmp_path):
        """Test updating headlines truncates to last 3."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        headlines = ["H1", "H2", "H3", "H4", "H5"]
        dashboard.update(headlines=headlines)
        assert dashboard.status.last_headlines == ["H3", "H4", "H5"]

    def test_update_headlines_fewer_than_3(self, tmp_path):
        """Test updating headlines with fewer than 3 items."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        headlines = ["H1", "H2"]
        dashboard.update(headlines=headlines)
        assert dashboard.status.last_headlines == ["H1", "H2"]

    def test_update_headlines_exactly_3(self, tmp_path):
        """Test updating headlines with exactly 3 items."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        headlines = ["H1", "H2", "H3"]
        dashboard.update(headlines=headlines)
        assert dashboard.status.last_headlines == ["H1", "H2", "H3"]

    def test_update_round_time_appends(self, tmp_path):
        """Test updating round_time appends to round_times list."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(round_time=1.5)
        dashboard.update(round_time=2.3)
        dashboard.update(round_time=1.8)

        assert dashboard.status.round_times == [1.5, 2.3, 1.8]

    def test_update_error(self, tmp_path):
        """Test updating error field."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(error="Test error message")
        assert dashboard.status.error == "Test error message"

    def test_update_multiple_fields(self, tmp_path):
        """Test updating multiple fields at once."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(
            phase="deliberation",
            round_num=3,
            country="China",
            escalation_level=5,
            headlines=["Breaking news"],
        )

        assert dashboard.status.phase == "deliberation"
        assert dashboard.status.current_round == 3
        assert dashboard.status.current_country == "China"
        assert dashboard.status.escalation_level == 5
        assert dashboard.status.escalation_label == "HIGH"
        assert dashboard.status.last_headlines == ["Breaking news"]

    def test_update_none_fields_are_ignored(self, tmp_path):
        """Test that None fields do not overwrite existing values."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        # Set initial values
        dashboard.update(phase="briefing", round_num=5, country="Russia")

        # Update with None values - should not change anything
        dashboard.update(phase=None, round_num=None, country=None)

        assert dashboard.status.phase == "briefing"
        assert dashboard.status.current_round == 5
        assert dashboard.status.current_country == "Russia"

    def test_update_calculates_eta_from_round_times(self, tmp_path):
        """Test that ETA is calculated from round_times."""
        dashboard = Dashboard(game_dir=tmp_path / "game", total_rounds=10)
        dashboard.status.game_start_time = time.time()
        dashboard.status.current_round = 3

        # Add round times: average = (60 + 90 + 75) / 3 = 75 seconds
        dashboard.update(round_time=60.0)
        dashboard.update(round_time=90.0)
        dashboard.update(round_time=75.0)

        # Remaining rounds = 10 - 3 = 7
        # ETA = 75 * 7 = 525 seconds
        assert dashboard.status.eta_seconds == 525.0

    def test_update_eta_when_current_round_equals_total_rounds(self, tmp_path):
        """Test that ETA is not updated when current_round >= total_rounds."""
        dashboard = Dashboard(game_dir=tmp_path / "game", total_rounds=10)
        dashboard.status.game_start_time = time.time()
        dashboard.status.current_round = 10

        dashboard.update(round_time=60.0)

        # ETA should not be calculated when current >= total
        assert dashboard.status.eta_seconds == 0.0

    def test_update_eta_when_current_round_exceeds_total_rounds(self, tmp_path):
        """Test that ETA is not updated when current_round > total_rounds."""
        dashboard = Dashboard(game_dir=tmp_path / "game", total_rounds=10)
        dashboard.status.game_start_time = time.time()
        dashboard.status.current_round = 11

        dashboard.update(round_time=60.0)

        # ETA should not be calculated when current > total
        assert dashboard.status.eta_seconds == 0.0

    def test_update_eta_with_no_round_times(self, tmp_path):
        """Test that ETA is 0 when there are no round_times."""
        dashboard = Dashboard(game_dir=tmp_path / "game", total_rounds=10)
        dashboard.status.game_start_time = time.time()
        dashboard.status.current_round = 3

        dashboard.update(phase="briefing")

        assert dashboard.status.eta_seconds == 0.0

    def test_update_calculates_elapsed_seconds(self, tmp_path):
        """Test that elapsed_seconds is calculated on each update."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        start_time = time.time()
        dashboard.status.game_start_time = start_time

        # Wait a tiny bit
        time.sleep(0.01)

        dashboard.update(phase="briefing")

        # elapsed_seconds should be > 0 and approximately the time waited
        assert dashboard.status.elapsed_seconds > 0
        assert dashboard.status.elapsed_seconds < 1.0  # Should be small

    @patch("engine.dashboard.Dashboard._write_status")
    def test_update_calls_write_status(self, mock_write, tmp_path):
        """Test that update calls _write_status."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        dashboard.update(phase="briefing")

        mock_write.assert_called_once()

    @patch("engine.dashboard.Dashboard._write_status")
    def test_update_with_rich_live_updates_display(self, mock_write, tmp_path):
        """Test that update calls _live.update when Rich is available."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.status.game_start_time = time.time()

        # Mock the _live object
        mock_live = Mock()
        dashboard._live = mock_live

        dashboard.update(phase="briefing")

        # Should call _live.update
        mock_live.update.assert_called_once()


class TestDashboardWriteStatus:
    """Tests for Dashboard._write_status method."""

    def test_write_status_creates_directory(self, tmp_path):
        """Test that _write_status creates the game directory."""
        game_dir = tmp_path / "new_game_dir"
        dashboard = Dashboard(game_dir=game_dir)
        dashboard.status.scenario_name = "Test"

        dashboard._write_status()

        assert game_dir.exists()
        assert game_dir.is_dir()

    def test_write_status_creates_status_json(self, tmp_path):
        """Test that _write_status creates status.json file."""
        game_dir = tmp_path / "game"
        dashboard = Dashboard(game_dir=game_dir)
        dashboard.status.scenario_name = "Test"

        dashboard._write_status()

        status_file = game_dir / "status.json"
        assert status_file.exists()
        assert status_file.is_file()

    def test_write_status_json_content(self, tmp_path):
        """Test that _write_status writes correct JSON content."""
        game_dir = tmp_path / "game"
        dashboard = Dashboard(
            game_dir=game_dir,
            total_rounds=10,
            num_countries=5,
            scenario_name="Test Scenario",
        )
        dashboard.status.current_round = 3
        dashboard.status.phase = "deliberation"
        dashboard.status.escalation_level = 7

        dashboard._write_status()

        status_file = game_dir / "status.json"
        content = status_file.read_text(encoding="utf-8")
        data = json.loads(content)

        assert data["scenario_name"] == "Test Scenario"
        assert data["total_rounds"] == 10
        assert data["total_countries"] == 5
        assert data["current_round"] == 3
        assert data["phase"] == "deliberation"
        assert data["escalation_level"] == 7

    def test_write_status_atomic_write(self, tmp_path):
        """Test that _write_status uses atomic write (tmp file then replace)."""
        game_dir = tmp_path / "game"
        dashboard = Dashboard(game_dir=game_dir)
        dashboard.status.scenario_name = "Test"

        dashboard._write_status()

        status_file = game_dir / "status.json"
        tmp_file = status_file.with_suffix(".tmp")

        # After write, status.json should exist and .tmp should not
        assert status_file.exists()
        assert not tmp_file.exists()

    def test_write_status_overwrites_existing_file(self, tmp_path):
        """Test that _write_status overwrites existing status.json."""
        game_dir = tmp_path / "game"
        dashboard = Dashboard(game_dir=game_dir)

        # Write first time
        dashboard.status.current_round = 1
        dashboard._write_status()

        # Write second time with updated data
        dashboard.status.current_round = 2
        dashboard._write_status()

        # Read and verify the file has the latest data
        status_file = game_dir / "status.json"
        content = status_file.read_text(encoding="utf-8")
        data = json.loads(content)

        assert data["current_round"] == 2

    def test_write_status_with_none_game_dir(self, tmp_path):
        """Test that _write_status does nothing when game_dir is None."""
        dashboard = Dashboard(game_dir=None)
        dashboard.status.scenario_name = "Test"

        # Should not raise an error
        dashboard._write_status()

        # No file should be created anywhere

    def test_write_status_json_format(self, tmp_path):
        """Test that status.json is properly formatted with indentation."""
        game_dir = tmp_path / "game"
        dashboard = Dashboard(game_dir=game_dir)
        dashboard.status.scenario_name = "Test"

        dashboard._write_status()

        status_file = game_dir / "status.json"
        content = status_file.read_text(encoding="utf-8")

        # Should be indented (contains newlines and spaces)
        assert "\n" in content
        assert "  " in content

    def test_write_status_with_special_characters(self, tmp_path):
        """Test that _write_status handles special characters correctly."""
        game_dir = tmp_path / "game"
        dashboard = Dashboard(game_dir=game_dir)
        dashboard.status.scenario_name = "Test: Scenario with 'quotes' and émojis"
        dashboard.status.last_headlines = [
            "Breaking: NATO responds",
            "Russia claims 'victory'",
            "中国观察",
        ]

        dashboard._write_status()

        status_file = game_dir / "status.json"
        content = status_file.read_text(encoding="utf-8")
        data = json.loads(content)

        assert data["scenario_name"] == "Test: Scenario with 'quotes' and émojis"
        assert "中国观察" in data["last_headlines"]

    def test_write_status_all_fields(self, tmp_path):
        """Test that all GameStatus fields are written to JSON."""
        game_dir = tmp_path / "game"
        dashboard = Dashboard(
            game_dir=game_dir,
            total_rounds=10,
            num_countries=5,
            scenario_name="Full Test",
        )

        # Set all fields
        dashboard.status.current_round = 3
        dashboard.status.phase = "deliberation"
        dashboard.status.current_country = "Russia"
        dashboard.status.current_country_index = 2
        dashboard.status.total_countries = 5
        dashboard.status.faction_index = 1
        dashboard.status.total_factions = 3
        dashboard.status.debate_round = 2
        dashboard.status.escalation_level = 7
        dashboard.status.escalation_label = "SEVERE"
        dashboard.status.last_headlines = ["H1", "H2", "H3"]
        dashboard.status.round_times = [60.0, 75.0, 90.0]
        dashboard.status.eta_seconds = 300.0
        dashboard.status.game_start_time = 1234567890.0
        dashboard.status.elapsed_seconds = 180.0
        dashboard.status.is_running = True
        dashboard.status.error = ""

        dashboard._write_status()

        status_file = game_dir / "status.json"
        content = status_file.read_text(encoding="utf-8")
        data = json.loads(content)

        # Verify all fields
        assert data["scenario_name"] == "Full Test"
        assert data["total_rounds"] == 10
        assert data["current_round"] == 3
        assert data["phase"] == "deliberation"
        assert data["current_country"] == "Russia"
        assert data["current_country_index"] == 2
        assert data["total_countries"] == 5
        assert data["faction_index"] == 1
        assert data["total_factions"] == 3
        assert data["debate_round"] == 2
        assert data["escalation_level"] == 7
        assert data["escalation_label"] == "SEVERE"
        assert data["last_headlines"] == ["H1", "H2", "H3"]
        assert data["round_times"] == [60.0, 75.0, 90.0]
        assert data["eta_seconds"] == 300.0
        assert data["game_start_time"] == 1234567890.0
        assert data["elapsed_seconds"] == 180.0
        assert data["is_running"] is True
        assert data["error"] == ""


class TestDashboardStartStop:
    """Tests for Dashboard.start and stop methods."""

    def test_start_sets_running_state(self, tmp_path):
        """Test that start() sets is_running to True."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.start()

        assert dashboard.status.is_running is True

    def test_start_sets_game_start_time(self, tmp_path):
        """Test that start() sets game_start_time."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        before = time.time()
        dashboard.start()
        after = time.time()

        assert before <= dashboard.status.game_start_time <= after

    @patch("engine.dashboard.Dashboard._write_status")
    def test_start_calls_write_status(self, mock_write, tmp_path):
        """Test that start() calls _write_status."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.start()

        mock_write.assert_called()

    def test_stop_sets_running_state(self, tmp_path):
        """Test that stop() sets is_running to False."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.start()
        dashboard.stop()

        assert dashboard.status.is_running is False

    def test_stop_sets_phase_to_complete(self, tmp_path):
        """Test that stop() sets phase to 'complete'."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.start()
        dashboard.update(phase="deliberation")
        dashboard.stop()

        assert dashboard.status.phase == "complete"

    def test_stop_calculates_elapsed_seconds(self, tmp_path):
        """Test that stop() calculates elapsed_seconds."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.start()

        # Wait a tiny bit
        time.sleep(0.01)

        dashboard.stop()

        assert dashboard.status.elapsed_seconds > 0

    @patch("engine.dashboard.Dashboard._write_status")
    def test_stop_calls_write_status(self, mock_write, tmp_path):
        """Test that stop() calls _write_status."""
        dashboard = Dashboard(game_dir=tmp_path / "game")
        dashboard.start()
        mock_write.reset_mock()  # Reset to ignore start() call

        dashboard.stop()

        mock_write.assert_called()


class TestDashboardIntegration:
    """Integration tests for Dashboard."""

    def test_full_game_lifecycle(self, tmp_path):
        """Test a complete game lifecycle with Dashboard."""
        game_dir = tmp_path / "full_game"
        dashboard = Dashboard(
            game_dir=game_dir,
            total_rounds=3,
            num_countries=2,
            scenario_name="Integration Test",
        )

        # Start game
        dashboard.start()
        assert dashboard.status.is_running is True

        # Round 1
        dashboard.update(phase="briefing", round_num=1)
        dashboard.update(
            phase="deliberation",
            country="Russia",
            country_index=0,
            escalation_level=2,
        )
        dashboard.update(round_time=60.0)

        # Round 2
        dashboard.update(phase="briefing", round_num=2)
        dashboard.update(
            phase="deliberation",
            country="USA",
            country_index=1,
            escalation_level=5,
            headlines=["Tensions rise", "Military buildup"],
        )
        dashboard.update(round_time=75.0)

        # Round 3
        dashboard.update(phase="briefing", round_num=3)
        dashboard.update(
            phase="resolution",
            escalation_level=8,
            headlines=["Crisis point", "Diplomatic efforts fail", "Countdown begins"],
        )
        dashboard.update(round_time=90.0)

        # Stop game
        dashboard.stop()
        assert dashboard.status.is_running is False
        assert dashboard.status.phase == "complete"

        # Verify final state
        assert dashboard.status.current_round == 3
        assert dashboard.status.escalation_level == 8
        assert dashboard.status.escalation_label == "CRITICAL"
        assert dashboard.status.last_headlines == [
            "Crisis point",
            "Diplomatic efforts fail",
            "Countdown begins",
        ]  # Last 3 headlines
        assert len(dashboard.status.round_times) == 3
        assert dashboard.status.elapsed_seconds > 0

        # Verify status.json was written
        status_file = game_dir / "status.json"
        assert status_file.exists()
        data = json.loads(status_file.read_text())
        assert data["scenario_name"] == "Integration Test"
        assert data["total_rounds"] == 3
        assert data["current_round"] == 3
        assert data["phase"] == "complete"
        assert data["is_running"] is False

    def test_escalation_progression(self, tmp_path):
        """Test escalation level progression through game."""
        dashboard = Dashboard(game_dir=tmp_path / "escalation_test")
        dashboard.status.game_start_time = time.time()

        # Test escalation levels and labels
        test_cases = [
            (0, "NORMAL"),
            (1, "NORMAL"),
            (2, "ELEVATED"),
            (3, "ELEVATED"),
            (4, "HIGH"),
            (5, "HIGH"),
            (6, "SEVERE"),
            (7, "SEVERE"),
            (8, "CRITICAL"),
            (9, "CRITICAL"),
            (10, "NUCLEAR"),
        ]

        for level, expected_label in test_cases:
            dashboard.update(escalation_level=level)
            assert dashboard.status.escalation_level == level
            assert dashboard.status.escalation_label == expected_label

    def test_headlines_management(self, tmp_path):
        """Test headline truncation and management."""
        dashboard = Dashboard(game_dir=tmp_path / "headlines_test")
        dashboard.status.game_start_time = time.time()

        # Add 1 headline
        dashboard.update(headlines=["H1"])
        assert dashboard.status.last_headlines == ["H1"]

        # Add 2 more (total 3)
        dashboard.update(headlines=["H1", "H2", "H3"])
        assert dashboard.status.last_headlines == ["H1", "H2", "H3"]

        # Add 5 headlines (should keep last 3)
        dashboard.update(headlines=["H1", "H2", "H3", "H4", "H5"])
        assert dashboard.status.last_headlines == ["H3", "H4", "H5"]

        # Add 10 headlines (should keep last 3)
        dashboard.update(headlines=[f"H{i}" for i in range(1, 11)])
        assert dashboard.status.last_headlines == ["H8", "H9", "H10"]
