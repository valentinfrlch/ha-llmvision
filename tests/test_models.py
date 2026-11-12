"""Unit tests for the model capability registry."""

from dataclasses import FrozenInstanceError

import pytest

from custom_components.llmvision.models import (
    ADAPTIVE,
    ADAPTIVE_ALWAYS,
    ADAPTIVE_ALWAYS_NO_FORCED_TOOL,
    ADAPTIVE_OR_MANUAL,
    EFFORT_ORDER,
    MANUAL_ONLY,
    MODELS,
    SAMPLING_PARAMS,
    UNKNOWN,
    Model,
    Thinking,
    build_params,
    get,
    normalize_effort,
)


def test_effort_order_matches_effort_literal():
    assert EFFORT_ORDER == (
        "none",
        "minimal",
        "low",
        "medium",
        "high",
        "xhigh",
        "max",
    )


def test_sampling_params_are_the_rejected_claude_fields():
    assert SAMPLING_PARAMS == ("temperature", "top_p", "top_k")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("high", "high"),
        (" HIGH ", "high"),
        ("XHigh", "xhigh"),
        (None, "none"),
        ("", "none"),
        ("invalid", "none"),
        (7, "none"),
    ],
)
def test_normalize_effort(value, expected):
    assert normalize_effort(value) == expected


def test_model_defaults():
    model = Model(name="test-model")

    assert model.name == "test-model"
    assert model.efforts == ()
    assert model.params == frozenset()
    assert model.thinking == Thinking()


def test_thinking_defaults():
    thinking = Thinking()

    assert thinking.adaptive is False
    assert thinking.manual is False
    assert thinking.can_disable is False
    assert thinking.between_tools is False
    assert thinking.forced_tool_choice is True


def test_thinking_presets_are_distinct():
    assert ADAPTIVE_ALWAYS.adaptive is True
    assert ADAPTIVE_ALWAYS.can_disable is False
    assert ADAPTIVE_ALWAYS_NO_FORCED_TOOL.forced_tool_choice is False
    assert ADAPTIVE.can_disable is True
    assert ADAPTIVE_OR_MANUAL.manual is True
    assert ADAPTIVE_OR_MANUAL.adaptive is True
    assert MANUAL_ONLY.manual is True
    assert MANUAL_ONLY.adaptive is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"efforts": ("turbo",)}, "unknown effort"),
        ({"efforts": ("high", "high")}, "duplicate effort"),
        ({"params": frozenset({"nope"})}, "unknown parameter"),
        (
            {"efforts": ("high",), "params": frozenset({"temperature"})},
            "without an effort param",
        ),
        (
            {"params": frozenset({"temperature"}), "thinking": ADAPTIVE},
            "without thinking param",
        ),
    ],
)
def test_model_rejects_invalid_capabilities(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Model(name="bad", **kwargs)


def test_model_accepts_thinking_level_as_effort_param():
    model = Model(
        name="gemini-x",
        efforts=("low", "high"),
        params=frozenset({"temperature", "thinking_level"}),
    )

    assert model.supports("thinking_level") is True
    assert model.resolve_effort("high") == "high"


def test_model_accepts_thinking_flag():
    model = Model(
        name="claude-x",
        efforts=("low", "high"),
        params=frozenset({"effort", "thinking"}),
        thinking=ADAPTIVE,
    )

    assert model.supports("thinking") is True
    assert model.supports("effort") is True


def test_model_is_frozen_and_hashable():
    model = Model(name="x", params=frozenset({"temperature"}))

    with pytest.raises(FrozenInstanceError):
        model.name = "y"
    assert hash(model) == hash(Model(name="x", params=frozenset({"temperature"})))


def test_supports_reports_declared_params_only():
    model = Model(name="x", params=frozenset({"temperature", "top_p"}))

    assert model.supports("temperature") is True
    assert model.supports("top_p") is True
    assert model.supports("top_k") is False
    assert model.supports("reasoning_effort") is False


def test_resolve_effort_without_levels_returns_none():
    assert Model(name="x").resolve_effort("high") is None


def test_resolve_effort_returns_exact_level():
    model = Model(
        name="x", efforts=("low", "medium", "high"), params=frozenset({"effort"})
    )

    assert model.resolve_effort("medium") == "medium"


def test_resolve_effort_clamps_to_highest_supported_level():
    model = Model(
        name="x",
        efforts=("none", "low", "medium", "high", "xhigh"),
        params=frozenset({"reasoning_effort"}),
    )

    assert model.resolve_effort("max") == "xhigh"
    assert model.resolve_effort("xhigh") == "xhigh"
    assert model.resolve_effort("minimal") == "none"


def test_resolve_effort_returns_none_below_smallest_level():
    model = Model(name="x", efforts=("medium", "high"), params=frozenset({"effort"}))

    assert model.resolve_effort("low") is None
    assert model.resolve_effort("none") is None


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(" HIGH ", "high"), (None, None), ("invalid", None), (7, None)],
)
def test_resolve_effort_normalizes_request(requested, expected):
    model = Model(
        name="x", efforts=("low", "medium", "high"), params=frozenset({"effort"})
    )

    assert model.resolve_effort(requested) == expected


