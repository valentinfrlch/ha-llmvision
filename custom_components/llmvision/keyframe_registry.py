"""Shared, hass-global protection registry for in-flight key-frame snapshots.

Background
----------
``MediaProcessor._expose_image`` writes a key-frame snapshot to
``/media/llmvision/snapshots`` at the *start* of an analysis, but the matching
timeline event (which "links" the file and protects it from cleanup) is only
inserted at the *end*, after the LLM call returns. A ``Timeline`` object is
constructed per service call and per timeline API request, and each construction
schedules ``Timeline._cleanup()``. That cleanup deletes any snapshot that is not
linked to an event and is older than the grace window -- so for any analysis that
runs longer than the grace window, the key frame is swept *before* its event
exists, and the card/notification end up pointing at a missing file.

A per-instance ``_pending_key_frames`` set cannot fix this because the writer,
the inserter and the cleaner are three different ``Timeline``/``MediaProcessor``
objects. This module keeps the protection list in ``hass.data[DOMAIN]`` so every
instance sees the same set, with a TTL so a failed analysis cannot leak a file
forever.
"""

import os
import time

from .const import (
    CONF_CLEANUP_GRACE,
    CONF_PROVIDER,
    DEFAULT_CLEANUP_GRACE,
    DOMAIN,
)

_PENDING_KEY = "_pending_key_frames"
_GRACE_KEY = "_cleanup_grace"


def _basename(key_frame: str) -> str:
    return (os.path.basename(key_frame) or "").lower() if key_frame else ""


def _domain_data(hass) -> dict | None:
    """Return hass.data[DOMAIN] (creating it), or None if hass.data isn't a dict.

    Defensive: some unit tests pass a bare ``Mock`` as ``hass.data``; production
    always has a real dict.
    """
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return None
    domain_data = data.get(DOMAIN)
    if not isinstance(domain_data, dict):
        domain_data = {}
        data[DOMAIN] = domain_data
    return domain_data


def _registry(hass) -> dict:
    """Return the (lazily created) basename -> expiry-timestamp map."""
    domain_data = _domain_data(hass)
    if domain_data is None:
        return {}
    reg = domain_data.get(_PENDING_KEY)
    if not isinstance(reg, dict):
        reg = {}
        domain_data[_PENDING_KEY] = reg
    return reg


def protect(hass, key_frame: str, ttl: float | None = None) -> None:
    """Protect ``key_frame`` (by basename) from cleanup for up to ``ttl`` seconds.

    Call this the moment the snapshot is written, before the (slow) analysis
    runs. ``ttl`` defaults to the configured global cleanup grace.
    """
    base = _basename(key_frame)
    if not base:
        return
    if ttl is None:
        ttl = get_cleanup_grace(hass)
    try:
        ttl = float(ttl)
    except (TypeError, ValueError):
        ttl = float(DEFAULT_CLEANUP_GRACE)
    _registry(hass)[base] = time.time() + max(0.0, ttl)


def release(hass, key_frame: str) -> None:
    """Drop protection for ``key_frame`` once its event row exists.

    After the event is inserted the file is "linked", so the normal
    linked-file protection takes over and the TTL entry is no longer needed.
    """
    base = _basename(key_frame)
    if base:
        _registry(hass).pop(base, None)


def protected_basenames(hass) -> set:
    """Return basenames still under (unexpired) protection, pruning expired ones."""
    reg = _registry(hass)
    now = time.time()
    for base in [b for b, exp in reg.items() if exp <= now]:
        reg.pop(base, None)
    return set(reg.keys())


def set_cleanup_grace(hass, seconds) -> None:
    """Store the configured global cleanup grace (seconds) for this install."""
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        seconds = float(DEFAULT_CLEANUP_GRACE)
    domain_data = _domain_data(hass)
    if domain_data is not None:
        domain_data[_GRACE_KEY] = max(0.0, seconds)


def get_cleanup_grace(hass) -> float:
    """Return the configured global cleanup grace (seconds).

    Falls back to the Settings config entry, then ``DEFAULT_CLEANUP_GRACE``.
    """
    data = hass.data.get(DOMAIN) if isinstance(getattr(hass, "data", None), dict) else None
    if isinstance(data, dict) and _GRACE_KEY in data:
        return data[_GRACE_KEY]
    # Fall back to reading the Settings entry directly (cleanup can run before
    # async_setup_entry has cached the value).
    try:
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.data.get(CONF_PROVIDER) == "Settings":
                return float(
                    entry.data.get(CONF_CLEANUP_GRACE, DEFAULT_CLEANUP_GRACE)
                )
    except Exception:  # noqa: BLE001 - never let cleanup-grace lookup break cleanup
        pass
    return float(DEFAULT_CLEANUP_GRACE)
