"""Unit tests for the shared key-frame protection registry.

These are pure-logic tests (no Home Assistant runtime needed) covering the
mechanism that fixes the key-frame cleanup race: a snapshot written at the
start of an analysis must stay protected until its timeline event is inserted,
regardless of how long the (slow) analysis runs.
"""
import time

import pytest

from custom_components.llmvision import keyframe_registry as kr
from custom_components.llmvision.const import (
    CONF_CLEANUP_GRACE,
    CONF_PROVIDER,
    DEFAULT_CLEANUP_GRACE,
    DOMAIN,
)


class _FakeConfigEntries:
    def __init__(self, entries):
        self._entries = entries

    def async_entries(self, domain):
        return self._entries


class _FakeHass:
    """Minimal stand-in: the registry only needs ``.data`` and ``.config_entries``."""

    def __init__(self, entries=None):
        self.data = {}
        self.config_entries = _FakeConfigEntries(entries or [])


class _FakeEntry:
    def __init__(self, data):
        self.data = data


def test_protect_then_listed_then_released():
    hass = _FakeHass()
    kf = "/media/llmvision/snapshots/abc123-camera0.jpg"
    kr.protect(hass, kf, ttl=100)
    assert "abc123-camera0.jpg" in kr.protected_basenames(hass)
    kr.release(hass, kf)
    assert "abc123-camera0.jpg" not in kr.protected_basenames(hass)


def test_protect_uses_lowercased_basename():
    hass = _FakeHass()
    kr.protect(hass, "/x/AbC-Camera0.JPG", ttl=100)
    assert "abc-camera0.jpg" in kr.protected_basenames(hass)


def test_expired_entries_are_pruned():
    hass = _FakeHass()
    kr.protect(hass, "/x/expire-me.jpg", ttl=0.01)
    time.sleep(0.05)
    assert "expire-me.jpg" not in kr.protected_basenames(hass)
    # The backing dict is actually pruned, not just filtered.
    assert "expire-me.jpg" not in hass.data[DOMAIN][kr._PENDING_KEY]


def test_empty_or_none_keyframe_is_noop():
    hass = _FakeHass()
    kr.protect(hass, "", ttl=100)
    kr.protect(hass, None, ttl=100)
    kr.release(hass, "")  # must not raise
    assert kr.protected_basenames(hass) == set()


def test_get_grace_defaults_when_unset():
    hass = _FakeHass()
    assert kr.get_cleanup_grace(hass) == float(DEFAULT_CLEANUP_GRACE)


def test_set_and_get_cleanup_grace():
    hass = _FakeHass()
    kr.set_cleanup_grace(hass, 450)
    assert kr.get_cleanup_grace(hass) == 450.0


def test_get_grace_falls_back_to_settings_entry():
    hass = _FakeHass(
        entries=[_FakeEntry({CONF_PROVIDER: "Settings", CONF_CLEANUP_GRACE: 222})]
    )
    assert kr.get_cleanup_grace(hass) == 222.0


def test_protect_ttl_none_uses_global_grace():
    hass = _FakeHass()
    kr.set_cleanup_grace(hass, 30)
    before = time.time()
    kr.protect(hass, "/x/k.jpg", ttl=None)
    expiry = hass.data[DOMAIN][kr._PENDING_KEY]["k.jpg"]
    assert 29 <= (expiry - before) <= 31


def test_bad_grace_value_falls_back_to_default():
    hass = _FakeHass()
    kr.set_cleanup_grace(hass, "not-a-number")
    assert kr.get_cleanup_grace(hass) == float(DEFAULT_CLEANUP_GRACE)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
