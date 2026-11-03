"""Unit tests for OpenAI Decisions API support."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.llmvision import (
    ServiceCallData,
    _apply_decision_entity_updates,
    _format_decision_answers_for_timeline,
    setup,
)
from custom_components.llmvision.const import (
    DEFAULT_DECISIONS_MODEL,
    DECISIONS_SUPPORTED_PROVIDERS,
    DOMAIN,
    ENDPOINT_OPENAI_DECISIONS,
    ERROR_DECISIONS_NOT_SUPPORTED,
)
from custom_components.llmvision.providers import (
    AzureOpenAI,
    Mistral,
    OpenAI,
    Request,
    normalize_decision_questions,
)
from tests.test_init import _base_service_data, _build_data_call, _make_hass


class TestNormalizeDecisionQuestions:
    def test_predicate_choice_and_score(self):
        questions = normalize_decision_questions(
            [
                {
                    "id": "silver_car",
                    "type": "predicate",
                    "instruction": "Is a silver car present?",
                },
                {
                    "name": "visitor",
                    "type": "choice",
                    "instructions": "Who is at the door?",
                    "options": ["Mailman", "Amazon", {"value": "UPS", "description": "UPS truck"}],
                },
                {
                    "id": "urgency",
                    "type": "score",
                    "instruction": "How urgent?",
                    "levels": ["low", {"label": "high", "description": "Immediate"}],
                },
            ]
        )

        assert questions[0] == {
            "type": "predicate",
            "instructions": "Is a silver car present?",
            "name": "silver_car",
        }
        assert questions[1]["choices"] == [
            {"value": "Mailman"},
            {"value": "Amazon"},
            {"value": "UPS", "description": "UPS truck"},
        ]
        assert questions[2]["levels"] == [
            {"label": "low"},
            {"label": "high", "description": "Immediate"},
        ]

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="type must be"):
            normalize_decision_questions(
                [{"type": "ranking", "instruction": "Rank this"}]
            )

    def test_choice_requires_two_options(self):
        with pytest.raises(ValueError, match="at least 2"):
            normalize_decision_questions(
                [
                    {
                        "type": "choice",
                        "instruction": "Pick one",
                        "options": ["only-one"],
                    }
                ]
            )


class TestOpenAIDecisions:
    def test_supports_decisions(self, mock_hass):
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "test_api_key", DEFAULT_DECISIONS_MODEL)
            mistral = Mistral(mock_hass, "test_api_key", "pixtral-12b-2409")

            assert openai.supports_decisions() is True
            assert mistral.supports_decisions() is False

    def test_get_decisions_url_variants(self, mock_hass):
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            official = OpenAI(mock_hass, "key", DEFAULT_DECISIONS_MODEL)
            custom_v1 = OpenAI(
                mock_hass,
                "key",
                DEFAULT_DECISIONS_MODEL,
                endpoint={"base_url": "https://example.test/v1/"},
            )
            custom_chat = OpenAI(
                mock_hass,
                "key",
                DEFAULT_DECISIONS_MODEL,
                endpoint={"base_url": "https://example.test/v1/chat/completions"},
            )

            assert official._get_decisions_url() == ENDPOINT_OPENAI_DECISIONS
            assert custom_v1._get_decisions_url() == "https://example.test/v1/decisions"
            assert (
                custom_chat._get_decisions_url() == "https://example.test/v1/decisions"
            )

    def test_prepare_decision_data(self, mock_hass):
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "key", DEFAULT_DECISIONS_MODEL)
            call = SimpleNamespace(
                message="Driveway snapshot",
                base64_images=["abc123"],
                filenames=["driveway.jpg"],
                include_filename=True,
                decision_questions=[
                    {
                        "type": "predicate",
                        "name": "silver_car",
                        "instructions": "Is a silver car present?",
                    }
                ],
            )

            payload = openai._prepare_decision_data(call)

            assert payload["model"] == DEFAULT_DECISIONS_MODEL
            assert payload["questions"][0]["type"] == "predicate"
            content = payload["input"][0]["content"]
            assert content[0] == {
                "type": "input_text",
                "text": "Driveway snapshot",
            }
            assert content[1] == {"type": "input_text", "text": "driveway.jpg:"}
            assert content[2]["type"] == "input_image"
            assert content[2]["image_url"].startswith("data:image/jpeg;base64,")

    @pytest.mark.anyio
    async def test_decision_request_posts_to_decisions_endpoint(self, mock_hass):
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            openai = OpenAI(mock_hass, "key", DEFAULT_DECISIONS_MODEL)
            call = SimpleNamespace(
                message="",
                base64_images=["img"],
                filenames=[""],
                include_filename=False,
                decision_questions=[
                    {
                        "type": "predicate",
                        "name": "present",
                        "instructions": "Is anyone present?",
                    }
                ],
            )
            api_response = {
                "model": DEFAULT_DECISIONS_MODEL,
                "answers": [
                    {"type": "predicate", "name": "present", "probability": 0.91}
                ],
                "usage": {"input_tokens": 12, "output_tokens": 0, "total_tokens": 12},
            }

            with patch.object(
                openai, "_post", new=AsyncMock(return_value=api_response)
            ) as post_mock:
                result = await openai.decision_request(call)

            assert result == api_response
            assert post_mock.await_args.kwargs["url"] == ENDPOINT_OPENAI_DECISIONS
            assert (
                post_mock.await_args.kwargs["headers"]["Authorization"]
                == "Bearer key"
            )
            posted = post_mock.await_args.kwargs["data"]
            assert posted["model"] == DEFAULT_DECISIONS_MODEL
            assert posted["questions"][0]["name"] == "present"


class TestAzureDecisions:
    def test_get_decisions_url_and_request(self, mock_hass):
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            azure = AzureOpenAI(
                mock_hass,
                "azure-key",
                DEFAULT_DECISIONS_MODEL,
                endpoint={
                    "base_url": "unused",
                    "endpoint": "https://example.openai.azure.com",
                    "deployment": "gpt-6-luna",
                    "api_version": "2025-04-01-preview",
                },
            )

            assert (
                azure._get_decisions_url()
                == "https://example.openai.azure.com/openai/v1/decisions"
            )
            assert azure.supports_decisions() is True

    @pytest.mark.anyio
    async def test_decision_request_uses_api_key_header(self, mock_hass):
        with patch("custom_components.llmvision.providers.async_get_clientsession"):
            azure = AzureOpenAI(
                mock_hass,
                "azure-key",
                DEFAULT_DECISIONS_MODEL,
                endpoint={
                    "base_url": "unused",
                    "endpoint": "https://example.openai.azure.com/",
                    "deployment": "gpt-6-luna",
                    "api_version": "2025-04-01-preview",
                },
            )
            call = SimpleNamespace(
                message="context",
                base64_images=["img"],
                filenames=[""],
                include_filename=False,
                decision_questions=[
                    {
                        "type": "choice",
                        "name": "visitor",
                        "instructions": "Who is there?",
                        "choices": [{"value": "Person"}, {"value": "No person"}],
                    }
                ],
            )
            api_response = {
                "model": DEFAULT_DECISIONS_MODEL,
                "answers": [
                    {
                        "type": "choice",
                        "name": "visitor",
                        "choice": "Person",
                        "confidence": 0.8,
                        "probabilities": [
                            {"value": "Person", "probability": 0.8},
                            {"value": "No person", "probability": 0.2},
                        ],
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 0, "total_tokens": 20},
            }

            with patch.object(
                azure, "_post", new=AsyncMock(return_value=api_response)
            ) as post_mock:
                result = await azure.decision_request(call)

            assert result["answers"][0]["choice"] == "Person"
            assert post_mock.await_args.kwargs["headers"]["api-key"] == "azure-key"
            assert post_mock.await_args.kwargs["url"].endswith("/openai/v1/decisions")


class TestRequestDecisionCall:
    @pytest.mark.anyio
    async def test_decision_call_success(self, mock_hass):
        mock_hass.data = {
            DOMAIN: {
                "entry_openai": {
                    "provider": "OpenAI",
                    "api_key": "sk-test",
                }
            }
        }
        with patch(
            "custom_components.llmvision.providers.async_get_clientsession"
        ):
            request = Request(mock_hass, "context", 1000, 0.5)
            request.base64_images = ["img"]
            request.filenames = [""]
            call = SimpleNamespace(
                provider="entry_openai",
                model=None,
                message="context",
                include_filename=False,
                questions=[
                    {
                        "id": "present",
                        "type": "predicate",
                        "instruction": "Is a person present?",
                    }
                ],
            )
            api_response = {
                "model": DEFAULT_DECISIONS_MODEL,
                "answers": [
                    {"type": "predicate", "name": "present", "probability": 0.42}
                ],
                "usage": {"input_tokens": 8, "output_tokens": 0, "total_tokens": 8},
            }

            with patch.object(
                OpenAI, "decision_request", new=AsyncMock(return_value=api_response)
            ):
                result = await request.decision_call(call)

            assert result == api_response
            assert call.model == DEFAULT_DECISIONS_MODEL
            assert call.decision_questions[0]["name"] == "present"

    @pytest.mark.anyio
    async def test_decision_call_rejects_unsupported_provider(self, mock_hass):
        mock_hass.data = {
            DOMAIN: {
                "entry_anthropic": {
                    "provider": "Anthropic",
                    "api_key": "key",
                }
            }
        }
        with patch(
            "custom_components.llmvision.providers.async_get_clientsession"
        ):
            request = Request(mock_hass, "", 1000, 0.5)
            request.base64_images = ["img"]
            request.filenames = [""]
            call = SimpleNamespace(
                provider="entry_anthropic",
                model=DEFAULT_DECISIONS_MODEL,
                message="",
                include_filename=False,
                questions=[
                    {
                        "type": "predicate",
                        "instruction": "Is a person present?",
                    }
                ],
            )

            with pytest.raises(ServiceValidationError, match="only supported"):
                await request.decision_call(call)

    def test_supported_providers_constant(self):
        assert DECISIONS_SUPPORTED_PROVIDERS == {
            "OpenAI",
            "Custom OpenAI",
            "Azure",
        }


class TestDecisionHelpers:
    def test_format_decision_answers_for_timeline(self):
        title, description = _format_decision_answers_for_timeline(
            [
                {"type": "predicate", "name": "silver_car", "probability": 0.9},
                {"type": "choice", "name": "visitor", "choice": "Amazon"},
                {"type": "refusal", "name": "blocked"},
            ]
        )
        assert "silver_car" in title
        assert "visitor: Amazon" in description
        assert "blocked: refused" in description

    @pytest.mark.anyio
    async def test_apply_decision_entity_updates_predicate_and_choice(self):
        hass = _make_hass()
        hass.states.get.side_effect = lambda entity_id: SimpleNamespace(
            state="off",
            attributes={"options": ["Mailman", "Amazon", "UPS", "FedEx", "Person", "No person"]},
        )

        with patch(
            "custom_components.llmvision._update_sensor", new=AsyncMock()
        ) as update_mock:
            updates = await _apply_decision_entity_updates(
                hass,
                [
                    {
                        "id": "silver_car",
                        "type": "predicate",
                        "threshold": 0.7,
                        "entity": "input_boolean.silver_car_present",
                    },
                    {
                        "id": "visitor",
                        "type": "choice",
                        "entity": "input_select.front_door_visitor",
                    },
                ],
                [
                    {"type": "predicate", "name": "silver_car", "probability": 0.81},
                    {
                        "type": "choice",
                        "name": "visitor",
                        "choice": "Amazon",
                        "confidence": 0.77,
                    },
                ],
            )

        assert updates[0]["updated"] is True
        assert updates[0]["value"] == "on"
        assert updates[1]["value"] == "Amazon"
        assert update_mock.await_count == 2


class TestDecisionAnalyzerService:
    def _registered_handlers(self, hass):
        handlers = {}
        for call in hass.services.register.call_args_list:
            _, service_name, handler = call.args[:3]
            handlers[service_name] = handler
        return handlers

    @pytest.mark.anyio
    async def test_decision_analyzer_success(self):
        hass = _make_hass()
        assert setup(hass, {}) is True
        handler = self._registered_handlers(hass)["decision_analyzer"]

        call_obj = ServiceCallData(
            _build_data_call(
                _base_service_data(
                    message="Front door",
                    questions=[
                        {
                            "id": "visitor",
                            "type": "choice",
                            "instruction": "Who is at the front door?",
                            "options": [
                                "Mailman",
                                "Amazon",
                                "UPS",
                                "FedEx",
                                "Person",
                                "No person",
                            ],
                        }
                    ],
                )
            )
        )
        request_obj = Mock()
        request_obj.decision_call = AsyncMock(
            return_value={
                "model": DEFAULT_DECISIONS_MODEL,
                "answers": [
                    {
                        "type": "choice",
                        "name": "visitor",
                        "choice": "FedEx",
                        "confidence": 0.88,
                        "probabilities": [],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 0, "total_tokens": 10},
            }
        )
        processor = Mock()
        processor.key_frame = "frame.jpg"
        processor.add_images = AsyncMock(return_value=request_obj)

        with (
            patch("custom_components.llmvision.ServiceCallData", return_value=call_obj),
            patch("custom_components.llmvision.Request", return_value=request_obj),
            patch("custom_components.llmvision.MediaProcessor", return_value=processor),
            patch("custom_components.llmvision._create_event", new=AsyncMock()),
            patch(
                "custom_components.llmvision._apply_decision_entity_updates",
                new=AsyncMock(return_value=[]),
            ),
        ):
            result = await handler(
                _build_data_call(
                    _base_service_data(
                        questions=[
                            {
                                "id": "visitor",
                                "type": "choice",
                                "instruction": "Who is at the front door?",
                                "options": ["Mailman", "Amazon"],
                            }
                        ]
                    )
                )
            )

        assert result["answers"][0]["choice"] == "FedEx"
        assert result["key_frame"] == "frame.jpg"
        assert "response_time_ms" in result
        assert result["model"] == DEFAULT_DECISIONS_MODEL
        request_obj.decision_call.assert_awaited_once()

    @pytest.mark.anyio
    async def test_decision_analyzer_surfaces_provider_error(self):
        hass = _make_hass()
        assert setup(hass, {}) is True
        handler = self._registered_handlers(hass)["decision_analyzer"]

        call_obj = ServiceCallData(
            _build_data_call(
                _base_service_data(
                    questions=[
                        {
                            "type": "predicate",
                            "instruction": "Is a silver car present?",
                        }
                    ]
                )
            )
        )
        request_obj = Mock()
        request_obj.decision_call = AsyncMock(
            side_effect=ServiceValidationError(ERROR_DECISIONS_NOT_SUPPORTED)
        )
        processor = Mock()
        processor.key_frame = ""
        processor.add_images = AsyncMock(return_value=request_obj)

        with (
            patch("custom_components.llmvision.ServiceCallData", return_value=call_obj),
            patch("custom_components.llmvision.Request", return_value=request_obj),
            patch("custom_components.llmvision.MediaProcessor", return_value=processor),
        ):
            with pytest.raises(ServiceValidationError, match="only supported"):
                await handler(
                    _build_data_call(
                        _base_service_data(
                            questions=[
                                {
                                    "type": "predicate",
                                    "instruction": "Is a silver car present?",
                                }
                            ]
                        )
                    )
                )