def test_build_params_keeps_only_supported_keys():
    model = Model(name="x", params=frozenset({"temperature", "top_p"}))

    assert build_params(model, {"temperature": 0.2, "top_p": 0.9, "top_k": 5}) == {
        "temperature": 0.2,
        "top_p": 0.9,
    }


def test_build_params_strict_raises_for_rejected_keys():
    model = Model(name="x", params=frozenset({"temperature"}))

    with pytest.raises(ValueError) as exc:
        build_params(model, {"temperature": 0.2, "top_k": 5}, strict=True)

    assert "x does not accept ['top_k']" in str(exc.value)


def test_build_params_strict_passes_when_all_keys_supported():
    model = Model(name="x", params=frozenset({"temperature"}))

    assert build_params(model, {"temperature": 0.2}, strict=True) == {
        "temperature": 0.2
    }


def test_build_params_names_unknown_models():
    with pytest.raises(ValueError) as exc:
        build_params(UNKNOWN, {"top_k": 5}, strict=True)

    assert "unknown model does not accept ['top_k']" in str(exc.value)


def test_get_returns_registry_instance():
    assert get("gpt-5") is MODELS["gpt-5"]
    assert get("claude-sonnet-5") is MODELS["claude-sonnet-5"]
    assert get("gemini-3.8-flash") is MODELS["gemini-3.8-flash"]


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("gpt-5", "gpt-5"),
        ("GPT-5", "gpt-5"),
        ("  gpt-5  ", "gpt-5"),
        ("gpt-5-2026-01-15", "gpt-5"),
        ("gpt-5.6-terra", "gpt-5.6-terra"),
        ("claude-opus-4-7", "claude-opus-4-7"),
        ("anthropic.claude-sonnet-5", "claude-sonnet-5"),
        ("gemini-2.5-flash-lite", "gemini-2.5-flash-lite"),
        ("gemini-3.1-pro-preview", "gemini-3.1-pro-preview"),
    ],
)
def test_get_resolves_known_models(requested, expected):
    assert get(requested).name == expected


@pytest.mark.parametrize(
    "requested",
    ["", None, "gpt", "gpt-5.40", "gpt-6-luna-custom", "llama3.2-vision", "gemini-9"],
)
def test_get_falls_back_to_unknown(requested):
    assert get(requested) is UNKNOWN


def test_registry_keys_match_entry_names():
    assert MODELS
    for name, model in MODELS.items():
        assert model.name == name


def test_registry_entries_are_frozen():
    for model in MODELS.values():
        with pytest.raises(FrozenInstanceError):
            model.name = "changed"


def test_registry_covers_every_provider_family():
    families = {name.split("-")[0] for name in MODELS}

    assert {"gpt", "claude", "gemini"} <= families


def test_claude_entries_never_declare_sampling_params():
    claude = {
        name: model for name, model in MODELS.items() if name.startswith("claude-")
    }

    assert claude
    for name, model in claude.items():
        assert not set(SAMPLING_PARAMS) & model.params, name
        assert model.supports("thinking") is True, name


def test_openai_entries_declare_reasoning_effort_only():
    openai_models = {
        name: model for name, model in MODELS.items() if name.startswith("gpt-")
    }

    assert openai_models
    for name, model in openai_models.items():
        assert model.supports("reasoning_effort") is True, name
        assert model.supports("effort") is False, name
        assert model.supports("thinking") is False, name


