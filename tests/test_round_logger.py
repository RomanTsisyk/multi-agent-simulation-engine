"""Comprehensive tests for the RoundLogger module.

Tests all functionality including:
- Directory creation
- Timestamped directory generation
- Round logging with zero-padding
- Summary logging
- Event logging with timestamps
- Atomic JSON writing with temp file cleanup
- Handling non-serializable objects
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from engine.round_logger import RoundLogger


class TestRoundLoggerInit:
    """Tests for RoundLogger.__init__ method."""

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Test that __init__ creates the game directory if it doesn't exist."""
        game_dir = tmp_path / "test_game"
        assert not game_dir.exists()

        logger = RoundLogger(str(game_dir))

        assert game_dir.exists()
        assert game_dir.is_dir()
        assert logger.game_dir == game_dir

    def test_accepts_existing_directory(self, tmp_path: Path) -> None:
        """Test that __init__ works with an existing directory."""
        game_dir = tmp_path / "existing_game"
        game_dir.mkdir()
        assert game_dir.exists()

        logger = RoundLogger(str(game_dir))

        assert game_dir.exists()
        assert logger.game_dir == game_dir

    def test_creates_nested_directories(self, tmp_path: Path) -> None:
        """Test that __init__ creates parent directories (parents=True)."""
        nested_dir = tmp_path / "level1" / "level2" / "level3" / "game"
        assert not nested_dir.exists()

        logger = RoundLogger(str(nested_dir))

        assert nested_dir.exists()
        assert nested_dir.is_dir()
        assert logger.game_dir == nested_dir

    def test_game_dir_attribute_is_path(self, tmp_path: Path) -> None:
        """Test that game_dir attribute is a Path object."""
        game_dir = tmp_path / "test_game"
        logger = RoundLogger(str(game_dir))

        assert isinstance(logger.game_dir, Path)


