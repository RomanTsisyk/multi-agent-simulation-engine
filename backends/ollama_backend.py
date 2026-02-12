"""Ollama backend -- talks to a locally-running Ollama server.

Default endpoint: http://localhost:11434/api/chat
Default model:    deepseek-r1:32b

The backend sends a *non-streaming* request and returns the full
assistant response as a string.  A generous 300-second timeout is used
because large local models can be slow on consumer hardware.

Includes automatic retry with exponential backoff and configurable
num_ctx to prevent silent prompt truncation.
"""

import asyncio
import logging
from typing import Any

import aiohttp

from backends.base import LLMBackend

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "deepseek-r1:32b"
_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TIMEOUT_S = 300  # 5 minutes -- local models can be slow
_DEFAULT_NUM_CTX = 16384  # context window -- Ollama defaults to 4096 which truncates prompts
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0  # seconds, doubles each retry


class OllamaBackend(LLMBackend):
    """LLM backend that delegates to a local Ollama instance.

    Args:
        model: Ollama model tag (e.g. ``"deepseek-r1:32b"``).
        base_url: Root URL of the Ollama HTTP API.
        timeout: Total request timeout in seconds.
        num_ctx: Context window size in tokens. Defaults to 16384.
        max_retries: Number of retry attempts on failure.
        retry_delay: Initial delay between retries (doubles each attempt).
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: int = _DEFAULT_TIMEOUT_S,
        num_ctx: int = _DEFAULT_NUM_CTX,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.num_ctx = num_ctx
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazily create (and cache) an ``aiohttp.ClientSession``."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    def _build_payload(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Build the JSON payload expected by ``/api/chat``."""
        ollama_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        for msg in messages:
            ollama_messages.append(
                {"role": msg["role"], "content": msg["content"]}
            )

        options: dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": self.num_ctx,
        }
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        return {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": options,
        }

    # ------------------------------------------------------------------
    # Public API (LLMBackend interface)
    # ------------------------------------------------------------------

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Send a chat completion request to the local Ollama server.

        Retries up to ``max_retries`` times with exponential backoff on
        transient failures (timeouts, HTTP 5xx, connection errors).

        Raises:
            ConnectionError: If Ollama is not reachable after all retries.
            TimeoutError: If all attempts time out.
            RuntimeError: On any other unexpected HTTP / API error.
        """
        url = f"{self.base_url}/api/chat"
        payload = self._build_payload(system_prompt, messages, temperature, max_tokens)

        logger.info(
            "Ollama request  | model=%s | messages=%d | num_ctx=%d",
            self.model, len(messages), self.num_ctx,
        )

        last_exc: Exception | None = None
        delay = self.retry_delay

        for attempt in range(1, self.max_retries + 1):
            try:
                session = await self._get_session()
                async with session.post(url, json=payload) as resp:
                    if resp.status >= 500:
                        body = await resp.text()
                        raise RuntimeError(
                            f"Ollama returned HTTP {resp.status}: {body}"
                        )
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(
                            f"Ollama returned HTTP {resp.status}: {body}"
                        )

                    data: dict = await resp.json()

                # Success -- extract and return
                content: str = data.get("message", {}).get("content", "")

                prompt_tokens = data.get("prompt_eval_count")
                completion_tokens = data.get("eval_count")
                if prompt_tokens is not None or completion_tokens is not None:
                    logger.info(
                        "Ollama response | model=%s | prompt_tokens=%s | completion_tokens=%s | attempt=%d",
                        self.model, prompt_tokens, completion_tokens, attempt,
                    )
                else:
                    logger.info(
                        "Ollama response | model=%s | tokens=N/A | attempt=%d",
                        self.model, attempt,
                    )

                return content

            except aiohttp.ClientConnectorError as exc:
                last_exc = ConnectionError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Is Ollama running? Try: ollama serve"
                )
                last_exc.__cause__ = exc

            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_exc = TimeoutError(
                    f"Ollama request timed out after {self.timeout.total}s "
                    f"(attempt {attempt}/{self.max_retries})."
                )
                last_exc.__cause__ = exc

            except RuntimeError as exc:
                if "HTTP 5" in str(exc):
                    last_exc = exc
                else:
                    raise  # 4xx errors are not retryable

            # Log retry and wait
            if attempt < self.max_retries:
                logger.warning(
                    "Ollama attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt, self.max_retries, last_exc, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2  # exponential backoff
            else:
                logger.error(
                    "Ollama all %d attempts failed. Last error: %s",
                    self.max_retries, last_exc,
                )

        raise last_exc  # type: ignore[misc]

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
