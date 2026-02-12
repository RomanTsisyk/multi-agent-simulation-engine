"""Robust JSON extraction from LLM responses.

Local models frequently return JSON wrapped in markdown fences, preceded
by preamble text, sprinkled with trailing commas, or enclosed in
``<think>`` reasoning blocks.  This module provides a single
:func:`parse_json_response` function used throughout the engine to
extract the first valid JSON object from such responses.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def parse_json_response(raw: str, fallback_key: str = "_raw") -> dict:
    """Best-effort extraction of a JSON object from an LLM response.

    Strategies (tried in order):
    1. Direct ``json.loads``.
    2. Strip ``<think>…</think>`` blocks (DeepSeek R1 reasoning).
    3. Strip markdown code fences.
    4. Find the outermost ``{…}`` block (brace-matching).
    5. Fix common LLM JSON issues (trailing commas, single quotes,
       unescaped newlines in strings).

    Args:
        raw: The raw LLM response text.
        fallback_key: If all parsing fails, return ``{fallback_key: raw}``.

    Returns:
        A parsed dictionary, or a fallback wrapper if parsing fails.
    """
    text = raw.strip()

    # 1. Direct parse
    obj = _try_loads(text)
    if obj is not None:
        return obj

    # 2. Strip <think>...</think> reasoning blocks
    text_no_think = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text_no_think != text:
        obj = _try_loads(text_no_think)
        if obj is not None:
            return obj
        text = text_no_think

    # 3. Strip markdown fences (```json ... ``` or ``` ... ```)
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fenced:
        obj = _try_loads(fenced.group(1).strip())
        if obj is not None:
            return obj

    # 4. Find outermost { ... } block via brace-matching
    candidate = _extract_outermost_braces(text)
    if candidate:
        obj = _try_loads(candidate)
        if obj is not None:
            return obj

        # 5. Fix common LLM JSON issues
        fixed = _fix_common_issues(candidate)
        obj = _try_loads(fixed)
        if obj is not None:
            return obj

    logger.warning("Failed to parse JSON from LLM response. Returning raw text in wrapper.")
    return {fallback_key: text}


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _try_loads(text: str) -> dict | None:
    """Return parsed dict or None on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _extract_outermost_braces(text: str) -> str | None:
    """Find the substring from the first '{' to its matching '}'."""
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape_next:
            escape_next = False
            continue

        if ch == "\\":
            if in_string:
                escape_next = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


def _fix_common_issues(candidate: str) -> str:
    """Attempt to fix common LLM JSON mistakes."""
    fixed = candidate

    # Remove trailing commas before } or ]
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)

    # Replace single quotes with double quotes (only if no double quotes in values)
    if "'" in fixed and fixed.count('"') < 4:
        fixed = fixed.replace("'", '"')

    # Fix unescaped newlines inside string values
    # This is a crude heuristic: replace literal newlines between quotes
    fixed = re.sub(r'(?<=": ")(.*?)(?=")', _escape_newlines_in_match, fixed, flags=re.DOTALL)

    return fixed


def _escape_newlines_in_match(match: re.Match) -> str:
    """Replace literal newlines with \\n inside a JSON string value."""
    return match.group(0).replace("\n", "\\n")
