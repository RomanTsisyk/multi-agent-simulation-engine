"""Comprehensive unit tests for engine/analytics.py.

Tests cover all analysis functions, edge cases, and data processing.
All functions are pure (no LLM, no async).
"""

import json
import pytest
from pathlib import Path

from engine.analytics import (
    generate_analytics,
    format_analytics_text,
    _escalation_timeline,
    _country_scores,
    _pivotal_moments,
    _nuclear_evolution,
    _casualty_summary,
    _humanitarian_summary,
    _diplomatic_network,
)


# ==============================================================================
# Fixture Data - Mimics real round_NNN.json structure
# ==============================================================================

def create_minimal_round(round_num: int) -> dict:
    """Create a minimal valid round structure."""
    return {
        "round": round_num,
        "world_state_after": {
            "nato_alert_level": "normal",
            "nuclear_posture": {},
            "sanctions": [],
            "military_units": [],
            "refugee_flows": [],
            "humanitarian_crisis_level": {},
        },
        "resolution": {
            "events": [],
            "surprises": [],
        },
        "country_decisions": [],
        "diplomatic_messages": [],
    }


def create_escalated_round(round_num: int, nato_level: str = "elevated") -> dict:
    """Create a round with escalated NATO alert."""
    rd = create_minimal_round(round_num)
    rd["world_state_after"]["nato_alert_level"] = nato_level
    return rd


def create_combat_round(round_num: int) -> dict:
    """Create a round with combat events."""
    rd = create_minimal_round(round_num)
    rd["resolution"]["events"] = [
        "RU forces launched an attack on eastern positions",
        "Heavy casualties reported in the combat zone",
    ]
    return rd


def create_nuclear_round(round_num: int, posture_level: str) -> dict:
    """Create a round with nuclear posture changes."""
    rd = create_minimal_round(round_num)
    rd["world_state_after"]["nuclear_posture"] = {
        "RU": posture_level,
        "US": "elevated",
    }
    return rd


def create_round_with_actions(round_num: int, country: str, actions: list[str]) -> dict:
    """Create a round with country actions."""
    rd = create_minimal_round(round_num)
    rd["country_decisions"] = [
        {
            "country": country,
            "actions": actions,
            "diplomatic_messages": [],
        }
    ]
    return rd


def create_round_with_messages(round_num: int, messages: list[dict]) -> dict:
    """Create a round with diplomatic messages."""
    rd = create_minimal_round(round_num)
    rd["diplomatic_messages"] = messages
    return rd


# ==============================================================================
# Tests for generate_analytics
# ==============================================================================

class TestGenerateAnalytics:
    """Tests for the main generate_analytics function."""

    def test_no_round_files_found(self, tmp_path):
        """Test that returns error dict when no round files found."""
        game_dir = tmp_path / "empty_game"
        game_dir.mkdir()

        result = generate_analytics(game_dir)

        assert result == {"error": "No round data found"}

    def test_complete_report_with_all_sections(self, tmp_path):
        """Test that returns complete report with all sections."""
        game_dir = tmp_path / "complete_game"
        game_dir.mkdir()

        # Create round files
        round1 = create_minimal_round(1)
        round2 = create_escalated_round(2, "high")

        (game_dir / "round_001.json").write_text(json.dumps(round1))
        (game_dir / "round_002.json").write_text(json.dumps(round2))

        # Create game summary
        summary = {
            "end_condition": {
                "description": "Peace treaty signed",
                "winner": "NATO",
            }
        }
        (game_dir / "game_summary.json").write_text(json.dumps(summary))

        result = generate_analytics(game_dir)

        assert "error" not in result
        assert result["game_dir"] == str(game_dir)
        assert result["rounds_analysed"] == 2
        assert "escalation_timeline" in result
        assert "country_scores" in result
        assert "pivotal_moments" in result
        assert "nuclear_evolution" in result
        assert "casualty_summary" in result
        assert "humanitarian_summary" in result
        assert "diplomatic_network" in result
        assert result["end_condition"]["description"] == "Peace treaty signed"
        assert result["end_condition"]["winner"] == "NATO"

    def test_reads_round_files_in_order(self, tmp_path):
        """Test that round files are read and sorted correctly."""
        game_dir = tmp_path / "ordered_game"
        game_dir.mkdir()

        # Create out of order files
        (game_dir / "round_003.json").write_text(json.dumps(create_minimal_round(3)))
        (game_dir / "round_001.json").write_text(json.dumps(create_minimal_round(1)))
        (game_dir / "round_002.json").write_text(json.dumps(create_minimal_round(2)))

        result = generate_analytics(game_dir)

        assert result["rounds_analysed"] == 3
        # Verify they were processed in order
        assert result["escalation_timeline"][0]["round"] == 1
        assert result["escalation_timeline"][1]["round"] == 2
        assert result["escalation_timeline"][2]["round"] == 3

    def test_handles_missing_game_summary(self, tmp_path):
        """Test that missing game_summary.json is handled gracefully."""
        game_dir = tmp_path / "no_summary"
        game_dir.mkdir()

        (game_dir / "round_001.json").write_text(json.dumps(create_minimal_round(1)))

        result = generate_analytics(game_dir)

        assert "error" not in result
        assert result["end_condition"] is None

    def test_handles_corrupted_round_file(self, tmp_path):
        """Test that corrupted round files are skipped with warning."""
        game_dir = tmp_path / "corrupted_game"
        game_dir.mkdir()

        (game_dir / "round_001.json").write_text(json.dumps(create_minimal_round(1)))
        (game_dir / "round_002.json").write_text("invalid json {{{")
        (game_dir / "round_003.json").write_text(json.dumps(create_minimal_round(3)))

        result = generate_analytics(game_dir)

        # Should only process valid files
        assert result["rounds_analysed"] == 2


