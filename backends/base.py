"""Abstract base class for LLM backends.

All LLM backends (Ollama, DeepSeek, etc.) must inherit from LLMBackend
and implement the generate() and close() methods.
"""

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    """Base interface that every LLM backend must implement.

    Subclasses are responsible for managing their own HTTP sessions,
    API keys, and model-specific serialisation.
    """

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a single text response from the model.

        Args:
            system_prompt: The system-level instruction that frames the
                conversation (e.g. "You are a military strategist ...").
            messages: Conversation history as a list of dicts, each with
                ``"role"`` (``"user"`` or ``"assistant"``) and
                ``"content"`` (a string).
            temperature: Sampling temperature.  Lower values produce more
                deterministic output; higher values increase creativity.
            max_tokens: Optional maximum number of tokens in the response.
                If *None*, the model's default limit is used.

        Returns:
            The model's response as a plain string.
        """
        pass

    @property
    def supports_parallel(self) -> bool:
        """Whether this backend can handle multiple concurrent requests.

        API backends (DeepSeek, OpenAI) return True; local backends
        (Ollama with a single GPU) return False.  The game engine uses
        this to decide whether to parallelise country deliberations.
        """
        return False

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by the backend (HTTP sessions, etc.)."""
        pass
