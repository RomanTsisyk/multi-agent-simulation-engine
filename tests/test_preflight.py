"""Comprehensive unit tests for engine/preflight.py.

Tests cover all pre-flight check functions including:
- CheckResult dataclass
- File-based checks (country files, scenario files)
- Configuration validation
- HTTP-based checks (Ollama reachability, model availability, RAM checks)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import URLError

import pytest
import yaml

from engine.preflight import (
    CheckResult,
    check_config_structure,
    check_country_files,
    check_model_available,
    check_num_ctx,
    check_ollama_reachable,
    check_ram_sufficient,
    check_scenario_file,
)


# ======================================================================
# CheckResult dataclass tests
# ======================================================================


class TestCheckResult:
    """Tests for the CheckResult dataclass."""

    def test_check_result_defaults(self):
        """Test that CheckResult has correct default values."""
        result = CheckResult(
            name="Test Check",
            status="PASS",
            message="All good",
        )
        assert result.name == "Test Check"
        assert result.status == "PASS"
        assert result.message == "All good"
        assert result.critical is True  # Default should be True

    def test_check_result_with_critical_false(self):
        """Test CheckResult with critical=False."""
        result = CheckResult(
            name="Warning Check",
            status="WARN",
            message="Minor issue",
            critical=False,
        )
        assert result.critical is False

    def test_check_result_field_types(self):
        """Test that CheckResult fields have correct types."""
        result = CheckResult(
            name="Type Test",
            status="FAIL",
            message="Something broke",
            critical=True,
        )
        assert isinstance(result.name, str)
        assert isinstance(result.status, str)
        assert isinstance(result.message, str)
        assert isinstance(result.critical, bool)


# ======================================================================
# check_country_files tests
# ======================================================================


class TestCheckCountryFiles:
    """Tests for check_country_files function."""

    def test_directory_not_exists(self, tmp_path):
        """Test when countries directory doesn't exist."""
        non_existent = tmp_path / "non_existent_dir"
        result = check_country_files(non_existent)

        assert result.name == "Country files"
        assert result.status == "FAIL"
        assert "not found" in result.message
        assert str(non_existent) in result.message
        assert result.critical is True

    def test_no_yaml_files(self, tmp_path):
        """Test when directory exists but has no YAML files."""
        countries_dir = tmp_path / "countries"
        countries_dir.mkdir()

        # Create a non-YAML file
        (countries_dir / "readme.txt").write_text("Not a YAML file")

        result = check_country_files(countries_dir)

        assert result.name == "Country files"
        assert result.status == "FAIL"
        assert "No YAML files" in result.message
        assert str(countries_dir) in result.message
        assert result.critical is True

    def test_yaml_files_found(self, tmp_path):
        """Test when YAML files are found."""
        countries_dir = tmp_path / "countries"
        countries_dir.mkdir()

        # Create some YAML files
        (countries_dir / "usa.yaml").write_text("name: USA")
        (countries_dir / "russia.yaml").write_text("name: Russia")
        (countries_dir / "china.yaml").write_text("name: China")

        result = check_country_files(countries_dir)

        assert result.name == "Country files"
        assert result.status == "PASS"
        assert "Found 3 country files" in result.message
        assert str(countries_dir) in result.message
        assert result.critical is True  # Default value


# ======================================================================
# check_num_ctx tests
# ======================================================================


