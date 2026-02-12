"""LLM backend layer for the WarGame simulation.

Usage::

    from backends import create_backend

    # Local Ollama
    backend = create_backend("ollama", model="deepseek-r1:32b")

    # DeepSeek API (R1)
    backend = create_backend("deepseek", model="deepseek-reasoner")

    response = await backend.generate(
        system_prompt="You are a military strategist.",
        messages=[{"role": "user", "content": "Analyse the situation."}],
    )
    await backend.close()
"""

from backends.base import LLMBackend
from backends.deepseek_backend import DeepSeekBackend
from backends.ollama_backend import OllamaBackend

__all__ = [
    "LLMBackend",
    "OllamaBackend",
    "DeepSeekBackend",
    "create_backend",
]

_BACKEND_REGISTRY: dict[str, type[LLMBackend]] = {
    "ollama": OllamaBackend,
    "deepseek": DeepSeekBackend,
}


def create_backend(backend_name: str, **kwargs) -> LLMBackend:
    """Factory that instantiates an LLM backend by name.

    Args:
        backend_name: One of ``"ollama"`` or ``"deepseek"``
            (case-insensitive).
        **kwargs: Forwarded to the backend constructor (e.g. ``model``,
            ``api_key``, ``timeout``).

    Returns:
        An instance of the requested :class:`LLMBackend` subclass.

    Raises:
        ValueError: If *backend_name* is not recognised.

    Examples::

        backend = create_backend("ollama")
        backend = create_backend("deepseek", model="deepseek-chat")
    """
    key = backend_name.strip().lower()
    cls = _BACKEND_REGISTRY.get(key)
    if cls is None:
        available = ", ".join(sorted(_BACKEND_REGISTRY))
        raise ValueError(
            f"Unknown backend {backend_name!r}. "
            f"Available backends: {available}"
        )
    return cls(**kwargs)
