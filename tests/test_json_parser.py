"""Comprehensive unit tests for utils/json_parser.py.

Tests cover all parsing strategies, edge cases, and fallback behavior.
"""

import pytest

from utils.json_parser import (
    parse_json_response,
    _try_loads,
    _extract_outermost_braces,
    _fix_common_issues,
)


class TestParseJsonResponse:
    """Tests for the main parse_json_response function."""

    def test_direct_valid_json(self):
        """Test Strategy 1: Direct json.loads with valid JSON."""
        raw = '{"action": "ATTACK", "target": "enemy_base"}'
        result = parse_json_response(raw)
        assert result == {"action": "ATTACK", "target": "enemy_base"}

    def test_json_with_leading_trailing_whitespace(self):
        """Test that leading/trailing whitespace is handled."""
        raw = '  \n  {"action": "DEFEND"}  \n  '
        result = parse_json_response(raw)
        assert result == {"action": "DEFEND"}

    def test_json_with_think_blocks_deepseek_r1_style(self):
        """Test Strategy 2: Strip <think>reasoning</think> blocks."""
        raw = '<think>Let me analyze the situation...</think>{"action": "SCOUT"}'
        result = parse_json_response(raw)
        assert result == {"action": "SCOUT"}

    def test_json_with_think_blocks_multiline(self):
        """Test <think> blocks with multiple lines."""
        raw = """<think>
        This is a complex decision.
        Need to consider multiple factors.
        </think>
        {"action": "RETREAT", "reason": "low_health"}"""
        result = parse_json_response(raw)
        assert result == {"action": "RETREAT", "reason": "low_health"}

    def test_json_wrapped_in_markdown_fence_with_json_tag(self):
        """Test Strategy 3: JSON wrapped in ```json ... ```."""
        raw = """```json
        {
            "action": "BUILD",
            "structure": "barracks"
        }
        ```"""
        result = parse_json_response(raw)
        assert result == {"action": "BUILD", "structure": "barracks"}

    def test_json_wrapped_in_markdown_fence_without_tag(self):
        """Test Strategy 3: JSON wrapped in ``` ... ``` (no json tag)."""
        raw = """```
        {"action": "GATHER", "resource": "gold"}
        ```"""
        result = parse_json_response(raw)
        assert result == {"action": "GATHER", "resource": "gold"}

    def test_json_with_preamble_text_before_braces(self):
        """Test Strategy 4: JSON with preamble text before { }."""
        raw = 'Here is my decision in JSON format: {"action": "ATTACK"}'
        result = parse_json_response(raw)
        assert result == {"action": "ATTACK"}

    def test_json_with_trailing_text_after_braces(self):
        """Test Strategy 4: JSON with trailing text after { }."""
        raw = '{"action": "DEFEND"} This is my final decision.'
        result = parse_json_response(raw)
        assert result == {"action": "DEFEND"}

    def test_json_with_both_preamble_and_trailing_text(self):
        """Test JSON with text on both sides."""
        raw = 'The answer is: {"action": "SCOUT", "area": "north"} - done!'
        result = parse_json_response(raw)
        assert result == {"action": "SCOUT", "area": "north"}

    def test_nested_json_objects_brace_matching(self):
        """Test Strategy 4: Nested objects (brace matching must handle depth)."""
        raw = """Some text before
        {
            "action": "TRAIN",
            "units": {
                "type": "knight",
                "count": 5,
                "equipment": {
                    "weapon": "sword",
                    "armor": "plate"
                }
            }
        }
        Some text after"""
        result = parse_json_response(raw)
        assert result == {
            "action": "TRAIN",
            "units": {
                "type": "knight",
                "count": 5,
                "equipment": {"weapon": "sword", "armor": "plate"},
            },
        }

    def test_trailing_comma_before_closing_brace(self):
        """Test Strategy 5: Trailing commas before }."""
        raw = '{"action": "ATTACK", "target": "castle",}'
        result = parse_json_response(raw)
        assert result == {"action": "ATTACK", "target": "castle"}

    def test_trailing_comma_before_closing_bracket(self):
        """Test Strategy 5: Trailing commas before ]."""
        raw = '{"units": ["archer", "knight",]}'
        result = parse_json_response(raw)
        assert result == {"units": ["archer", "knight"]}

    def test_single_quotes_instead_of_double_quotes(self):
        """Test Strategy 5: Single quotes converted to double quotes."""
        raw = "{'action': 'DEFEND', 'position': 'gate'}"
        result = parse_json_response(raw)
        assert result == {"action": "DEFEND", "position": "gate"}

    def test_unescaped_newlines_in_string_values(self):
        """Test Strategy 5: Unescaped newlines in string values."""
        # This is tricky - the function tries to fix literal newlines in values
        raw = """{"message": "Line one
Line two", "action": "REPORT"}"""
        result = parse_json_response(raw)
        # The fix should escape the newline
        assert result["action"] == "REPORT"
        assert "message" in result

    def test_multiple_issues_combined(self):
        """Test multiple issues: preamble, trailing comma, single quotes."""
        raw = "Here's the plan: {'action': 'BUILD', 'type': 'tower',}"
        result = parse_json_response(raw)
        assert result == {"action": "BUILD", "type": "tower"}

    def test_completely_unparseable_text_fallback(self):
        """Test fallback wrapper for completely unparseable text."""
        raw = "This is just plain text with no JSON at all."
        result = parse_json_response(raw)
        assert result == {"_raw": raw.strip()}

    def test_custom_fallback_key(self):
        """Test custom fallback_key parameter."""
        raw = "No JSON here either!"
        result = parse_json_response(raw, fallback_key="error_response")
        assert result == {"error_response": raw.strip()}

    def test_empty_input(self):
        """Test empty string input."""
        raw = ""
        result = parse_json_response(raw)
        assert result == {"_raw": ""}

    def test_whitespace_only_input(self):
        """Test whitespace-only input."""
        raw = "   \n\t   "
        result = parse_json_response(raw)
        assert result == {"_raw": ""}

    def test_json_array_should_fallback(self):
        """Test that JSON arrays fall back since function expects dict."""
        raw = '["item1", "item2", "item3"]'
        result = parse_json_response(raw)
        # Arrays don't match dict type, should fall back
        assert result == {"_raw": raw.strip()}

    def test_strings_containing_braces_inside_json(self):
        """Test that braces inside string values don't confuse the parser."""
        raw = '{"message": "Use {variable} for formatting", "action": "NOTIFY"}'
        result = parse_json_response(raw)
        assert result == {"message": "Use {variable} for formatting", "action": "NOTIFY"}

    def test_escaped_quotes_in_strings(self):
        """Test that escaped quotes in strings are handled correctly."""
        raw = r'{"message": "He said \"hello\"", "action": "GREET"}'
        result = parse_json_response(raw)
        assert result == {"message": 'He said "hello"', "action": "GREET"}

    def test_think_blocks_with_nested_tags(self):
        """Test <think> blocks with content that might look like nested tags."""
        raw = '<think>Consider: <strategy>attack</strategy></think>{"action": "ATTACK"}'
        result = parse_json_response(raw)
        assert result == {"action": "ATTACK"}

    def test_multiple_think_blocks(self):
        """Test multiple <think> blocks in the response."""
        raw = '<think>First thought</think><think>Second thought</think>{"action": "WAIT"}'
        result = parse_json_response(raw)
        assert result == {"action": "WAIT"}

    def test_think_block_after_json(self):
        """Test <think> block appearing after JSON (should still be removed)."""
        raw = '{"action": "MOVE"}<think>This was a good move</think>'
        result = parse_json_response(raw)
        assert result == {"action": "MOVE"}

    def test_markdown_fence_with_extra_whitespace(self):
        """Test markdown fence with various whitespace patterns."""
        raw = """```json

        {"action": "HARVEST"}

        ```"""
        result = parse_json_response(raw)
        assert result == {"action": "HARVEST"}

    def test_complex_nested_structure_with_arrays(self):
        """Test complex nested structure with multiple arrays and objects."""
        raw = """{
            "strategy": {
                "phase": "attack",
                "units": [
                    {"type": "cavalry", "count": 10},
                    {"type": "infantry", "count": 50}
                ],
                "targets": ["tower1", "tower2"]
            }
        }"""
        result = parse_json_response(raw)
        assert result["strategy"]["phase"] == "attack"
        assert len(result["strategy"]["units"]) == 2
        assert result["strategy"]["targets"] == ["tower1", "tower2"]