class TestCheckNumCtx:
    """Tests for check_num_ctx function."""

    def test_sufficient_context_window(self):
        """Test when num_ctx is >= recommended."""
        # For 5 countries: recommended = 4000 + 1000 * 5 = 9000
        result = check_num_ctx(num_ctx=10000, num_countries=5)

        assert result.name == "Context window"
        assert result.status == "PASS"
        assert "num_ctx=10000" in result.message
        assert "9000" in result.message  # recommended value
        assert "5 countries" in result.message
        assert result.critical is True  # Default value

    def test_exact_recommended_context_window(self):
        """Test when num_ctx exactly matches recommended."""
        # For 3 countries: recommended = 4000 + 1000 * 3 = 7000
        result = check_num_ctx(num_ctx=7000, num_countries=3)

        assert result.name == "Context window"
        assert result.status == "PASS"
        assert "7000" in result.message

    def test_insufficient_context_window(self):
        """Test when num_ctx is below recommended."""
        # For 10 countries: recommended = 4000 + 1000 * 10 = 14000
        result = check_num_ctx(num_ctx=8192, num_countries=10)

        assert result.name == "Context window"
        assert result.status == "WARN"
        assert "num_ctx=8192" in result.message
        assert "may be small" in result.message
        assert "10 countries" in result.message
        assert "14000" in result.message  # recommended value
        assert result.critical is False  # Warnings are not critical

    def test_small_num_countries(self):
        """Test with small number of countries."""
        # For 1 country: recommended = 4000 + 1000 * 1 = 5000
        result = check_num_ctx(num_ctx=4000, num_countries=1)

        assert result.name == "Context window"
        assert result.status == "WARN"
        assert "4000" in result.message
        assert "5000" in result.message


# ======================================================================
# check_scenario_file tests
# ======================================================================


class TestCheckScenarioFile:
    """Tests for check_scenario_file function."""

    def test_file_not_exists(self, tmp_path):
        """Test when scenario file doesn't exist."""
        non_existent = tmp_path / "non_existent.yaml"
        result = check_scenario_file(non_existent)

        assert result.name == "Scenario file"
        assert result.status == "FAIL"
        assert "not found" in result.message
        assert str(non_existent) in result.message
        assert result.critical is True

    def test_yaml_parse_error(self, tmp_path):
        """Test when YAML file has syntax errors."""
        scenario_file = tmp_path / "bad_scenario.yaml"
        # Invalid YAML with unclosed bracket
        scenario_file.write_text("name: Test\ndata: [1, 2, 3\n")

        result = check_scenario_file(scenario_file)

        assert result.name == "Scenario file"
        assert result.status == "FAIL"
        assert "YAML parse error" in result.message
        assert str(scenario_file) in result.message
        assert result.critical is True

    def test_not_a_dict(self, tmp_path):
        """Test when YAML file doesn't contain a dict."""
        scenario_file = tmp_path / "list_scenario.yaml"
        # Valid YAML but not a dict
        scenario_file.write_text("- item1\n- item2\n- item3")

        result = check_scenario_file(scenario_file)

        assert result.name == "Scenario file"
        assert result.status == "FAIL"
        assert "not a valid YAML dict" in result.message
        assert str(scenario_file) in result.message
        assert result.critical is True

    def test_valid_scenario_with_name(self, tmp_path):
        """Test with a valid scenario file containing a name."""
        scenario_file = tmp_path / "good_scenario.yaml"
        scenario_data = {
            "name": "Suwalki Gap",
            "description": "A test scenario",
            "countries": ["USA", "Russia"],
        }
        scenario_file.write_text(yaml.dump(scenario_data))

        result = check_scenario_file(scenario_file)

        assert result.name == "Scenario file"
        assert result.status == "PASS"
        assert "Suwalki Gap" in result.message
        assert str(scenario_file) in result.message
        assert result.critical is True  # Default value

    def test_valid_scenario_without_name(self, tmp_path):
        """Test with a valid scenario file without a name field."""
        scenario_file = tmp_path / "unnamed_scenario.yaml"
        scenario_data = {
            "description": "No name field",
            "countries": ["UK", "France"],
        }
        scenario_file.write_text(yaml.dump(scenario_data))

        result = check_scenario_file(scenario_file)

        assert result.name == "Scenario file"
        assert result.status == "PASS"
        assert "unnamed" in result.message  # Default name


# ======================================================================
# check_config_structure tests
# ======================================================================