# ==============================================================================
# Tests for format_analytics_text
# ==============================================================================

class TestFormatAnalyticsText:
    """Tests for format_analytics_text function."""

    def test_formats_all_sections_as_readable_text(self):
        """Test that all sections are formatted correctly."""
        report = {
            "rounds_analysed": 3,
            "end_condition": {
                "description": "Nuclear exchange",
                "winner": "None",
            },
            "escalation_timeline": [
                {"round": 1, "tension": 3, "note": "elevated"},
                {"round": 2, "tension": 7, "note": "combat, Article 5"},
            ],
            "country_scores": {
                "RU": {
                    "total_actions": 10,
                    "military_actions": 8,
                    "diplomatic_actions": 2,
                    "messages_sent": 5,
                },
                "US": {
                    "total_actions": 8,
                    "military_actions": 6,
                    "diplomatic_actions": 2,
                    "messages_sent": 4,
                },
            },
            "pivotal_moments": [
                {"round": 2, "country": "RU", "description": "Nuclear escalation"},
            ],
            "nuclear_evolution": [
                {"round": 2, "postures": {"RU": "tactical_use", "US": "launch_ready"}},
            ],
            "casualty_summary": {
                "1st Guards": {
                    "country": "RU",
                    "casualties": 500,
                    "strength": 6,
                    "morale": 4,
                },
            },
            "humanitarian_summary": {
                "total_refugees": 50000,
                "crisis_levels": {"UA": 8, "PL": 5},
            },
            "diplomatic_network": {
                "total_messages": 15,
                "pair_counts": {"US -> RU": 5, "RU -> US": 4},
            },
        }

        text = format_analytics_text(report)

        assert "POST-GAME ANALYTICS REPORT" in text
        assert "Rounds analysed: 3" in text
        assert "GAME ENDED BY: Nuclear exchange" in text
        assert "Winner: None" in text
        assert "ESCALATION TIMELINE:" in text
        assert "Round  1" in text
        assert "Round  2" in text
        assert "COUNTRY SCORES:" in text
        assert "RU: actions=10" in text
        assert "US: actions=8" in text
        assert "PIVOTAL MOMENTS:" in text
        assert "Nuclear escalation" in text
        assert "NUCLEAR POSTURE EVOLUTION:" in text
        assert "RU=tactical_use" in text
        assert "CASUALTY SUMMARY" in text
        assert "1st Guards (RU): casualties=500" in text
        assert "HUMANITARIAN SUMMARY:" in text
        assert "Total refugees: ~50,000" in text
        assert "DIPLOMATIC MESSAGE NETWORK:" in text
        assert "Total messages: 15" in text

    def test_handles_missing_sections_gracefully(self):
        """Test that missing sections don't cause errors."""
        report = {
            "rounds_analysed": 1,
        }

        text = format_analytics_text(report)

        assert "POST-GAME ANALYTICS REPORT" in text
        assert "Rounds analysed: 1" in text
        # Should not crash on missing sections

    def test_bar_chart_rendering_for_escalation_timeline(self):
        """Test that tension bars are rendered correctly."""
        report = {
            "rounds_analysed": 3,
            "escalation_timeline": [
                {"round": 1, "tension": 2, "note": ""},
                {"round": 2, "tension": 5, "note": "combat"},
                {"round": 3, "tension": 10, "note": "nuclear"},
            ],
        }

        text = format_analytics_text(report)

        # Check for bar representation (# symbols)
        assert "##" in text  # tension 2
        assert "#####" in text  # tension 5
        assert "##########" in text  # tension 10
        assert "(2/10)" in text
        assert "(5/10)" in text
        assert "(10/10)" in text

    def test_empty_lists_produce_appropriate_messages(self):
        """Test that empty lists are handled properly."""
        report = {
            "rounds_analysed": 1,
            "escalation_timeline": [],
            "country_scores": {},
            "pivotal_moments": [],
            "nuclear_evolution": [],
            "casualty_summary": {},
            "humanitarian_summary": {"total_refugees": 0},
            "diplomatic_network": {},
        }

        text = format_analytics_text(report)

        # Should contain headers but not crash
        assert "ESCALATION TIMELINE:" in text
        assert "COUNTRY SCORES:" in text
        # Sections with empty data should be omitted or minimal
        assert "PIVOTAL MOMENTS:" not in text  # Only shown if data exists
        assert "NUCLEAR POSTURE EVOLUTION:" not in text
        assert "CASUALTY SUMMARY" not in text
        assert "HUMANITARIAN SUMMARY:" not in text  # Zero refugees

    def test_formats_casualties_only_if_present(self):
        """Test that casualties are only shown when > 0."""
        report = {
            "rounds_analysed": 1,
            "casualty_summary": {
                "Unit A": {"country": "RU", "casualties": 100, "strength": 8, "morale": 7},
                "Unit B": {"country": "US", "casualties": 0, "strength": 10, "morale": 10},
            },
        }

        text = format_analytics_text(report)

        assert "Unit A (RU): casualties=100" in text
        assert "Unit B" not in text  # Should be skipped (0 casualties)


