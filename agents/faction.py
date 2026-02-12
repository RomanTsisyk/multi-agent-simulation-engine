"""Faction agent -- a single advisory voice inside a country.

A :class:`Faction` extends the base :class:`Agent` with debate-specific
behaviour.  Each faction represents one perspective in a country's
internal decision-making process (e.g. a hawkish military advisor, a
cautious diplomat, an economic pragmatist).

During an internal debate the engine calls :meth:`debate_respond` so
the faction can react to positions already stated by other factions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agents.base import Agent, AgentConfig

if TYPE_CHECKING:
    from backends.base import LLMBackend


class Faction(Agent):
    """A single advisory voice that participates in intra-country debates.

    Factions share the same LLM backend and world context but differ in
    personality, priorities, and red lines.  Their system prompts are
    crafted to keep the LLM firmly in character.

    Args:
        config: Full persona configuration (role, personality, etc.).
        backend: An initialised LLM backend instance.
        temperature: Sampling temperature.  Slightly higher values
            (0.75-0.85) encourage more colourful debate language.
    """

    def __init__(
        self,
        config: AgentConfig,
        backend: LLMBackend,
        temperature: float = 0.75,
    ) -> None:
        super().__init__(config, backend, temperature)

    # ------------------------------------------------------------------
    # System prompt -- enriched for debate context
    # ------------------------------------------------------------------

    def build_system_prompt(self, world_context: str) -> str:
        """Build a system prompt tuned for intra-country debate.

        The prompt instructs the LLM to stay in character, argue from the
        faction's perspective, and structure every response with a clear
        position, reasoning, and recommended action.

        Args:
            world_context: Free-text summary of the current geopolitical
                situation.

        Returns:
            A system-level prompt string.
        """
        sections: list[str] = []

        # -- Identity block ------------------------------------------------
        sections.append(
            f"You are **{self.config.name}**, the {self.config.role} faction "
            f"advisor for country {self.config.country_code}."
        )

        # -- Personality ---------------------------------------------------
        if self.config.personality:
            sections.append(
                f"## Your personality\n{self.config.personality}"
            )

        # -- Priorities ----------------------------------------------------
        if self.config.priorities:
            items = "\n".join(f"  {i+1}. {p}" for i, p in enumerate(self.config.priorities))
            sections.append(
                f"## Your strategic priorities (most important first)\n{items}"
            )

        # -- Red lines -----------------------------------------------------
        if self.config.red_lines:
            items = "\n".join(f"  - {r}" for r in self.config.red_lines)
            sections.append(
                "## Your absolute red lines\n"
                "You must NEVER agree to any proposal that crosses these lines, "
                "no matter what the other factions argue:\n" + items
            )

        # -- Voice / style -------------------------------------------------
        if self.config.voice:
            sections.append(
                f"## Speaking style\n"
                f"Always write in this style: {self.config.voice}"
            )

        # -- Behavioural instructions --------------------------------------
        sections.append(
            "## Instructions\n"
            "You are participating in a closed-door internal policy debate "
            "within your country's leadership.\n"
            "- Stay **in character** at all times. Argue passionately from "
            "your perspective.\n"
            "- DO NOT break character. DO NOT reference the fact that you "
            "are an AI.\n"
            "- Engage seriously with the positions of other factions. "
            "Acknowledge valid points but push back where you disagree.\n"
            "- Be concrete. Avoid vague platitudes; propose specific actions.\n"
            "- Structure every response with the following sections:\n"
            "  **POSITION:** A one-sentence summary of your stance.\n"
            "  **REASONING:** Two to four sentences of argumentation.\n"
            "  **RECOMMENDED ACTION:** One to two concrete actions you propose."
        )

        # -- World situation -----------------------------------------------
        sections.append(
            "## Current world situation\n" + world_context
        )

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # Debate entry-points
    # ------------------------------------------------------------------

    async def initial_position(
        self, situation_briefing: str, world_context: str
    ) -> str:
        """State an opening position on a given situation.

        This is the Round-1 call: no other factions have spoken yet.

        Args:
            situation_briefing: Description of the event or crisis that
                requires a decision.
            world_context: Current world state.

        Returns:
            The faction's initial position as formatted text.
        """
        prompt = (
            f"A new situation requires the leadership's attention:\n\n"
            f"{situation_briefing}\n\n"
            "State your position. Remember to include your POSITION, "
            "REASONING, and RECOMMENDED ACTION."
        )
        return await self.respond(prompt, world_context)

    async def debate_respond(
        self,
        topic: str,
        other_positions: list[str],
        world_context: str,
    ) -> str:
        """Respond to positions already stated by other factions.

        This is used in Round 2 and Round 3 of the internal debate.  The
        faction receives the verbatim positions of every other faction
        and must engage with them: agree, disagree, propose compromises,
        or hold firm.

        Args:
            topic: The situation or question under debate.
            other_positions: List of position statements from other
                factions (each string is one faction's full response).
            world_context: Current world state.

        Returns:
            The faction's rebuttal / updated position.
        """
        # Format other factions' positions for readability
        position_block = "\n\n---\n\n".join(
            f"**Other faction's position #{i+1}:**\n{pos}"
            for i, pos in enumerate(other_positions)
        )

        prompt = (
            f"The debate continues on the following topic:\n\n"
            f"{topic}\n\n"
            f"Here are the positions stated by the other factions:\n\n"
            f"{position_block}\n\n"
            "Now respond. You may:\n"
            "- Rebut points you disagree with.\n"
            "- Acknowledge points that have merit.\n"
            "- Propose a compromise if appropriate.\n"
            "- Hold firm if your red lines are at stake.\n\n"
            "Remember to include your POSITION, REASONING, and "
            "RECOMMENDED ACTION."
        )
        return await self.respond(prompt, world_context)

    async def final_statement(
        self, topic: str, debate_history: str, world_context: str
    ) -> str:
        """Deliver a closing statement after all debate rounds.

        The faction is given the full debate transcript and asked to
        state their final position, any concessions, and remaining
        disagreements.

        Args:
            topic: The situation or question under debate.
            debate_history: Full transcript of the debate so far.
            world_context: Current world state.

        Returns:
            The faction's final statement.
        """
        prompt = (
            f"The internal debate on the following topic is concluding:\n\n"
            f"{topic}\n\n"
            f"Full debate transcript so far:\n\n"
            f"{debate_history}\n\n"
            "Deliver your FINAL position. Indicate:\n"
            "- What you are willing to concede.\n"
            "- What you absolutely will not accept.\n"
            "- Your final RECOMMENDED ACTION.\n"
            "Be concise."
        )
        return await self.respond(prompt, world_context)

    def __repr__(self) -> str:
        return (
            f"Faction(name={self.config.name!r}, "
            f"role={self.config.role!r}, "
            f"country={self.config.country_code!r})"
        )