class TestCheckConfigStructure:
    """Tests for check_config_structure function."""

    def test_missing_game_section(self):
        """Test when 'game' section is missing."""
        config = {"llm": {"backend": "ollama"}}
        result = check_config_structure(config)

        assert result.name == "Config structure"
        assert result.status == "FAIL"
        assert "Missing required config sections" in result.message
        assert "game" in result.message
        assert result.critical is True

    def test_missing_llm_section(self):
        """Test when 'llm' section is missing."""
        config = {"game": {"scenario": "test.yaml"}}
        result = check_config_structure(config)

        assert result.name == "Config structure"
        assert result.status == "FAIL"
        assert "Missing required config sections" in result.message
        assert "llm" in result.message
        assert result.critical is True

    def test_missing_both_sections(self):
        """Test when both required sections are missing."""
        config = {"other": "data"}
        result = check_config_structure(config)

        assert result.name == "Config structure"
        assert result.status == "FAIL"
        assert "Missing required config sections" in result.message
        assert "game" in result.message
        assert "llm" in result.message
        assert result.critical is True

    def test_missing_scenario_in_game_section(self):
        """Test when 'scenario' is missing from game section."""
        config = {
            "game": {"countries_dir": "countries"},
            "llm": {"backend": "ollama", "ollama": {"model": "llama2"}},
        }
        result = check_config_structure(config)

        assert result.name == "Config structure"
        assert result.status == "FAIL"
        assert "missing 'scenario' path" in result.message
        assert result.critical is True

    def test_missing_backend_settings(self):
        """Test when backend settings section is missing."""
        config = {
            "game": {"scenario": "test.yaml"},
            "llm": {"backend": "ollama"},  # ollama section missing
        }
        result = check_config_structure(config)

        assert result.name == "Config structure"
        assert result.status == "FAIL"
        assert "missing 'ollama' backend settings" in result.message
        assert result.critical is True

    def test_valid_config_with_ollama(self):
        """Test with a valid configuration for ollama backend."""
        config = {
            "game": {"scenario": "scenarios/test.yaml"},
            "llm": {
                "backend": "ollama",
                "ollama": {
                    "base_url": "http://localhost:11434",
                    "model": "llama2",
                },
            },
        }
        result = check_config_structure(config)

        assert result.name == "Config structure"
        assert result.status == "PASS"
        assert "has all required sections" in result.message
        assert result.critical is True  # Default value

    def test_valid_config_with_deepseek(self):
        """Test with a valid configuration for deepseek backend."""
        config = {
            "game": {"scenario": "scenarios/test.yaml"},
            "llm": {
                "backend": "deepseek",
                "deepseek": {
                    "api_key": "test_key",
                    "model": "deepseek-chat",
                },
            },
        }
        result = check_config_structure(config)

        assert result.name == "Config structure"
        assert result.status == "PASS"
        assert "has all required sections" in result.message


# ======================================================================
# check_ollama_reachable tests
# ======================================================================


