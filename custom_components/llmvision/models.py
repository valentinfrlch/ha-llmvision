from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, cast, get_args

Effort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
EFFORT_ORDER: tuple[Effort, ...] = get_args(Effort)

Param = Literal[
    "temperature",
    "top_p",
    "top_k",
    "reasoning_effort",
    "effort",
    "thinking",
    "thinking_budget",
    "thinking_level",
]


@dataclass(frozen=True, slots=True)
class Thinking:
    """Which ``thinking.type`` values a model accepts, and whether it allows
    forced tool use."""

    adaptive: bool = False
    manual: bool = False
    can_disable: bool = False
    between_tools: bool = False
    forced_tool_choice: bool = True


# Always-on adaptive thinking: "enabled" and "disabled" both return 400.
ADAPTIVE_ALWAYS = Thinking(adaptive=True)
# Always-on adaptive thinking that also rejects forced tool use.
ADAPTIVE_ALWAYS_NO_FORCED_TOOL = Thinking(adaptive=True, forced_tool_choice=False)
# Adaptive by default, can be switched off.
ADAPTIVE = Thinking(adaptive=True, can_disable=True)
# Adaptive or legacy extended thinking (budget_tokens).
ADAPTIVE_OR_MANUAL = Thinking(adaptive=True, manual=True, can_disable=True)
# Extended thinking only; "adaptive" returns 400.
MANUAL_ONLY = Thinking(manual=True, can_disable=True)

SAMPLING_PARAMS: tuple[Param, ...] = ("temperature", "top_p", "top_k")


def normalize_effort(value: Any) -> Effort:
    """Coerce a config value to a known effort level, defaulting to "none"."""
    effort = str(value).strip().lower() if value is not None else "none"
    return cast(Effort, effort) if effort in EFFORT_ORDER else "none"


@dataclass(frozen=True, slots=True)
class Model:
    """Capabilities of one model family."""

    name: str
    efforts: tuple[Effort, ...] = ()
    params: frozenset[Param] = frozenset()
    thinking: Thinking = Thinking()

    def __post_init__(self) -> None:
        if not set(self.efforts) <= set(EFFORT_ORDER):
            raise ValueError(f"{self.name}: unknown effort in {self.efforts}")
        if len(set(self.efforts)) != len(self.efforts):
            raise ValueError(f"{self.name}: duplicate effort in {self.efforts}")
        if not self.params <= frozenset(get_args(Param)):
            raise ValueError(f"{self.name}: unknown parameter in {self.params}")
        if self.efforts and not self.params & {
            "effort",
            "reasoning_effort",
            "thinking_level",
        }:
            raise ValueError(f"{self.name}: efforts declared without an effort param")
        if self.thinking != Thinking() and "thinking" not in self.params:
            raise ValueError(f"{self.name}: thinking declared without thinking param")

    def supports(self, param: Param) -> bool:
        """True when the API accepts the param as a request field."""
        return param in self.params

    def resolve_effort(self, requested: Any) -> Effort | None:
        """Highest effort the model supports that does not exceed requested."""
        if not self.efforts:
            return None
        ceiling = EFFORT_ORDER.index(normalize_effort(requested))
        for effort in reversed(EFFORT_ORDER[: ceiling + 1]):
            if effort in self.efforts:
                return effort
        return None


def _openai(name: str, efforts: tuple[Effort, ...], *, sampling: bool = True) -> Model:
    """Build an OpenAI-style entry: sampling params plus optional reasoning."""
    params: set[Param] = {"temperature", "top_p"} if sampling else set()
    if efforts:
        params.add("reasoning_effort")
    return Model(name=name, efforts=efforts, params=frozenset(params))


def _claude(
    name: str,
    efforts: tuple[Effort, ...],
    thinking: Thinking,
) -> Model:
    """Build claude entry

    Sampling parameters are left out on purpose: from API version 2026-10-21
    the Claude API rejects temperature, top_p, and top_k on every model.
    """
    params: set[Param] = {"thinking"}
    if efforts:
        params.add("effort")
    return Model(
        name=name, efforts=efforts, params=frozenset(params), thinking=thinking
    )


def _gemini(name: str, levels: tuple[Effort, ...], *, budget: bool = True) -> Model:
    """Build a Gemini entry: sampling params plus thinking controls.

    Gemini 3 and newer take ``thinkingLevel``; ``thinkingBudget`` still works on
    every model except Gemini 4, where it is deprecated and maps to the nearest
    level with a warning.
    """
    params: set[Param] = {"temperature", "top_p"}
    if levels:
        params.add("thinking_level")
    if budget:
        params.add("thinking_budget")
    return Model(name=name, efforts=levels, params=frozenset(params))


