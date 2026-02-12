"""Base agent primitives for the wargame simulation.

Every agent in the simulation (faction advisors, synthesisers, diplomats)
inherits from :class:`Agent` and uses an :class:`AgentConfig` to define
its personality, priorities, and behavioural constraints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backends.base import LLMBackend


@dataclass
class AgentConfig:
    """Static configuration that fully describes an agent's persona.

    Attributes:
        name: Human-readable identifier (e.g. ``"General Ivanov"``).
        role: Archetype tag such as ``"hawk"``, ``"diplomat"``, or
            ``"military_realist"``.
        personality: Multi-sentence description of how this agent thinks,
            what they value, and how they argue.
        priorities: Ordered list of strategic priorities the agent cares
            about most (e.g. ``["territorial integrity", "deterrence"]``).
        red_lines: Conditions the agent will never accept, even under
            pressure from other factions.
        voice: Short description of speaking style and tone
            (e.g. ``"blunt, uses military jargon"``).
        country_code: ISO-style code linking this agent to a country
            (e.g. ``"US"``, ``"RU"``).
    """

    name: str
    role: str
    personality: str
    priorities: list[str] = field(default_factory=list)
    red_lines: list[str] = field(default_factory=list)
    voice: str = ""
    country_code: str = ""


_DEFAULT_MAX_HISTORY = 20  # keep at most this many messages (10 turns)


class Agent:
    """Thin wrapper around an LLM backend that maintains conversation state.

    An ``Agent`` keeps a rolling message history so that multi-turn
    conversations (e.g. internal faction debates) are coherent.  The
    heavy lifting is delegated to whichever :class:`LLMBackend` is
    injected at construction time.

    A sliding window (``max_history``) prevents the history from growing
    unbounded across rounds, which would cause context-window overflow.

    Args:
        config: The persona and behavioural configuration for this agent.
        backend: An initialised LLM backend instance (Ollama, DeepSeek, etc.).
        temperature: Sampling temperature passed to the backend on every call.
        max_history: Maximum number of messages to retain.  Older messages
            are dropped from the front when the limit is exceeded.
    """

    def __init__(
        self,
        config: AgentConfig,
        backend: LLMBackend,
        temperature: float = 0.7,
        max_history: int = _DEFAULT_MAX_HISTORY,
    ) -> None:
        self.config = config
        self.backend = backend
        self.temperature = temperature
        self.max_history = max_history
        self.message_history: list[dict[str, str]] = []
        self.logger = logging.getLogger(
            f"agent.{config.country_code}.{config.name}"
        )

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def build_system_prompt(self, world_context: str) -> str:
        """Assemble a system prompt from the agent config and live world state.

        Subclasses should override this to add role-specific instructions
        (e.g. debate formatting rules for factions).

        Args:
            world_context: A free-text summary of the current geopolitical
                situation, recent events, and any scenario-specific data.

        Returns:
            A complete system-level prompt string ready to send to the LLM.
        """
        sections: list[str] = []

        sections.append(
            f"You are {self.config.name}, a {self.config.role} advisor."
        )

        if self.config.personality:
            sections.append(f"Personality: {self.config.personality}")

        if self.config.priorities:
            bullet_list = "\n".join(
                f"  - {p}" for p in self.config.priorities
            )
            sections.append(f"Your strategic priorities (in order):\n{bullet_list}")

        if self.config.red_lines:
            bullet_list = "\n".join(
                f"  - {r}" for r in self.config.red_lines
            )
            sections.append(f"Your absolute red lines (never accept):\n{bullet_list}")

        if self.config.voice:
            sections.append(f"Speaking style: {self.config.voice}")

        sections.append(
            "--- CURRENT WORLD SITUATION ---\n" + world_context
        )

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # LLM interaction
    # ------------------------------------------------------------------

    async def respond(self, prompt: str, world_context: str) -> str:
        """Send a user-turn prompt to the LLM and return the response.

        The prompt is appended to the running ``message_history`` so that
        subsequent calls within the same session are contextually aware.

        Args:
            prompt: The user-side message (question, briefing, etc.).
            world_context: Current world state used to build the system prompt.

        Returns:
            The LLM's generated response as a plain string.
        """
        system_prompt = self.build_system_prompt(world_context)

        self.message_history.append({"role": "user", "content": prompt})

        self.logger.debug(
            "Requesting LLM response (history length=%d)",
            len(self.message_history),
        )

        response = await self.backend.generate(
            system_prompt=system_prompt,
            messages=self.message_history,
            temperature=self.temperature,
        )

        self.message_history.append({"role": "assistant", "content": response})

        # Trim history to prevent unbounded context growth
        if len(self.message_history) > self.max_history:
            trimmed = len(self.message_history) - self.max_history
            self.message_history = self.message_history[-self.max_history:]
            self.logger.debug("Trimmed %d old messages from history", trimmed)

        self.logger.info(
            "Response received (%d chars)", len(response)
        )

        return response

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset_history(self) -> None:
        """Clear the conversation history for a fresh session."""
        self.message_history = []
        self.logger.debug("Message history cleared")

    def __repr__(self) -> str:
        return (
            f"Agent(name={self.config.name!r}, "
            f"role={self.config.role!r}, "
            f"country={self.config.country_code!r})"
        )
