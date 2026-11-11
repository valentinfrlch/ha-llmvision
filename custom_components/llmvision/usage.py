"""Opt-in, local accounting of provider-reported usage.

Inspired by bforejt's token usage proposal and normalization convention:
https://github.com/valentinfrlch/ha-llmvision/discussions/714
No request/response content is retained. Unknown usage is never estimated.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import CONF_PROVIDER, CONF_TRACK_USAGE, DOMAIN

USAGE_DATA = "llmvision_usage"
SIGNAL_USAGE_UPDATED = "llmvision_usage_updated"
EVENT_TOKEN_USAGE = "llmvision_token_usage"
EVENT_CALL_FINISHED = "llmvision_call_finished"
PROVIDERS = frozenset(
    {
        "OpenAI",
        "Azure",
        "Anthropic",
        "Google",
        "Groq",
        "LocalAI",
        "Ollama",
        "Custom OpenAI",
        "AWS Bedrock",
        "AWS",
        "Open WebUI",
        "OpenWebUI",
        "OpenRouter",
        "Mistral",
    }
)
SERVICES = frozenset(
    {"image_analyzer", "video_analyzer", "stream_analyzer", "data_analyzer"}
)
TOKEN_KEYS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)
COUNTER_KEYS = (
    "calls",
    "errors",
    "missing_usage",
    *TOKEN_KEYS,
    *(f"{phase}_{key}" for phase in ("analysis", "title") for key in TOKEN_KEYS[:3]),
)
_LOGGER = logging.getLogger(__name__)


def is_provider_entry(entry: ConfigEntry) -> bool:
    """Exclude settings and legacy non-provider entries from accounting."""
    return entry.data.get(CONF_PROVIDER) in PROVIDERS


def _count(value: Any) -> int | None:
    """Accept actual nonnegative integer counts, not coerced or estimated values."""
    return value if type(value) is int and value >= 0 else None


def normalize_usage(response: Any) -> dict[str, int] | None:
    """Normalize five schemas; cache/reasoning breakdowns are subsets of totals.

    Anthropic cache counts and Gemini thoughts are disjoint in their APIs and
    must be added. Missing/malformed core counts remain unknown, not zero.
    """
    if not isinstance(response, dict):
        return None
    usage = response.get("usage")
    usage = usage if isinstance(usage, dict) else {}
    extras: dict[str, Any] = {}
    additive_input: tuple[str, ...] = ()
    additive_output: tuple[str, ...] = ()
    # Schema selection is explicit: cache semantics differ even when the
    # providers use similar field names. Do not combine keys across schemas.
    if isinstance(response.get("usageMetadata"), dict):
        # Gemini thoughts are outside candidate tokens; cached input is inside
        # promptTokenCount. Adding both optional fields would overcount input.
        usage = response["usageMetadata"]
        input_key, output_key, total_key = (
            "promptTokenCount",
            "candidatesTokenCount",
            "totalTokenCount",
        )
        extras = {
            "cache_read_tokens": usage.get("cachedContentTokenCount"),
            "reasoning_tokens": usage.get("thoughtsTokenCount"),
        }
        additive_output = ("thoughtsTokenCount",)
    elif "prompt_tokens" in usage or "completion_tokens" in usage:
        # OpenAI-compatible cache and reasoning details are already subsets.
        input_key, output_key, total_key = (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
        )
        prompt = usage.get("prompt_tokens_details")
        completion = usage.get("completion_tokens_details")
        extras = {
            "cache_read_tokens": (
                prompt.get("cached_tokens") if isinstance(prompt, dict) else None
            ),
            "reasoning_tokens": (
                completion.get("reasoning_tokens")
                if isinstance(completion, dict)
                else None
            ),
        }
    elif "input_tokens" in usage or "output_tokens" in usage:
        # Anthropic reports cache reads/writes outside its uncached input count.
        input_key, output_key, total_key = (
            "input_tokens",
            "output_tokens",
            "total_tokens",
        )
        additive_input = ("cache_read_input_tokens", "cache_creation_input_tokens")
        extras = {
            "cache_read_tokens": usage.get("cache_read_input_tokens"),
            "cache_write_tokens": usage.get("cache_creation_input_tokens"),
        }
    elif "inputTokens" in usage or "outputTokens" in usage:
        input_key, output_key, total_key = "inputTokens", "outputTokens", "totalTokens"
        # Bedrock Converse exposes cache counts separately from uncached input.
        additive_input = ("cacheReadInputTokens", "cacheWriteInputTokens")
        extras = {
            "cache_read_tokens": usage.get("cacheReadInputTokens"),
            "cache_write_tokens": usage.get("cacheWriteInputTokens"),
        }
    elif "prompt_eval_count" in response or "eval_count" in response:
        usage = response
        input_key, output_key, total_key = (
            "prompt_eval_count",
            "eval_count",
            "total_tokens",
        )
    else:
        return None
    input_tokens, output_tokens = _count(usage.get(input_key)), _count(
        usage.get(output_key)
    )
    if input_tokens is None or output_tokens is None:
        return None
    for key in additive_input + additive_output:
        if key in usage and _count(usage[key]) is None:
            return None
    input_tokens += sum(usage.get(key, 0) for key in additive_input)
    output_tokens += sum(usage.get(key, 0) for key in additive_output)
    # Keep extra provider-reported categories in a larger total. A smaller total
    # may exclude separately reported cache/thinking counts, so use the sum.
    total = _count(usage.get(total_key))
    result = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": max(total or 0, input_tokens + output_tokens),
    }
    for key, raw in extras.items():
        value = _count(raw)
        bound = output_tokens if key == "reasoning_tokens" else input_tokens
        if value is not None and value <= bound:
            result[key] = value
    return result


def safe_model(model: Any) -> str | None:
    """Only expose bounded model identifiers, never arbitrary provider text/URLs."""
    if (
        isinstance(model, str)
        and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,127}", model)
        and "://" not in model
        and not model.startswith("arn:")
    ):
        return model
    return None


class UsageManager:
    """Persist bounded per-entry totals independently of Recorder retention."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        # Providers can start before Settings. Read its saved opt-in, but never
        # revive a disabled Settings entry merely because HA has restarted.
        self._enabled = any(
            entry.data.get(CONF_PROVIDER) == "Settings"
            and entry.data.get(CONF_TRACK_USAGE, False) is True
            and entry.disabled_by is None
            for entry in hass.config_entries.async_entries(DOMAIN)
        )
        self._store = Store(hass, 1, USAGE_DATA)
        self._totals: dict[str, dict[str, int]] = {}
        self._lock = asyncio.Lock()
        self._loaded = False
        self._storage_available = True
        self._removed: set[str] = set()

    async def async_load(self) -> None:
        """Serialize first load even when HA starts provider entries in parallel."""
        async with self._lock:
            if self._loaded:
                return
            try:
                data = await self._store.async_load()
                restored: dict[str, dict[str, int]] = {}
                # None means a new store. Any malformed existing payload must
                # fail closed: silently dropping bad counters resets lifetime
                # statistics and the next save would destroy the old evidence.
                if data is not None:
                    if not isinstance(data, dict):
                        raise ValueError("Invalid usage storage structure")
                    for entry_id, totals in data.items():
                        if not isinstance(entry_id, str) or not isinstance(
                            totals, dict
                        ):
                            raise ValueError("Invalid usage storage entry")
                        restored[entry_id] = {}
                        for key in COUNTER_KEYS:
                            if key not in totals:
                                # New counters can be added in compatible releases.
                                continue
                            value = _count(totals[key])
                            if value is None:
                                raise ValueError("Invalid usage storage counter")
                            restored[entry_id][key] = value
                self._totals = restored
            except Exception:
                # Analysis remains usable even when local storage is broken.
                # Never include the error or corrupt content in a log message.
                self._storage_available = False
                _LOGGER.warning(
                    "Token usage storage is unavailable; tracking is disabled"
                )
            self._loaded = True

    @property
    def enabled(self) -> bool:
        """Require opt-in and a successful restore before recording new totals."""
        return self._enabled and self._loaded and self._storage_available

    @callback
    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled is True
        async_dispatcher_send(self.hass, SIGNAL_USAGE_UPDATED, None)

    def get_totals(self, entry_id: str) -> dict[str, int]:
        """Return a copy so an entity cannot mutate the manager's accumulator."""
        stored = self._totals.get(entry_id, {})
        return {key: stored.get(key, 0) for key in COUNTER_KEYS}

    async def async_record(
        self,
        *,
        entry_id: str,
        provider: str,
        model: str,
        service: str,
        phase: str,
        usage: dict[str, int] | None,
        failed: bool,
        duration_ms: int,
        context: Context | None = None,
    ) -> None:
        """Account once per attempted analysis/title call; never retain raw content."""
        if (
            not self.enabled
            or provider not in PROVIDERS
            or phase not in ("analysis", "title")
        ):
            return
        async with self._lock:
            if not self.enabled or entry_id in self._removed:
                return
            totals = self._totals.setdefault(entry_id, {})
            increments = {
                "calls": 1,
                "errors": int(failed),
                "missing_usage": int(usage is None),
            }
            if usage is not None:
                increments.update(
                    {
                        key: value
                        for key in TOKEN_KEYS
                        if (value := _count(usage.get(key))) is not None
                    }
                )
                increments.update(
                    {f"{phase}_{key}": usage[key] for key in TOKEN_KEYS[:3]}
                )
            for key, value in increments.items():
                totals[key] = totals.get(key, 0) + value
            # Only allowlisted, content-free fields cross the event bus. Counters
            # remain valid even if an event listener or persistence later fails.
            payload = {
                "schema": 1,
                "provider": provider,
                "config_entry_id": entry_id,
                "service": service if service in SERVICES else "unknown",
                "request_type": phase,
                "status": "error" if failed else "success",
                "usage_available": usage is not None,
                "duration_ms": max(0, duration_ms),
            }
            if (identifier := safe_model(model)) is not None:
                payload["model"] = identifier
            try:
                self.hass.bus.async_fire(EVENT_CALL_FINISHED, payload, context=context)
                if usage is not None:
                    self.hass.bus.async_fire(
                        EVENT_TOKEN_USAGE,
                        {
                            **payload,
                            **{key: usage[key] for key in TOKEN_KEYS if key in usage},
                        },
                        context=context,
                    )
                async_dispatcher_send(self.hass, SIGNAL_USAGE_UPDATED, entry_id)
            except Exception:
                _LOGGER.warning("Unable to publish token usage update")
            try:
                await self._store.async_save(self._totals)
            except Exception:
                _LOGGER.warning("Unable to persist token usage counters")

    async def async_remove(self, entry_id: str) -> None:
        """Discard only the removed provider; ordinary reloads never call this."""
        async with self._lock:
            # An in-flight provider response must not recreate deleted totals.
            self._removed.add(entry_id)
            if self._totals.pop(entry_id, None) is not None:
                await self._store.async_save(self._totals)


async def async_get_manager(hass: HomeAssistant) -> UsageManager:
    """Get the single integration-wide manager, outside provider config data."""
    if USAGE_DATA not in hass.data:
        hass.data[USAGE_DATA] = UsageManager(hass)
    manager = hass.data[USAGE_DATA]
    await manager.async_load()
    return manager