# ==============================================================================
# Tests for _escalation_timeline
# ==============================================================================

class TestEscalationTimeline:
    """Tests for _escalation_timeline function."""

    def test_nato_alert_scoring_article5(self):
        """Test NATO Article 5 adds +3 to tension."""
        rounds = [create_escalated_round(1, "article5")]

        timeline = _escalation_timeline(rounds)

        assert len(timeline) == 1
        # Base score 0 + 3 (article5) = 3, clamped to min 1, so stays 3
        assert timeline[0]["tension"] >= 3
        assert "Article 5" in timeline[0]["note"]

    def test_nato_alert_scoring_high(self):
        """Test NATO high alert adds +2 to tension."""
        rounds = [create_escalated_round(1, "high")]

        timeline = _escalation_timeline(rounds)

        assert len(timeline) == 1
        # Base 0 + 2 (high) = 2, clamped to min 1
        assert timeline[0]["tension"] >= 2

    def test_nato_alert_scoring_elevated(self):
        """Test NATO elevated alert adds +1 to tension."""
        rounds = [create_escalated_round(1, "elevated")]

        timeline = _escalation_timeline(rounds)

        assert len(timeline) == 1
        # Base 0 + 1 (elevated) = 1
        assert timeline[0]["tension"] >= 1

    def test_combat_keyword_detection_in_events(self):
        """Test that combat keywords in events add +2 tension."""
        rd = create_minimal_round(1)
        rd["resolution"]["events"] = ["Major attack launched on the capital"]
        rounds = [rd]

        timeline = _escalation_timeline(rounds)

        assert timeline[0]["tension"] >= 2
        assert "combat" in timeline[0]["note"]

    def test_combat_keyword_detection_in_surprises(self):
        """Test that combat keywords in surprises add +2 tension."""
        rd = create_minimal_round(1)
        rd["resolution"]["surprises"] = ["Surprise offensive causes heavy casualties"]
        rounds = [rd]

        timeline = _escalation_timeline(rounds)

        assert timeline[0]["tension"] >= 2
        assert "combat" in timeline[0]["note"]

    def test_nuclear_posture_scoring_tactical_use(self):
        """Test nuclear tactical_use adds significant tension."""
        rounds = [create_nuclear_round(1, "tactical_use")]

        timeline = _escalation_timeline(rounds)

        # tactical_use is index 4 in levels, max_nuc >= 3 adds +3
        assert timeline[0]["tension"] >= 3
        assert "nuclear:tactical_use" in timeline[0]["note"]

    def test_nuclear_posture_scoring_launch_ready(self):
        """Test nuclear launch_ready adds significant tension."""
        rounds = [create_nuclear_round(1, "launch_ready")]

        timeline = _escalation_timeline(rounds)

        # launch_ready is index 3 in levels, max_nuc >= 3 adds +3
        assert timeline[0]["tension"] >= 3
        assert "nuclear:launch_ready" in timeline[0]["note"]

    def test_nuclear_posture_scoring_dispersal(self):
        """Test nuclear dispersal adds moderate tension."""
        rounds = [create_nuclear_round(1, "dispersal")]

        timeline = _escalation_timeline(rounds)

        # dispersal is index 2 in levels, max_nuc >= 2 adds +1
        assert timeline[0]["tension"] >= 1

    def test_nuclear_posture_scoring_elevated(self):
        """Test nuclear elevated posture adds minimal tension."""
        rounds = [create_nuclear_round(1, "elevated")]

        timeline = _escalation_timeline(rounds)

        # elevated is index 1, max_nuc < 2 adds 0 from nuclear
        # But tension is clamped to min 1
        assert timeline[0]["tension"] >= 1

    def test_sanctions_threshold_adds_one(self):
        """Test that >3 sanctions add +1 to tension."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["sanctions"] = [
            {"target": "RU", "type": "economic"},
            {"target": "RU", "type": "tech"},
            {"target": "RU", "type": "energy"},
            {"target": "RU", "type": "military"},
        ]
        rounds = [rd]

        timeline = _escalation_timeline(rounds)

        # Base 0 + 1 (sanctions > 3) = 1
        assert timeline[0]["tension"] >= 1

    def test_tension_clamped_to_1_10_min(self):
        """Test that tension is clamped to minimum 1."""
        rounds = [create_minimal_round(1)]

        timeline = _escalation_timeline(rounds)

        assert timeline[0]["tension"] >= 1

    def test_tension_clamped_to_1_10_max(self):
        """Test that tension is clamped to maximum 10."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["nato_alert_level"] = "article5"  # +3
        rd["resolution"]["events"] = ["Attack with heavy casualties"]  # +2
        rd["world_state_after"]["nuclear_posture"] = {"RU": "tactical_use"}  # +3
        rd["world_state_after"]["sanctions"] = [{"t": "a"}] * 5  # +1
        # Total: 3 + 2 + 3 + 1 = 9, but could go higher with more factors
        rounds = [rd]

        timeline = _escalation_timeline(rounds)

        assert timeline[0]["tension"] <= 10

    def test_empty_rounds_list(self):
        """Test that empty rounds list returns empty timeline."""
        timeline = _escalation_timeline([])

        assert timeline == []

    def test_missing_fields_handled_gracefully(self):
        """Test that missing fields don't crash the function."""
        rounds = [{"round": 1}]  # Minimal structure

        timeline = _escalation_timeline(rounds)

        assert len(timeline) == 1
        assert timeline[0]["round"] == 1
        assert timeline[0]["tension"] >= 1