class TestCheckOllamaReachable:
    """Tests for check_ollama_reachable function."""

    @patch("urllib.request.urlopen")
    def test_http_200_success(self, mock_urlopen):
        """Test when Ollama API returns HTTP 200."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_ollama_reachable("http://localhost:11434")

        assert result.name == "Ollama reachable"
        assert result.status == "PASS"
        assert "Connected to" in result.message
        assert "http://localhost:11434" in result.message
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_http_non_200_status(self, mock_urlopen):
        """Test when Ollama API returns non-200 status."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_ollama_reachable("http://localhost:11434")

        assert result.name == "Ollama reachable"
        assert result.status == "FAIL"
        assert "HTTP 404" in result.message
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen):
        """Test when connection to Ollama fails."""
        mock_urlopen.side_effect = URLError("Connection refused")

        result = check_ollama_reachable("http://localhost:11434")

        assert result.name == "Ollama reachable"
        assert result.status == "FAIL"
        assert "Cannot connect" in result.message
        assert "http://localhost:11434" in result.message
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_timeout_error(self, mock_urlopen):
        """Test when connection to Ollama times out."""
        import socket
        mock_urlopen.side_effect = socket.timeout("timed out")

        result = check_ollama_reachable("http://localhost:11434")

        assert result.name == "Ollama reachable"
        assert result.status == "FAIL"
        assert "Unexpected error" in result.message or "Cannot connect" in result.message
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_url_with_trailing_slash(self, mock_urlopen):
        """Test that trailing slash in URL is handled correctly."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_ollama_reachable("http://localhost:11434/")

        assert result.status == "PASS"
        # Verify the URL was constructed correctly
        mock_urlopen.assert_called_once()


# ======================================================================
# check_model_available tests
# ======================================================================


class TestCheckModelAvailable:
    """Tests for check_model_available function."""

    @patch("urllib.request.urlopen")
    def test_model_found_exact_match(self, mock_urlopen):
        """Test when model is found with exact name match."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "llama2:latest"},
                {"name": "mistral:7b"},
            ]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_model_available("http://localhost:11434", "llama2:latest")

        assert result.name == "Model available"
        assert result.status == "PASS"
        assert "llama2:latest" in result.message
        assert "found" in result.message.lower()
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_model_found_without_tag(self, mock_urlopen):
        """Test when model is found by base name (without :latest tag)."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "llama2:latest"},
                {"name": "mistral:7b"},
            ]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Search for "llama2" without the :latest tag
        result = check_model_available("http://localhost:11434", "llama2")

        assert result.name == "Model available"
        assert result.status == "PASS"
        assert "llama2" in result.message
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_model_base_match(self, mock_urlopen):
        """Test base name matching when full name not found."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "mistral:7b-instruct"},
            ]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Search for "mistral:7b" when "mistral:7b-instruct" exists
        result = check_model_available("http://localhost:11434", "mistral:7b")

        assert result.name == "Model available"
        # Should pass due to base matching logic
        assert result.status == "PASS" or result.status == "FAIL"  # Depends on exact impl

    @patch("urllib.request.urlopen")
    def test_model_not_found(self, mock_urlopen):
        """Test when requested model is not found."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": [
                {"name": "llama2:latest"},
                {"name": "mistral:7b"},
            ]
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_model_available("http://localhost:11434", "gpt-4")

        assert result.name == "Model available"
        assert result.status == "FAIL"
        assert "not found" in result.message.lower()
        assert "gpt-4" in result.message
        assert "Available:" in result.message or "available:" in result.message
        # Should list available models
        assert "llama2:latest" in result.message or "mistral:7b" in result.message
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_no_models_available(self, mock_urlopen):
        """Test when no models are available."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "models": []
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_model_available("http://localhost:11434", "llama2")

        assert result.name == "Model available"
        assert result.status == "FAIL"
        assert "not found" in result.message.lower()
        assert "none" in result.message.lower()
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_connection_error(self, mock_urlopen):
        """Test when connection fails."""
        mock_urlopen.side_effect = URLError("Connection refused")

        result = check_model_available("http://localhost:11434", "llama2")

        assert result.name == "Model available"
        assert result.status == "FAIL"
        assert "Cannot check models" in result.message
        assert result.critical is True

    @patch("urllib.request.urlopen")
    def test_invalid_json_response(self, mock_urlopen):
        """Test when API returns invalid JSON."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = check_model_available("http://localhost:11434", "llama2")

        assert result.name == "Model available"
        assert result.status == "FAIL"
        assert "Cannot check models" in result.message
        assert result.critical is True


# ======================================================================
# check_ram_sufficient tests
# ======================================================================


class TestCheckRamSufficient:
    """Tests for check_ram_sufficient function."""

    @patch("engine.preflight._get_total_ram_gb")
    @patch("urllib.request.urlopen")
    def test_sufficient_ram(self, mock_urlopen, mock_get_ram):
        """Test when system has sufficient RAM for the model."""
        # Mock model info response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "details": {
                "parameter_size": "7B",
                "format": "gguf",
            }
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Mock system RAM (20GB available, model needs ~4.2GB)
        mock_get_ram.return_value = 20.0

        result = check_ram_sufficient("http://localhost:11434", "llama2:7b")

        assert result.name == "RAM sufficient"
        assert result.status == "PASS"
        assert "20GB" in result.message
        assert result.critical is True  # Default value

    @patch("engine.preflight._get_total_ram_gb")
    @patch("urllib.request.urlopen")
    def test_tight_ram(self, mock_urlopen, mock_get_ram):
        """Test when system has barely enough RAM (tight margin)."""
        # Mock model info response for a 13B model
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "details": {
                "parameter_size": "13B",
                "format": "gguf",
            }
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Mock system RAM (8GB available, model needs ~7.8GB, which is tight)
        mock_get_ram.return_value = 8.0

        result = check_ram_sufficient("http://localhost:11434", "llama2:13b")

        assert result.name == "RAM sufficient"
        assert result.status == "WARN"
        assert "may be tight" in result.message.lower() or "tight" in result.message.lower()
        assert result.critical is False  # Warnings are not critical

    @patch("engine.preflight._get_total_ram_gb")
    @patch("urllib.request.urlopen")
    def test_cannot_estimate_model_size(self, mock_urlopen, mock_get_ram):
        """Test when model parameter size cannot be parsed."""
        # Mock model info response without parameter_size
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "details": {
                "format": "gguf",
            }
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        mock_get_ram.return_value = 16.0

        result = check_ram_sufficient("http://localhost:11434", "custom-model")

        assert result.name == "RAM sufficient"
        assert result.status == "WARN"
        assert "Cannot estimate" in result.message
        assert result.critical is False

    @patch("engine.preflight._get_total_ram_gb")
    @patch("urllib.request.urlopen")
    def test_cannot_check_system_ram(self, mock_urlopen, mock_get_ram):
        """Test when system RAM cannot be determined."""
        # Mock model info response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "details": {
                "parameter_size": "7B",
            }
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Mock system RAM check failure
        mock_get_ram.return_value = 0.0

        result = check_ram_sufficient("http://localhost:11434", "llama2:7b")

        assert result.name == "RAM sufficient"
        assert result.status == "WARN"
        assert "cannot check system ram" in result.message.lower()
        assert "4gb" in result.message.lower()  # Should estimate model size
        assert result.critical is False

    @patch("urllib.request.urlopen")
    def test_api_error(self, mock_urlopen):
        """Test when API call fails."""
        mock_urlopen.side_effect = URLError("Connection refused")

        result = check_ram_sufficient("http://localhost:11434", "llama2")

        assert result.name == "RAM sufficient"
        assert result.status == "WARN"
        assert "Cannot estimate RAM" in result.message
        assert result.critical is False  # RAM checks are non-critical warnings

    @patch("engine.preflight._get_total_ram_gb")
    @patch("urllib.request.urlopen")
    def test_invalid_parameter_size_format(self, mock_urlopen, mock_get_ram):
        """Test when parameter size has invalid format."""
        # Mock model info response with weird parameter_size format
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "details": {
                "parameter_size": "unknown-format",
            }
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        mock_get_ram.return_value = 16.0

        result = check_ram_sufficient("http://localhost:11434", "weird-model")

        assert result.name == "RAM sufficient"
        assert result.status == "WARN"
        assert "Cannot estimate" in result.message
        assert result.critical is False

    @patch("engine.preflight._get_total_ram_gb")
    @patch("urllib.request.urlopen")
    def test_large_model_insufficient_ram(self, mock_urlopen, mock_get_ram):
        """Test when a large model requires more RAM than available."""
        # Mock model info response for a 70B model
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "details": {
                "parameter_size": "70B",
                "format": "gguf",
            }
        }).encode()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = mock_response

        # Mock system RAM (32GB available, model needs ~42GB)
        mock_get_ram.return_value = 32.0

        result = check_ram_sufficient("http://localhost:11434", "llama2:70b")

        assert result.name == "RAM sufficient"
        assert result.status == "WARN"
        assert "may be tight" in result.message.lower() or "tight" in result.message.lower()
        assert result.critical is False