MODELS: dict[str, Model] = {
    model.name: model
    for model in (
        _openai("gpt-5", ("minimal", "low", "medium", "high"), sampling=False),
        _openai("gpt-5-mini", ("minimal", "low", "medium", "high"), sampling=False),
        _openai("gpt-5-nano", ("minimal", "low", "medium", "high"), sampling=False),
        _openai("gpt-6.1-terra", ("none", "low", "medium", "high", "xhigh", "max")),
        _openai("gpt-6.1-sol", ("low", "medium", "high", "xhigh", "max")),
        _openai("gpt-6-astra", ("low", "medium", "high", "xhigh", "max")),
        _openai("gpt-6-sol", ("none", "low", "medium", "high", "xhigh", "max")),
        _openai("gpt-6-luna", ("none", "low", "medium", "high", "xhigh", "max")),
        _openai("gpt-5.6", ("none", "low", "medium", "high", "xhigh", "max")),
        _openai("gpt-5.6-sol", ("none", "low", "medium", "high", "xhigh", "max")),
        _openai("gpt-5.6-terra", ("none", "low", "medium", "high", "xhigh", "max")),
        _openai("gpt-5.6-luna", ("none", "low", "medium", "high", "xhigh", "max")),
        _openai("gpt-5.5", ("none", "low", "medium", "high", "xhigh")),
        _openai("gpt-5.4-pro", ("medium", "high", "xhigh")),
        _openai("gpt-5.4-mini", ("none", "low", "medium", "high", "xhigh")),
        _openai("gpt-5.4-nano", ("none", "low", "medium", "high", "xhigh")),
        _openai("gpt-5.4", ("none", "low", "medium", "high", "xhigh")),
        _openai("gpt-5.2", ("none", "low", "medium", "high", "xhigh")),
        _openai("gpt-5.1", ("none", "low", "medium", "high")),
        _openai("gpt-5-pro", ("high",)),
        _claude(
            "claude-fable-5-2",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE_ALWAYS_NO_FORCED_TOOL,
        ),
        _claude(
            "claude-mythos-5-2",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE_ALWAYS_NO_FORCED_TOOL,
        ),
        _claude(
            "claude-fable-5-1",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE_ALWAYS_NO_FORCED_TOOL,
        ),
        _claude(
            "claude-mythos-5-1",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE_ALWAYS_NO_FORCED_TOOL,
        ),
        _claude(
            "claude-fable-5",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE_ALWAYS,
        ),
        _claude(
            "claude-mythos-5",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE_ALWAYS,
        ),
        _claude(
            "claude-mythos-preview",
            ("low", "medium", "high", "xhigh", "max"),
            Thinking(adaptive=True, manual=True),
        ),
        _claude(
            "claude-opus-5-5",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE_ALWAYS_NO_FORCED_TOOL,
        ),
        _claude(
            "claude-opus-5",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE,
        ),
        _claude(
            "claude-sonnet-5-5",
            ("low", "medium", "high", "xhigh", "max"),
            Thinking(adaptive=True, between_tools=True, forced_tool_choice=False),
        ),
        _claude(
            "claude-sonnet-5",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE,
        ),
        _claude(
            "claude-haiku-5-5",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE,
        ),
        _claude(
            "claude-opus-4-8",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE,
        ),
        _claude(
            "claude-opus-4-7",
            ("low", "medium", "high", "xhigh", "max"),
            ADAPTIVE,
        ),
        _claude(
            "claude-opus-4-6",
            ("low", "medium", "high", "max"),
            ADAPTIVE_OR_MANUAL,
        ),
        _claude(
            "claude-sonnet-4-6",
            ("low", "medium", "high", "max"),
            ADAPTIVE_OR_MANUAL,
        ),
        _claude(
            "claude-opus-4-5",
            ("low", "medium", "high"),
            MANUAL_ONLY,
        ),
        _claude("claude-sonnet-4-5", (), MANUAL_ONLY),
        _claude("claude-haiku-4-5", (), MANUAL_ONLY),
        _claude("claude-opus-4-1", (), MANUAL_ONLY),
        _claude("claude-sonnet-4", (), MANUAL_ONLY),
        _claude("claude-opus-4", (), MANUAL_ONLY),
        _claude("claude-3-7-sonnet", (), MANUAL_ONLY),
        _gemini("gemini-4-argon", ("low", "medium", "high"), budget=False),
        _gemini("gemini-3.8-flash", ("low", "medium", "high")),
        _gemini("gemini-3.6-flash", ("minimal", "low", "medium", "high")),
        _gemini("gemini-3.5-flash-lite", ("minimal", "low", "medium", "high")),
        _gemini("gemini-3.1-flash-lite", ("minimal", "low", "medium", "high")),
        _gemini("gemini-3.1-pro-preview", ("low", "medium", "high")),
        _gemini("gemini-3-flash-preview", ("minimal", "low", "medium", "high")),
        _gemini("gemini-2.5-pro", ()),
        _gemini("gemini-2.5-flash", ()),
        _gemini("gemini-2.5-flash-lite", ()),
    )
}

# Fallback for unknown models
UNKNOWN = Model(name="", params=frozenset({"temperature", "top_p"}))


def get(model: str) -> Model:
    """Resolve a model id to its registry entry."""
    lowered = (model or "").strip().lower()
    for name, entry in MODELS.items():
        if re.fullmatch(
            rf"(?:\w+\.)*{re.escape(name)}(?:-\d{{4}}-?\d{{2}}-?\d{{2}})?",
            lowered,
        ):
            return entry
    return UNKNOWN


def build_params(
    model: Model, params: dict[str, Any], *, strict: bool = False
) -> dict[str, Any]:
    """Keep only the parameters the model accepts."""
    accepted = {key: value for key, value in params.items() if key in model.params}
    if strict:
        rejected = sorted(set(params) - set(accepted))
        if rejected:
            raise ValueError(
                f"{model.name or 'unknown model'} does not accept {rejected}"
            )
    return accepted