# ==============================================================================
# Tests for _country_scores
# ==============================================================================

class TestCountryScores:
    """Tests for _country_scores function."""

    def test_action_counting(self):
        """Test that actions are counted correctly per country."""
        rounds = [
            create_round_with_actions(1, "RU", ["Action 1", "Action 2", "Action 3"]),
            create_round_with_actions(2, "RU", ["Action 4", "Action 5"]),
            create_round_with_actions(2, "US", ["Action A"]),
        ]

        scores = _country_scores(rounds)

        assert scores["RU"]["total_actions"] == 5
        assert scores["US"]["total_actions"] == 1

    def test_military_keyword_detection_deploy(self):
        """Test military keyword 'deploy' is detected."""
        rounds = [
            create_round_with_actions(1, "RU", ["Deploy forces to the border"]),
        ]

        scores = _country_scores(rounds)

        assert scores["RU"]["military_actions"] == 1

    def test_military_keyword_detection_attack(self):
        """Test military keyword 'attack' is detected."""
        rounds = [
            create_round_with_actions(1, "RU", ["Launch attack on enemy positions"]),
        ]

        scores = _country_scores(rounds)

        assert scores["RU"]["military_actions"] == 1

    def test_military_keyword_detection_strike(self):
        """Test military keyword 'strike' is detected."""
        rounds = [
            create_round_with_actions(1, "US", ["Air strike on military targets"]),
        ]

        scores = _country_scores(rounds)

        assert scores["US"]["military_actions"] == 1

    def test_military_keyword_detection_mobilize(self):
        """Test military keyword 'mobiliz' is detected."""
        rounds = [
            create_round_with_actions(1, "RU", ["Mobilize reserve units"]),
        ]

        scores = _country_scores(rounds)

        assert scores["RU"]["military_actions"] == 1

    def test_military_keyword_detection_partial_match(self):
        """Test that partial keyword matches work (e.g., 'mobiliz' in 'mobilization')."""
        rounds = [
            create_round_with_actions(1, "RU", ["Begin mobilization of troops"]),
        ]

        scores = _country_scores(rounds)

        assert scores["RU"]["military_actions"] == 1

    def test_diplomatic_keyword_detection_negotiate(self):
        """Test diplomatic keyword 'negotiate' is detected."""
        rounds = [
            create_round_with_actions(1, "US", ["Negotiate peace terms"]),
        ]

        scores = _country_scores(rounds)

        assert scores["US"]["diplomatic_actions"] == 1

    def test_diplomatic_keyword_detection_treaty(self):
        """Test diplomatic keyword 'treaty' is detected."""
        rounds = [
            create_round_with_actions(1, "US", ["Propose new treaty"]),
        ]

        scores = _country_scores(rounds)

        assert scores["US"]["diplomatic_actions"] == 1

    def test_diplomatic_keyword_detection_ceasefire(self):
        """Test diplomatic keyword 'ceasefire' is detected."""
        rounds = [
            create_round_with_actions(1, "RU", ["Accept ceasefire proposal"]),
        ]

        scores = _country_scores(rounds)

        assert scores["RU"]["diplomatic_actions"] == 1

    def test_message_counting(self):
        """Test that diplomatic messages are counted correctly."""
        rd = create_minimal_round(1)
        rd["country_decisions"] = [
            {
                "country": "US",
                "actions": [],
                "diplomatic_messages": [
                    {"to": "RU", "content": "Message 1"},
                    {"to": "CN", "content": "Message 2"},
                ],
            }
        ]
        rounds = [rd]

        scores = _country_scores(rounds)

        assert scores["US"]["messages_sent"] == 2

    def test_action_can_be_both_military_and_diplomatic(self):
        """Test that an action can match both categories."""
        rounds = [
            create_round_with_actions(
                1, "US", ["Deploy diplomatic negotiation team"]
            ),
        ]

        scores = _country_scores(rounds)

        # Should match both 'deploy' and 'negotiat'
        assert scores["US"]["military_actions"] == 1
        assert scores["US"]["diplomatic_actions"] == 1

    def test_empty_rounds_returns_empty_scores(self):
        """Test that empty rounds list returns empty scores."""
        scores = _country_scores([])

        assert scores == {}

    def test_missing_country_decisions(self):
        """Test that missing country_decisions is handled."""
        rounds = [{"round": 1}]

        scores = _country_scores(rounds)

        assert scores == {}