def test_gemini_entries_declare_thinking_level_with_levels():
    gemini = {
        name: model for name, model in MODELS.items() if name.startswith("gemini-")
    }

    assert gemini
    for name, model in gemini.items():
        assert model.supports("temperature") is True, name
        assert model.supports("top_p") is True, name
        assert model.supports("thinking_level") is bool(model.efforts), name


@pytest.mark.parametrize("name", ["gpt-5", "gpt-5-mini", "gpt-5-nano"])
def test_gpt5_family_rejects_sampling_params(name):
    model = get(name)

    assert model.supports("temperature") is False
    assert model.supports("top_p") is False
    assert model.efforts == ("minimal", "low", "medium", "high")


def test_gpt5_pro_only_supports_high_effort():
    model = get("gpt-5-pro")

    assert model.efforts == ("high",)
    assert model.resolve_effort("low") is None
    assert model.resolve_effort("high") == "high"


def test_gpt51_caps_at_high_effort():
    model = get("gpt-5.1")

    assert model.resolve_effort("xhigh") == "high"
    assert model.resolve_effort("max") == "high"


def test_gpt61_sol_cannot_disable_reasoning():
    model = get("gpt-6.1-sol")

    assert "none" not in model.efforts
    assert model.resolve_effort("none") is None


def test_gpt54_pro_starts_at_medium():
    model = get("gpt-5.4-pro")

    assert model.efforts == ("medium", "high", "xhigh")
    assert model.resolve_effort("minimal") is None


@pytest.mark.parametrize(
    "name",
    [
        "claude-fable-5-2",
        "claude-mythos-5-2",
        "claude-fable-5-1",
        "claude-mythos-5-1",
        "claude-opus-5-5",
        "claude-sonnet-5-5",
    ],
)
def test_claude_models_reject_forced_tool_use(name):
    assert get(name).thinking.forced_tool_choice is False


@pytest.mark.parametrize("name", ["claude-fable-5", "claude-mythos-5"])
def test_claude_always_on_models_cannot_disable_thinking(name):
    thinking = get(name).thinking

    assert thinking.adaptive is True
    assert thinking.can_disable is False


def test_claude_sonnet_55_uses_between_tools():
    thinking = get("claude-sonnet-5-5").thinking

    assert thinking.adaptive is True
    assert thinking.between_tools is True


@pytest.mark.parametrize(
    "name", ["claude-sonnet-4-5", "claude-opus-4", "claude-3-7-sonnet"]
)
def test_claude_manual_only_models_have_no_levels(name):
    model = get(name)

    assert model.efforts == ()
    assert model.thinking.manual is True
    assert model.thinking.adaptive is False


def test_claude_46_models_support_both_thinking_modes():
    model = get("claude-opus-4-6")

    assert model.thinking.adaptive is True
    assert model.thinking.manual is True
    assert model.efforts == ("low", "medium", "high", "max")


def test_gemini_4_omits_deprecated_thinking_budget():
    argon = get("gemini-4-argon")

    assert argon.supports("thinking_level") is True
    assert argon.supports("thinking_budget") is False
    assert "minimal" not in argon.efforts


def test_gemini_38_flash_rejects_minimal_level():
    flash = get("gemini-3.8-flash")

    assert flash.efforts == ("low", "medium", "high")
    assert flash.resolve_effort("minimal") is None
    assert flash.resolve_effort("medium") == "medium"


def test_gemini_36_flash_supports_minimal_level():
    flash = get("gemini-3.6-flash")

    assert flash.efforts[0] == "minimal"
    assert flash.resolve_effort("minimal") == "minimal"


@pytest.mark.parametrize(
    "name", ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
)
def test_gemini_25_models_use_budget_only(name):
    model = get(name)

    assert model.efforts == ()
    assert model.supports("thinking_budget") is True
    assert model.supports("thinking_level") is False
    assert model.resolve_effort("high") is None


def test_unknown_model_capabilities():
    assert UNKNOWN.name == ""
    assert UNKNOWN.supports("temperature") is True
    assert UNKNOWN.supports("top_p") is True
    assert UNKNOWN.supports("reasoning_effort") is False
    assert UNKNOWN.resolve_effort("high") is None
    assert UNKNOWN.thinking == Thinking()