class TestTryLoads:
    """Tests for the _try_loads helper function."""

    def test_valid_json_dict(self):
        """Test parsing valid JSON dictionary."""
        result = _try_loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_valid_json_array_returns_none(self):
        """Test that valid JSON array returns None (expects dict)."""
        result = _try_loads('["a", "b", "c"]')
        assert result is None

    def test_invalid_json_returns_none(self):
        """Test that invalid JSON returns None."""
        result = _try_loads('{"key": invalid}')
        assert result is None

    def test_empty_string_returns_none(self):
        """Test that empty string returns None."""
        result = _try_loads("")
        assert result is None

    def test_plain_text_returns_none(self):
        """Test that plain text returns None."""
        result = _try_loads("not json at all")
        assert result is None

    def test_number_returns_none(self):
        """Test that a number (valid JSON but not dict) returns None."""
        result = _try_loads("42")
        assert result is None

    def test_boolean_returns_none(self):
        """Test that a boolean (valid JSON but not dict) returns None."""
        result = _try_loads("true")
        assert result is None


class TestExtractOutermostBraces:
    """Tests for the _extract_outermost_braces helper function."""

    def test_simple_json_object(self):
        """Test extracting simple JSON object."""
        text = '{"key": "value"}'
        result = _extract_outermost_braces(text)
        assert result == '{"key": "value"}'

    def test_json_with_preamble(self):
        """Test extracting JSON with preamble text."""
        text = 'Here is the data: {"key": "value"}'
        result = _extract_outermost_braces(text)
        assert result == '{"key": "value"}'

    def test_json_with_trailing_text(self):
        """Test extracting JSON with trailing text."""
        text = '{"key": "value"} and more text here'
        result = _extract_outermost_braces(text)
        assert result == '{"key": "value"}'

    def test_nested_objects(self):
        """Test extracting nested objects."""
        text = '{"outer": {"inner": {"deep": "value"}}}'
        result = _extract_outermost_braces(text)
        assert result == '{"outer": {"inner": {"deep": "value"}}}'

    def test_no_braces_returns_none(self):
        """Test that text with no braces returns None."""
        text = "No braces in this text"
        result = _extract_outermost_braces(text)
        assert result is None

    def test_unmatched_opening_brace_returns_none(self):
        """Test that unmatched opening brace returns None."""
        text = '{"key": "value"'
        result = _extract_outermost_braces(text)
        assert result is None

    def test_only_closing_brace_returns_none(self):
        """Test that only closing brace returns None."""
        text = "} no opening brace"
        result = _extract_outermost_braces(text)
        assert result is None

    def test_braces_inside_strings_ignored(self):
        """Test that braces inside string values are ignored."""
        text = '{"message": "This {has} braces", "key": "value"}'
        result = _extract_outermost_braces(text)
        assert result == '{"message": "This {has} braces", "key": "value"}'

    def test_escaped_quotes_in_strings(self):
        """Test that escaped quotes don't break string detection."""
        text = r'{"message": "She said \"hello {world}\"", "key": "value"}'
        result = _extract_outermost_braces(text)
        assert result == r'{"message": "She said \"hello {world}\"", "key": "value"}'

    def test_multiple_separate_objects_returns_first(self):
        """Test that only the first object is returned."""
        text = '{"first": 1} {"second": 2}'
        result = _extract_outermost_braces(text)
        assert result == '{"first": 1}'

    def test_deeply_nested_structure(self):
        """Test deeply nested structure."""
        text = '{"a": {"b": {"c": {"d": {"e": "deep"}}}}}'
        result = _extract_outermost_braces(text)
        assert result == '{"a": {"b": {"c": {"d": {"e": "deep"}}}}}'

    def test_empty_object(self):
        """Test empty object."""
        text = "{}"
        result = _extract_outermost_braces(text)
        assert result == "{}"

    def test_object_with_array_containing_objects(self):
        """Test object with array containing objects."""
        text = '{"items": [{"id": 1}, {"id": 2}]}'
        result = _extract_outermost_braces(text)
        assert result == '{"items": [{"id": 1}, {"id": 2}]}'