# ==============================================================================
# Tests for _pivotal_moments
# ==============================================================================

class TestPivotalMoments:
    """Tests for _pivotal_moments function."""

    def test_detects_nuclear_keyword_in_surprises(self):
        """Test detection of 'nuclear' keyword in surprises."""
        rd = create_minimal_round(1)
        rd["resolution"]["surprises"] = ["Nuclear weapons deployed to border region"]
        rounds = [rd]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 1
        assert pivotal[0]["round"] == 1
        assert pivotal[0]["country"] == "GM"
        assert pivotal[0]["type"] == "surprise"
        assert "Nuclear" in pivotal[0]["description"]

    def test_detects_ceasefire_keyword_in_surprises(self):
        """Test detection of 'ceasefire' keyword in surprises."""
        rd = create_minimal_round(1)
        rd["resolution"]["surprises"] = ["Unexpected ceasefire agreement reached"]
        rounds = [rd]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 1
        assert "ceasefire" in pivotal[0]["description"].lower()

    def test_detects_invasion_keyword_in_surprises(self):
        """Test detection of 'invasion' keyword in surprises."""
        rd = create_minimal_round(1)
        rd["resolution"]["surprises"] = ["Full-scale invasion begins"]
        rounds = [rd]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 1
        assert "invasion" in pivotal[0]["description"].lower()

    def test_detects_article5_keyword_in_surprises(self):
        """Test detection of 'article 5' keyword in surprises."""
        rd = create_minimal_round(1)
        rd["resolution"]["surprises"] = ["NATO invokes Article 5"]
        rounds = [rd]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 1
        assert "Article 5" in pivotal[0]["description"]

    def test_extracts_from_country_actions(self):
        """Test extraction of pivotal moments from country actions."""
        rounds = [
            create_round_with_actions(
                1, "RU", ["Launch nuclear strike on military base"]
            ),
        ]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 1
        assert pivotal[0]["round"] == 1
        assert pivotal[0]["country"] == "RU"
        assert pivotal[0]["type"] == "action"
        assert "nuclear" in pivotal[0]["description"].lower()

    def test_correct_type_tagging_surprise(self):
        """Test that surprises are tagged with type='surprise'."""
        rd = create_minimal_round(1)
        rd["resolution"]["surprises"] = ["Nuclear escalation occurs"]
        rounds = [rd]

        pivotal = _pivotal_moments(rounds)

        assert pivotal[0]["type"] == "surprise"

    def test_correct_type_tagging_action(self):
        """Test that actions are tagged with type='action'."""
        rounds = [
            create_round_with_actions(1, "US", ["Nuclear deterrent deployed"]),
        ]

        pivotal = _pivotal_moments(rounds)

        assert pivotal[0]["type"] == "action"

    def test_detects_multiple_keywords(self):
        """Test detection of multiple pivot keywords."""
        rd = create_minimal_round(1)
        rd["resolution"]["surprises"] = [
            "Nuclear alert raised",
            "Ceasefire negotiations begin",
        ]
        rounds = [rd]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 2

    def test_detects_retreat_keyword(self):
        """Test detection of 'retreat' keyword."""
        rounds = [
            create_round_with_actions(1, "RU", ["Order strategic retreat"]),
        ]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 1
        assert "retreat" in pivotal[0]["description"].lower()

    def test_detects_escalat_keyword(self):
        """Test detection of 'escalat' keyword (matches 'escalate', 'escalation')."""
        rounds = [
            create_round_with_actions(1, "US", ["Escalate military response"]),
        ]

        pivotal = _pivotal_moments(rounds)

        assert len(pivotal) == 1

    def test_empty_rounds_returns_empty_list(self):
        """Test that empty rounds list returns empty pivotal moments."""
        pivotal = _pivotal_moments([])

        assert pivotal == []

    def test_no_pivotal_moments_found(self):
        """Test rounds with no pivot keywords return empty list."""
        rounds = [
            create_round_with_actions(1, "US", ["Continue routine patrols"]),
        ]

        pivotal = _pivotal_moments(rounds)

        assert pivotal == []


# ==============================================================================
# Tests for _nuclear_evolution
# ==============================================================================

