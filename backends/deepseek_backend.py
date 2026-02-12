"""DeepSeek API backend -- OpenAI-compatible HTTP interface.

Supported models:
    - ``deepseek-reasoner``  (DeepSeek R1 -- reasoning-focused)
    - ``deepseek-chat``      (DeepSeek V3 -- general chat)

The API key is read from the ``DEEPSEEK_API_KEY`` environment variable.
A simple asyncio semaphore limits the number of concurrent in-flight
requests so we stay within rate limits.

Includes automatic retry with exponential backoff for transient errors.
"""

import asyncio
import logging
import os
from typing import Any

import aiohttp

from backends.base import LLMBackend

logger = logging.getLogger(__name__)

_API_URL = "https://api.deepseek.com/v1/chat/completions"
_DEFAULT_MODEL = "deepseek-reasoner"
_DEFAULT_TIMEOUT_S = 120
_DEFAULT_MAX_CONCURRENT = 5
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0


class DeepSeekBackend(LLMBackend):
    """LLM backend that calls the DeepSeek HTTP API.

    Args:
        model: Model identifier -- ``"deepseek-reasoner"`` (R1) or
            ``"deepseek-chat"`` (V3).
        api_key: DeepSeek API key.  Falls back to the
            ``DEEPSEEK_API_KEY`` environment variable when *None*.
        timeout: Per-request timeout in seconds.
        max_concurrent: Maximum number of requests that may be in-flight
            at the same time (simple semaphore-based rate limiter).
        max_retries: Number of retry attempts on transient failures.
        retry_delay: Initial delay between retries (doubles each attempt).
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        api_key: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT_S,
        max_concurrent: int = _DEFAULT_MAX_CONCURRENT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "DeepSeek API key not provided. Set the DEEPSEEK_API_KEY "
                "environment variable or pass api_key= to the constructor."
            )

        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: aiohttp.ClientSession | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        """Lazily create (and cache) an ``aiohttp.ClientSession``."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._session

    def _build_payload(
        self,
        system_prompt: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Build an OpenAI-compatible chat completion payload."""
        api_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
        ]
        for msg in messages:
            api_messages.append(
                {"role": msg["role"], "content": msg["content"]}
            )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        return payload

    @staticmethod
    def _is_retryable(status: int) -> bool:
        """Return True for HTTP status codes that warrant a retry."""
        return status == 429 or status >= 500

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
        """Send a chat completion request to the DeepSeek API.

        The call is guarded by an ``asyncio.Semaphore`` so that at most
        *max_concurrent* requests are in-flight simultaneously.

        Retries up to ``max_retries`` times with exponential backoff on
        transient failures (timeouts, HTTP 429/5xx).

        Raises:
            RuntimeError: On non-200 HTTP responses from the API.
            TimeoutError: If the request exceeds the configured timeout.
        """
        payload = self._build_payload(system_prompt, messages, temperature, max_tokens)

        logger.info(
            "DeepSeek request  | model=%s | messages=%d",
            self.model,
            len(messages),
        )

        last_exc: Exception | None = None
        delay = self.retry_delay

        for attempt in range(1, self.max_retries + 1):
            try:
                async with self._semaphore:
                    session = await self._get_session()
                    async with session.post(_API_URL, json=payload) as resp:
                        if self._is_retryable(resp.status):
                            body = await resp.text()
                            raise RuntimeError(
                                f"DeepSeek API returned HTTP {resp.status}: {body}"
                            )
                        if resp.status != 200:
                            body = await resp.text()
                            raise ValueError(
                                f"DeepSeek API returned HTTP {resp.status}: {body}"
                            )

                        data: dict[str, Any] = await resp.json()

                # Success -- extract and return
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError(
                        "DeepSeek API returned an empty choices array."
                    )

                content: str = choices[0].get("message", {}).get("content", "")

                usage: dict[str, int] = data.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                total_tokens = usage.get("total_tokens")

                logger.info(
                    "DeepSeek response | model=%s | prompt_tokens=%s | "
                    "completion_tokens=%s | total_tokens=%s | attempt=%d",
                    self.model, prompt_tokens, completion_tokens,
                    total_tokens, attempt,
                )

                return content

            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_exc = TimeoutError(
                    f"DeepSeek request timed out after {self.timeout.total}s "
                    f"(attempt {attempt}/{self.max_retries})."
                )
                last_exc.__cause__ = exc

            except RuntimeError as exc:
                # RuntimeError from retryable HTTP status
                last_exc = exc

            except ValueError:
                raise  # non-retryable 4xx errors

            # Log retry and wait
            if attempt < self.max_retries:
                logger.warning(
                    "DeepSeek attempt %d/%d failed: %s. Retrying in %.1fs...",
                    attempt, self.max_retries, last_exc, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
            else:
                logger.error(
                    "DeepSeek all %d attempts failed. Last error: %s",
                    self.max_retries, last_exc,
                )

        raise last_exc  # type: ignore[misc]

    @property
    def supports_parallel(self) -> bool:
        """DeepSeek API supports concurrent requests (semaphore-limited)."""
        return True

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