class TestCreateForNewGame:
    """Tests for RoundLogger.create_for_new_game class method."""

    def test_generates_timestamped_directory(self, tmp_path: Path) -> None:
        """Test that create_for_new_game generates a timestamped directory name."""
        base_dir = str(tmp_path)
        before = datetime.now().replace(microsecond=0)

        logger = RoundLogger.create_for_new_game(base_dir)

        after = datetime.now().replace(microsecond=0)

        # Check directory was created
        assert logger.game_dir.exists()
        assert logger.game_dir.is_dir()

        # Check directory name format
        dir_name = logger.game_dir.name
        assert dir_name.startswith("game_")

        # Extract timestamp and verify format
        timestamp_str = dir_name.replace("game_", "")
        # Should be YYYYMMDD_HHMMSS format
        assert len(timestamp_str) == 15  # YYYYMMDD_HHMMSS
        assert timestamp_str[8] == "_"

        # Parse timestamp and verify it's between before and after
        parsed_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        # Allow 1 second tolerance since timestamp format doesn't include microseconds
        assert before <= parsed_time <= after or (parsed_time - before).total_seconds() <= 1

    def test_default_base_dir_is_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default base_dir is 'logs'."""
        # We can't easily test default without creating files in current dir,
        # but we can test that passing "logs" explicitly works
        with monkeypatch.context() as m:
            # Create a temporary directory to use as the working directory
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                m.chdir(tmpdir)
                logger = RoundLogger.create_for_new_game()

                # Should create logs/game_timestamp directory
                assert logger.game_dir.exists()
                assert "logs" in str(logger.game_dir)
                assert logger.game_dir.name.startswith("game_")

    def test_creates_unique_directories(self, tmp_path: Path) -> None:
        """Test that multiple calls create unique directories."""
        base_dir = str(tmp_path)

        logger1 = RoundLogger.create_for_new_game(base_dir)
        # Small sleep to ensure different timestamp
        time.sleep(1.1)
        logger2 = RoundLogger.create_for_new_game(base_dir)

        assert logger1.game_dir != logger2.game_dir
        assert logger1.game_dir.exists()
        assert logger2.game_dir.exists()

    def test_custom_base_dir(self, tmp_path: Path) -> None:
        """Test that custom base_dir is used."""
        custom_base = tmp_path / "custom_logs"
        logger = RoundLogger.create_for_new_game(str(custom_base))

        assert logger.game_dir.parent == custom_base
        assert custom_base.exists()


class TestLogRound:
    """Tests for RoundLogger.log_round method."""

    def test_creates_round_file_with_zero_padding(self, tmp_path: Path) -> None:
        """Test that log_round creates round_NNN.json with zero-padding."""
        logger = RoundLogger(str(tmp_path))
        data = {"test": "data", "round_info": "some info"}

        filepath = logger.log_round(1, data)

        assert filepath.name == "round_001.json"
        assert filepath.exists()

    def test_zero_padding_for_different_numbers(self, tmp_path: Path) -> None:
        """Test zero-padding works correctly for various round numbers."""
        logger = RoundLogger(str(tmp_path))

        test_cases = [
            (1, "round_001.json"),
            (9, "round_009.json"),
            (10, "round_010.json"),
            (99, "round_099.json"),
            (100, "round_100.json"),
            (999, "round_999.json"),
        ]

        for round_num, expected_name in test_cases:
            filepath = logger.log_round(round_num, {"round": round_num})
            assert filepath.name == expected_name
            assert filepath.exists()

    def test_writes_correct_json_content(self, tmp_path: Path) -> None:
        """Test that log_round writes the correct JSON content."""
        logger = RoundLogger(str(tmp_path))
        data = {
            "round": 1,
            "player_action": "attack",
            "result": "success",
            "nested": {"key": "value"},
        }

        filepath = logger.log_round(1, data)

        # Read and verify content
        with open(filepath, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        assert loaded_data == data

    def test_returns_path_object(self, tmp_path: Path) -> None:
        """Test that log_round returns a Path object."""
        logger = RoundLogger(str(tmp_path))
        filepath = logger.log_round(1, {"test": "data"})

        assert isinstance(filepath, Path)

    def test_overwrites_existing_round_file(self, tmp_path: Path) -> None:
        """Test that log_round overwrites if file already exists."""
        logger = RoundLogger(str(tmp_path))

        # Write first version
        logger.log_round(1, {"version": 1})

        # Overwrite with second version
        filepath = logger.log_round(1, {"version": 2})

        # Verify content is from second write
        with open(filepath, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        assert loaded_data == {"version": 2}


class TestLogSummary:
    """Tests for RoundLogger.log_summary method."""

    def test_creates_game_summary_file(self, tmp_path: Path) -> None:
        """Test that log_summary creates game_summary.json."""
        logger = RoundLogger(str(tmp_path))
        summary = {"total_rounds": 10, "winner": "Player A"}

        filepath = logger.log_summary(summary)

        assert filepath.name == "game_summary.json"
        assert filepath.exists()

    def test_writes_correct_summary_content(self, tmp_path: Path) -> None:
        """Test that log_summary writes the correct JSON content."""
        logger = RoundLogger(str(tmp_path))
        summary = {
            "total_rounds": 10,
            "winner": "Player A",
            "statistics": {"attacks": 5, "defenses": 3},
            "narrative": "A great game!",
        }

        filepath = logger.log_summary(summary)

        # Read and verify content
        with open(filepath, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        assert loaded_data == summary

    def test_returns_path_object(self, tmp_path: Path) -> None:
        """Test that log_summary returns a Path object."""
        logger = RoundLogger(str(tmp_path))
        filepath = logger.log_summary({"test": "data"})

        assert isinstance(filepath, Path)

    def test_overwrites_existing_summary(self, tmp_path: Path) -> None:
        """Test that log_summary overwrites if file already exists."""
        logger = RoundLogger(str(tmp_path))

        # Write first version
        logger.log_summary({"version": 1})

        # Overwrite with second version
        filepath = logger.log_summary({"version": 2})

        # Verify content is from second write
        with open(filepath, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        assert loaded_data == {"version": 2}


class TestLogEvent:
    """Tests for RoundLogger.log_event method."""

    def test_creates_timestamped_event_file(self, tmp_path: Path) -> None:
        """Test that log_event creates event_HHMMSS_name.json."""
        logger = RoundLogger(str(tmp_path))
        data = {"event": "error", "message": "Something went wrong"}

        filepath = logger.log_event("error_occurred", data)

        # Verify filename format
        assert filepath.name.startswith("event_")
        assert filepath.name.endswith("_error_occurred.json")
        assert filepath.exists()

        # Extract timestamp from filename
        # Format: event_HHMMSS_error_occurred.json
        parts = filepath.name.split("_")
        timestamp_str = parts[1]  # Should be HHMMSS
        assert len(timestamp_str) == 6
        assert timestamp_str.isdigit()

    def test_timestamp_format_is_hhmmss(self, tmp_path: Path) -> None:
        """Test that timestamp in event filename is HHMMSS format."""
        logger = RoundLogger(str(tmp_path))
        before = datetime.now()

        filepath = logger.log_event("test_event", {"data": "test"})

        after = datetime.now()

        # Extract timestamp
        parts = filepath.name.split("_")
        timestamp_str = parts[1]  # HHMMSS

        # Parse and verify
        parsed_time = datetime.strptime(timestamp_str, "%H%M%S").time()
        assert before.time() <= parsed_time or parsed_time <= after.time()

    def test_writes_correct_event_content(self, tmp_path: Path) -> None:
        """Test that log_event writes the correct JSON content."""
        logger = RoundLogger(str(tmp_path))
        data = {
            "event_type": "diplomatic_message",
            "from": "Country A",
            "to": "Country B",
            "message": "Peace proposal",
        }

        filepath = logger.log_event("diplomacy", data)

        # Read and verify content
        with open(filepath, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        assert loaded_data == data

    def test_returns_path_object(self, tmp_path: Path) -> None:
        """Test that log_event returns a Path object."""
        logger = RoundLogger(str(tmp_path))
        filepath = logger.log_event("test", {"data": "test"})

        assert isinstance(filepath, Path)

    def test_multiple_events_get_unique_filenames(self, tmp_path: Path) -> None:
        """Test that multiple events get unique filenames."""
        logger = RoundLogger(str(tmp_path))

        filepath1 = logger.log_event("event1", {"id": 1})
        time.sleep(1.1)  # Ensure different timestamp
        filepath2 = logger.log_event("event2", {"id": 2})

        assert filepath1 != filepath2
        assert filepath1.exists()
        assert filepath2.exists()

    def test_event_name_in_filename(self, tmp_path: Path) -> None:
        """Test that event name appears in filename."""
        logger = RoundLogger(str(tmp_path))

        filepath = logger.log_event("my_custom_event", {"data": "test"})

        assert "my_custom_event" in filepath.name


class TestWriteJson:
    """Tests for RoundLogger._write_json static method."""

    def test_writes_json_with_pretty_print(self, tmp_path: Path) -> None:
        """Test that _write_json creates pretty-printed JSON."""
        filepath = tmp_path / "test.json"
        data = {"key1": "value1", "key2": {"nested": "value"}}

        RoundLogger._write_json(filepath, data)

        # Read the raw text to check formatting
        content = filepath.read_text(encoding="utf-8")

        # Pretty-printed JSON should have newlines and indentation
        assert "\n" in content
        assert "  " in content  # 2-space indent
        assert content.strip().startswith("{")
        assert content.strip().endswith("}")

        # Verify content is correct
        loaded_data = json.loads(content)
        assert loaded_data == data

    def test_uses_utf8_encoding(self, tmp_path: Path) -> None:
        """Test that _write_json uses UTF-8 encoding."""
        filepath = tmp_path / "test.json"
        data = {"unicode": "こんにちは", "emoji": "🎮", "special": "café"}

        RoundLogger._write_json(filepath, data)

        # Read and verify unicode characters are preserved
        with open(filepath, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        assert loaded_data == data

    def test_handles_non_serializable_objects_with_default_str(
        self, tmp_path: Path
    ) -> None:
        """Test that _write_json handles non-serializable objects via default=str."""

        class CustomObject:
            def __str__(self) -> str:
                return "CustomObject instance"

        filepath = tmp_path / "test.json"
        data = {
            "normal": "value",
            "custom": CustomObject(),
            "datetime": datetime(2026, 2, 12, 14, 30, 0),
            "path": Path("/some/path"),
        }

        # Should not raise an exception
        RoundLogger._write_json(filepath, data)

        # Read and verify content
        with open(filepath, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)

        assert loaded_data["normal"] == "value"
        assert loaded_data["custom"] == "CustomObject instance"
        # datetime and Path should be converted to strings
        assert isinstance(loaded_data["datetime"], str)
        assert isinstance(loaded_data["path"], str)

    def test_atomic_write_creates_temp_file(self, tmp_path: Path) -> None:
        """Test that _write_json uses temp file for atomic write."""
        filepath = tmp_path / "test.json"
        data = {"test": "data"}

        # Patch write_text to verify temp file is used
        original_write = Path.write_text
        temp_files_created = []

        def tracking_write(self: Path, *args: Any, **kwargs: Any) -> int:
            temp_files_created.append(str(self))
            return original_write(self, *args, **kwargs)

        Path.write_text = tracking_write  # type: ignore
        try:
            RoundLogger._write_json(filepath, data)
        finally:
            Path.write_text = original_write  # type: ignore

        # Should have written to .tmp file first
        assert any(f.endswith(".tmp") for f in temp_files_created)

    def test_atomic_write_renames_temp_to_final(self, tmp_path: Path) -> None:
        """Test that temp file is renamed to final file."""
        filepath = tmp_path / "test.json"
        tmp_filepath = filepath.with_suffix(".tmp")
        data = {"test": "data"}

        RoundLogger._write_json(filepath, data)

        # Final file should exist
        assert filepath.exists()
        # Temp file should not exist (renamed)
        assert not tmp_filepath.exists()

        # Verify content
        loaded_data = json.loads(filepath.read_text())
        assert loaded_data == data

    def test_cleans_up_temp_file_on_failure(self, tmp_path: Path) -> None:
        """Test that temp file is cleaned up if write fails."""
        filepath = tmp_path / "test.json"
        tmp_filepath = filepath.with_suffix(".tmp")

        # Create data that will cause json.dumps to fail
        # (or we can mock to force failure)
        import unittest.mock as mock

        # Mock json.dumps to raise an exception
        with mock.patch("engine.round_logger.json.dumps") as mock_dumps:
            mock_dumps.side_effect = ValueError("Serialization error")

            with pytest.raises(ValueError, match="Serialization error"):
                RoundLogger._write_json(filepath, {"test": "data"})

        # Temp file should be cleaned up
        assert not tmp_filepath.exists()
        assert not filepath.exists()

    def test_cleans_up_temp_file_on_rename_failure(self, tmp_path: Path) -> None:
        """Test that temp file is cleaned up if rename fails."""
        filepath = tmp_path / "test.json"
        tmp_filepath = filepath.with_suffix(".tmp")

        import unittest.mock as mock

        # Create the temp file first by allowing write_text to succeed
        original_replace = Path.replace

        def failing_replace(self: Path, target: Path) -> None:
            raise OSError("Rename failed")

        with mock.patch.object(Path, "replace", failing_replace):
            with pytest.raises(OSError, match="Rename failed"):
                RoundLogger._write_json(filepath, {"test": "data"})

        # Temp file should be cleaned up
        assert not tmp_filepath.exists()
        assert not filepath.exists()

    def test_preserves_ensure_ascii_false(self, tmp_path: Path) -> None:
        """Test that ensure_ascii=False is used (non-ASCII chars not escaped)."""
        filepath = tmp_path / "test.json"
        data = {"text": "日本語"}

        RoundLogger._write_json(filepath, data)

        # Read raw content
        content = filepath.read_text(encoding="utf-8")

        # Should contain actual unicode characters, not escape sequences
        assert "日本語" in content
        # Should NOT be escaped as \\uXXXX
        assert "\\u" not in content


class TestIntegration:
    """Integration tests for RoundLogger."""

    def test_full_game_session_workflow(self, tmp_path: Path) -> None:
        """Test a complete game session workflow."""
        base_dir = str(tmp_path)

        # Create logger for new game
        logger = RoundLogger.create_for_new_game(base_dir)

        # Log multiple rounds
        logger.log_round(1, {"round": 1, "action": "setup"})
        logger.log_round(2, {"round": 2, "action": "combat"})
        logger.log_round(3, {"round": 3, "action": "resolution"})

        # Log some events
        logger.log_event("error", {"message": "Minor error"})
        logger.log_event("milestone", {"achievement": "First victory"})

        # Log final summary
        logger.log_summary({"total_rounds": 3, "winner": "Player 1"})

        # Verify all files exist
        assert (logger.game_dir / "round_001.json").exists()
        assert (logger.game_dir / "round_002.json").exists()
        assert (logger.game_dir / "round_003.json").exists()
        assert (logger.game_dir / "game_summary.json").exists()

        # Count event files
        event_files = list(logger.game_dir.glob("event_*.json"))
        assert len(event_files) == 2

    def test_multiple_game_sessions_isolated(self, tmp_path: Path) -> None:
        """Test that multiple game sessions are properly isolated."""
        base_dir = str(tmp_path)

        # Create two game sessions
        logger1 = RoundLogger.create_for_new_game(base_dir)
        time.sleep(1.1)  # Ensure different timestamps
        logger2 = RoundLogger.create_for_new_game(base_dir)

        # Log to both
        logger1.log_round(1, {"game": 1})
        logger2.log_round(1, {"game": 2})

        # Verify isolation
        file1 = logger1.game_dir / "round_001.json"
        file2 = logger2.game_dir / "round_001.json"

        assert file1.exists()
        assert file2.exists()
        assert file1 != file2

        data1 = json.loads(file1.read_text())
        data2 = json.loads(file2.read_text())

        assert data1 == {"game": 1}
        assert data2 == {"game": 2}

    def test_handles_complex_nested_data(self, tmp_path: Path) -> None:
        """Test that complex nested data structures are handled correctly."""
        logger = RoundLogger(str(tmp_path))

        complex_data = {
            "round": 1,
            "players": [
                {"name": "Player 1", "score": 100, "items": ["sword", "shield"]},
                {"name": "Player 2", "score": 95, "items": ["bow", "arrow"]},
            ],
            "world_state": {
                "regions": {
                    "north": {"owner": "Player 1", "troops": 50},
                    "south": {"owner": "Player 2", "troops": 45},
                },
                "resources": {"gold": 1000, "food": 500},
            },
            "metadata": {
                "timestamp": datetime(2026, 2, 12, 14, 30, 0),
                "version": "1.0.0",
            },
        }

        filepath = logger.log_round(1, complex_data)

        # Read and verify
        loaded_data = json.loads(filepath.read_text())

        # Most of the structure should match (datetime will be string)
        assert loaded_data["round"] == 1
        assert loaded_data["players"] == complex_data["players"]
        assert loaded_data["world_state"] == complex_data["world_state"]
        assert isinstance(loaded_data["metadata"]["timestamp"], str)