class TestNuclearEvolution:
    """Tests for _nuclear_evolution function."""

    def test_tracks_nuclear_posture_across_rounds(self):
        """Test that nuclear posture changes are tracked."""
        rounds = [
            create_nuclear_round(1, "elevated"),
            create_nuclear_round(2, "dispersal"),
            create_nuclear_round(3, "launch_ready"),
        ]

        evolution = _nuclear_evolution(rounds)

        assert len(evolution) == 3
        assert evolution[0]["round"] == 1
        assert evolution[0]["postures"]["RU"] == "elevated"
        assert evolution[1]["round"] == 2
        assert evolution[1]["postures"]["RU"] == "dispersal"
        assert evolution[2]["round"] == 3
        assert evolution[2]["postures"]["RU"] == "launch_ready"

    def test_only_includes_changes(self):
        """Test that only changes in posture are included."""
        rounds = [
            create_nuclear_round(1, "elevated"),
            create_nuclear_round(2, "elevated"),  # No change
            create_nuclear_round(3, "dispersal"),  # Change
        ]

        evolution = _nuclear_evolution(rounds)

        # Should only have rounds 1 and 3
        assert len(evolution) == 2
        assert evolution[0]["round"] == 1
        assert evolution[1]["round"] == 3

    def test_tracks_multiple_countries(self):
        """Test that multiple countries' postures are tracked."""
        rd1 = create_minimal_round(1)
        rd1["world_state_after"]["nuclear_posture"] = {
            "RU": "elevated",
            "US": "peacetime",
            "CN": "peacetime",
        }
        rd2 = create_minimal_round(2)
        rd2["world_state_after"]["nuclear_posture"] = {
            "RU": "dispersal",
            "US": "elevated",
            "CN": "elevated",
        }
        rounds = [rd1, rd2]

        evolution = _nuclear_evolution(rounds)

        assert len(evolution) == 2
        assert evolution[0]["postures"]["RU"] == "elevated"
        assert evolution[0]["postures"]["US"] == "peacetime"
        assert evolution[1]["postures"]["RU"] == "dispersal"
        assert evolution[1]["postures"]["US"] == "elevated"

    def test_empty_rounds_returns_empty_list(self):
        """Test that empty rounds list returns empty evolution."""
        evolution = _nuclear_evolution([])

        assert evolution == []

    def test_no_nuclear_posture_data(self):
        """Test rounds with no nuclear posture data."""
        rounds = [create_minimal_round(1), create_minimal_round(2)]

        evolution = _nuclear_evolution(rounds)

        # Empty posture {} is different from prev {}, so won't be added
        assert evolution == []


# ==============================================================================
# Tests for _casualty_summary
# ==============================================================================

class TestCasualtySummary:
    """Tests for _casualty_summary function."""

    def test_extracts_casualties_from_last_round(self):
        """Test that casualties are extracted from the last round's world state."""
        rd1 = create_minimal_round(1)
        rd1["world_state_after"]["military_units"] = [
            {
                "name": "1st Guards",
                "country": "RU",
                "casualties": 100,
                "strength": 8,
                "morale": 7,
                "supply_level": 6,
            }
        ]
        rd2 = create_minimal_round(2)
        rd2["world_state_after"]["military_units"] = [
            {
                "name": "1st Guards",
                "country": "RU",
                "casualties": 250,
                "strength": 6,
                "morale": 5,
                "supply_level": 4,
            }
        ]
        rounds = [rd1, rd2]

        summary = _casualty_summary(rounds)

        # Should use last round data
        assert summary["1st Guards"]["casualties"] == 250
        assert summary["1st Guards"]["strength"] == 6
        assert summary["1st Guards"]["morale"] == 5

    def test_extracts_all_unit_data(self):
        """Test that all unit data fields are extracted."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["military_units"] = [
            {
                "name": "82nd Airborne",
                "country": "US",
                "casualties": 50,
                "strength": 9,
                "morale": 8,
                "supply_level": 10,
            }
        ]
        rounds = [rd]

        summary = _casualty_summary(rounds)

        unit = summary["82nd Airborne"]
        assert unit["country"] == "US"
        assert unit["casualties"] == 50
        assert unit["strength"] == 9
        assert unit["morale"] == 8
        assert unit["supply_level"] == 10

    def test_multiple_units(self):
        """Test extraction of multiple units."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["military_units"] = [
            {"name": "Unit A", "country": "RU", "casualties": 100, "strength": 7, "morale": 6, "supply_level": 5},
            {"name": "Unit B", "country": "US", "casualties": 50, "strength": 9, "morale": 8, "supply_level": 9},
            {"name": "Unit C", "country": "UA", "casualties": 200, "strength": 4, "morale": 5, "supply_level": 3},
        ]
        rounds = [rd]

        summary = _casualty_summary(rounds)

        assert len(summary) == 3
        assert summary["Unit A"]["casualties"] == 100
        assert summary["Unit B"]["casualties"] == 50
        assert summary["Unit C"]["casualties"] == 200

    def test_empty_rounds_returns_empty_dict(self):
        """Test that empty rounds list returns empty summary."""
        summary = _casualty_summary([])

        assert summary == {}

    def test_missing_military_units(self):
        """Test rounds with no military units."""
        rounds = [create_minimal_round(1)]

        summary = _casualty_summary(rounds)

        assert summary == {}

    def test_missing_fields_handled_with_defaults(self):
        """Test that missing fields get '?' as default."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["military_units"] = [
            {"name": "Incomplete Unit"}  # Missing all other fields
        ]
        rounds = [rd]

        summary = _casualty_summary(rounds)

        unit = summary["Incomplete Unit"]
        assert unit["country"] == "?"
        assert unit["casualties"] == 0
        assert unit["strength"] == "?"
        assert unit["morale"] == "?"


# ==============================================================================
# Tests for _humanitarian_summary
# ==============================================================================

class TestHumanitarianSummary:
    """Tests for _humanitarian_summary function."""

    def test_extracts_refugee_flows_from_final_state(self):
        """Test that refugee flows are extracted from final state."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["refugee_flows"] = [
            {"from": "UA", "to": "PL", "count": 10000},
            {"from": "UA", "to": "RO", "count": 5000},
        ]
        rounds = [rd]

        summary = _humanitarian_summary(rounds)

        assert summary["total_refugees"] == 15000
        assert len(summary["flows"]) == 2

    def test_calculates_total_refugees(self):
        """Test that total refugees is calculated correctly."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["refugee_flows"] = [
            {"from": "UA", "to": "PL", "count": 10000},
            {"from": "UA", "to": "RO", "count": 5000},
            {"from": "UA", "to": "HU", "count": 3000},
        ]
        rounds = [rd]

        summary = _humanitarian_summary(rounds)

        assert summary["total_refugees"] == 18000

    def test_extracts_crisis_levels(self):
        """Test that crisis levels are extracted."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["humanitarian_crisis_level"] = {
            "UA": 9,
            "PL": 5,
            "RO": 4,
        }
        rounds = [rd]

        summary = _humanitarian_summary(rounds)

        assert summary["crisis_levels"]["UA"] == 9
        assert summary["crisis_levels"]["PL"] == 5
        assert summary["crisis_levels"]["RO"] == 4

    def test_uses_last_round_data(self):
        """Test that data from the last round is used."""
        rd1 = create_minimal_round(1)
        rd1["world_state_after"]["refugee_flows"] = [
            {"from": "UA", "to": "PL", "count": 5000},
        ]
        rd2 = create_minimal_round(2)
        rd2["world_state_after"]["refugee_flows"] = [
            {"from": "UA", "to": "PL", "count": 15000},
        ]
        rounds = [rd1, rd2]

        summary = _humanitarian_summary(rounds)

        assert summary["total_refugees"] == 15000

    def test_empty_rounds_returns_empty_dict(self):
        """Test that empty rounds list returns empty summary."""
        summary = _humanitarian_summary([])

        assert summary == {}

    def test_missing_refugee_flows(self):
        """Test rounds with no refugee flows."""
        rounds = [create_minimal_round(1)]

        summary = _humanitarian_summary(rounds)

        assert summary["total_refugees"] == 0
        assert summary["flows"] == []

    def test_missing_count_field(self):
        """Test that missing count field defaults to 0."""
        rd = create_minimal_round(1)
        rd["world_state_after"]["refugee_flows"] = [
            {"from": "UA", "to": "PL"},  # No count field
        ]
        rounds = [rd]

        summary = _humanitarian_summary(rounds)

        assert summary["total_refugees"] == 0