class TestFixCommonIssues:
    """Tests for the _fix_common_issues helper function."""

    def test_remove_trailing_comma_before_brace(self):
        """Test removing trailing comma before }."""
        candidate = '{"key": "value",}'
        result = _fix_common_issues(candidate)
        assert result == '{"key": "value"}'

    def test_remove_trailing_comma_before_bracket(self):
        """Test removing trailing comma before ]."""
        candidate = '{"items": ["a", "b",]}'
        result = _fix_common_issues(candidate)
        assert result == '{"items": ["a", "b"]}'

    def test_remove_multiple_trailing_commas(self):
        """Test removing multiple trailing commas."""
        candidate = '{"a": 1, "b": [1, 2,], "c": 3,}'
        result = _fix_common_issues(candidate)
        assert ',' not in result.split(']')[0].split(',')[-1]
        assert ',' not in result.split('}')[-2].split(',')[-1]

    def test_replace_single_quotes_with_double_quotes(self):
        """Test replacing single quotes with double quotes."""
        candidate = "{'key': 'value'}"
        result = _fix_common_issues(candidate)
        assert result == '{"key": "value"}'

    def test_single_quotes_not_replaced_if_many_double_quotes(self):
        """Test that single quotes aren't blindly replaced if double quotes exist."""
        # The function has a heuristic: only replace if few double quotes
        candidate = '{"key": "val\'ue", "other": "test"}'
        result = _fix_common_issues(candidate)
        # Should not replace single quote since there are 4+ double quotes
        assert "'" in result or result == '{"key": "val"ue", "other": "test"}'

    def test_trailing_comma_with_whitespace(self):
        """Test removing trailing comma with whitespace."""
        candidate = '{"key": "value" , }'
        result = _fix_common_issues(candidate)
        # The regex removes ", " before } leaving single space
        assert result == '{"key": "value" }'

    def test_no_changes_needed(self):
        """Test that valid JSON is not modified."""
        candidate = '{"key": "value", "number": 42}'
        result = _fix_common_issues(candidate)
        assert result == candidate

    def test_combined_fixes(self):
        """Test multiple fixes applied together."""
        candidate = "{'key': 'value', 'items': [1, 2,],}"
        result = _fix_common_issues(candidate)
        # Should fix quotes and trailing commas
        assert '}' in result
        assert ']' in result
        # After fixes, commas before ] and } should be removed
        # Quotes should be converted
        assert '"' in result