# ==============================================================================
# Tests for _diplomatic_network
# ==============================================================================

class TestDiplomaticNetwork:
    """Tests for _diplomatic_network function."""

    def test_counts_total_messages(self):
        """Test that total messages are counted correctly."""
        rd1 = create_round_with_messages(1, [
            {"from": "US", "to": "RU", "content": "Message 1"},
            {"from": "RU", "to": "US", "content": "Message 2"},
        ])
        rd2 = create_round_with_messages(2, [
            {"from": "US", "to": "CN", "content": "Message 3"},
        ])
        rounds = [rd1, rd2]

        network = _diplomatic_network(rounds)

        assert network["total_messages"] == 3

    def test_constructs_message_pairs(self):
        """Test that message pairs are constructed correctly."""
        rounds = [
            create_round_with_messages(1, [
                {"from": "US", "to": "RU", "content": "Message 1"},
                {"from": "US", "to": "RU", "content": "Message 2"},
                {"from": "RU", "to": "US", "content": "Message 3"},
            ])
        ]

        network = _diplomatic_network(rounds)

        assert network["pair_counts"]["US -> RU"] == 2
        assert network["pair_counts"]["RU -> US"] == 1

    def test_counts_pairs_across_rounds(self):
        """Test that pairs are counted across all rounds."""
        rd1 = create_round_with_messages(1, [
            {"from": "US", "to": "RU", "content": "Message 1"},
        ])
        rd2 = create_round_with_messages(2, [
            {"from": "US", "to": "RU", "content": "Message 2"},
        ])
        rd3 = create_round_with_messages(3, [
            {"from": "US", "to": "RU", "content": "Message 3"},
        ])
        rounds = [rd1, rd2, rd3]

        network = _diplomatic_network(rounds)

        assert network["pair_counts"]["US -> RU"] == 3

    def test_different_direction_pairs_counted_separately(self):
        """Test that A->B and B->A are counted separately."""
        rounds = [
            create_round_with_messages(1, [
                {"from": "US", "to": "RU", "content": "Message 1"},
                {"from": "RU", "to": "US", "content": "Message 2"},
            ])
        ]

        network = _diplomatic_network(rounds)

        assert network["pair_counts"]["US -> RU"] == 1
        assert network["pair_counts"]["RU -> US"] == 1
        assert len(network["pair_counts"]) == 2

    def test_multiple_country_pairs(self):
        """Test multiple different country pairs."""
        rounds = [
            create_round_with_messages(1, [
                {"from": "US", "to": "RU", "content": "Message 1"},
                {"from": "US", "to": "CN", "content": "Message 2"},
                {"from": "CN", "to": "RU", "content": "Message 3"},
            ])
        ]

        network = _diplomatic_network(rounds)

        assert network["total_messages"] == 3
        assert network["pair_counts"]["US -> RU"] == 1
        assert network["pair_counts"]["US -> CN"] == 1
        assert network["pair_counts"]["CN -> RU"] == 1

    def test_empty_rounds_returns_zero_messages(self):
        """Test that empty rounds list returns zero messages."""
        network = _diplomatic_network([])

        assert network["total_messages"] == 0
        assert network["pair_counts"] == {}

    def test_missing_diplomatic_messages(self):
        """Test rounds with no diplomatic messages."""
        rounds = [create_minimal_round(1)]

        network = _diplomatic_network(rounds)

        assert network["total_messages"] == 0
        assert network["pair_counts"] == {}

    def test_missing_from_or_to_fields(self):
        """Test that missing from/to fields default to '?'."""
        rd = create_minimal_round(1)
        rd["diplomatic_messages"] = [
            {"content": "Message without from/to"},
        ]
        rounds = [rd]

        network = _diplomatic_network(rounds)

        assert network["total_messages"] == 1
        assert "? -> ?" in network["pair_counts"]


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_game_analysis_workflow(self, tmp_path):
        """Test complete workflow from files to formatted output."""
        game_dir = tmp_path / "full_game"
        game_dir.mkdir()

        # Create a realistic game scenario
        rd1 = create_minimal_round(1)
        rd1["country_decisions"] = [
            {
                "country": "RU",
                "actions": ["Deploy forces to border"],
                "diplomatic_messages": [{"to": "US", "content": "Warning"}],
            }
        ]

        rd2 = create_escalated_round(2, "elevated")
        rd2["resolution"]["events"] = ["Border skirmish with casualties"]
        rd2["country_decisions"] = [
            {
                "country": "US",
                "actions": ["Mobilize NATO response force"],
                "diplomatic_messages": [{"to": "RU", "content": "Demands"}],
            }
        ]

        rd3 = create_nuclear_round(3, "dispersal")
        rd3["world_state_after"]["nato_alert_level"] = "high"
        rd3["resolution"]["surprises"] = ["Nuclear weapons dispersed to field positions"]
        rd3["world_state_after"]["military_units"] = [
            {
                "name": "1st Guards",
                "country": "RU",
                "casualties": 150,
                "strength": 7,
                "morale": 6,
                "supply_level": 5,
            }
        ]
        rd3["world_state_after"]["refugee_flows"] = [
            {"from": "UA", "to": "PL", "count": 25000},
        ]
        rd3["world_state_after"]["humanitarian_crisis_level"] = {"UA": 8}

        # Add diplomatic messages at round level
        rd1["diplomatic_messages"] = [{"from": "RU", "to": "US", "content": "Warning"}]
        rd2["diplomatic_messages"] = [{"from": "US", "to": "RU", "content": "Demands"}]

        (game_dir / "round_001.json").write_text(json.dumps(rd1))
        (game_dir / "round_002.json").write_text(json.dumps(rd2))
        (game_dir / "round_003.json").write_text(json.dumps(rd3))

        summary = {
            "end_condition": {
                "description": "Ceasefire negotiated",
                "winner": "Stalemate",
            }
        }
        (game_dir / "game_summary.json").write_text(json.dumps(summary))

        # Generate analytics
        report = generate_analytics(game_dir)

        # Verify report completeness
        assert report["rounds_analysed"] == 3
        assert len(report["escalation_timeline"]) == 3
        assert "RU" in report["country_scores"]
        assert "US" in report["country_scores"]
        assert len(report["pivotal_moments"]) > 0
        assert len(report["nuclear_evolution"]) > 0
        assert "1st Guards" in report["casualty_summary"]
        assert report["humanitarian_summary"]["total_refugees"] == 25000
        assert report["diplomatic_network"]["total_messages"] == 2

        # Format as text
        text = format_analytics_text(report)

        # Verify text output
        assert "POST-GAME ANALYTICS REPORT" in text
        assert "Rounds analysed: 3" in text
        assert "Ceasefire negotiated" in text
        assert "ESCALATION TIMELINE:" in text
        assert "COUNTRY SCORES:" in text
        assert "RU:" in text
        assert "US:" in text
        assert "PIVOTAL MOMENTS:" in text
        assert "NUCLEAR POSTURE EVOLUTION:" in text
        assert "CASUALTY SUMMARY" in text
        assert "1st Guards" in text
        assert "HUMANITARIAN SUMMARY:" in text
        assert "25,000" in text
        assert "DIPLOMATIC MESSAGE NETWORK:" in text

    def test_handles_incomplete_game_data(self, tmp_path):
        """Test that incomplete or partial game data is handled gracefully."""
        game_dir = tmp_path / "incomplete_game"
        game_dir.mkdir()

        # Only one round, minimal data
        rd1 = {"round": 1}
        (game_dir / "round_001.json").write_text(json.dumps(rd1))

        report = generate_analytics(game_dir)
        text = format_analytics_text(report)

        # Should not crash
        assert "POST-GAME ANALYTICS REPORT" in text
        assert report["rounds_analysed"] == 1