class TestEdgeCases:
    """Additional edge case tests."""

    def test_json_null_value(self):
        """Test JSON with null value."""
        raw = '{"key": null}'
        result = parse_json_response(raw)
        assert result == {"key": None}

    def test_json_boolean_values(self):
        """Test JSON with boolean values."""
        raw = '{"active": true, "disabled": false}'
        result = parse_json_response(raw)
        assert result == {"active": True, "disabled": False}

    def test_json_number_values(self):
        """Test JSON with various number formats."""
        raw = '{"int": 42, "float": 3.14, "negative": -10, "exp": 1e5}'
        result = parse_json_response(raw)
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["negative"] == -10
        assert result["exp"] == 1e5

    def test_unicode_characters(self):
        """Test JSON with Unicode characters."""
        raw = '{"message": "Hello 世界 🌍"}'
        result = parse_json_response(raw)
        assert result == {"message": "Hello 世界 🌍"}

    def test_empty_nested_structures(self):
        """Test empty nested structures."""
        raw = '{"obj": {}, "arr": [], "str": ""}'
        result = parse_json_response(raw)
        assert result == {"obj": {}, "arr": [], "str": ""}

    def test_very_long_string_value(self):
        """Test JSON with very long string value."""
        long_text = "A" * 10000
        raw = f'{{"message": "{long_text}"}}'
        result = parse_json_response(raw)
        assert result["message"] == long_text

    def test_special_characters_in_strings(self):
        """Test JSON with special characters in strings."""
        raw = r'{"path": "C:\\Users\\file.txt", "regex": "\\d+", "tab": "a\tb"}'
        result = parse_json_response(raw)
        assert "path" in result
        assert "regex" in result
        assert "tab" in result
