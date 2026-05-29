"""Comprehensive unit tests for custom_components.llmvision.__init__.py."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.exceptions import ServiceValidationError

import custom_components.llmvision as init_module
from custom_components.llmvision import (
    ServiceCallData,
    _create_event,
    _update_sensor,
    async_migrate_entry,
    async_remove_entry,
    async_setup_entry,
    async_unload_entry,
    setup,
)
from custom_components.llmvision.const import (
    CONF_API_KEY,
    CONF_DEFAULT_MODEL,
    CONF_PROVIDER,
    CONF_RETENTION_TIME,
    DOMAIN,
)


def _build_data_call(data: dict) -> Mock:
    data_call = Mock()
    data_call.data = Mock()
    data_call.data.get = Mock(
        side_effect=lambda key, default=None: data.get(key, default)
    )
    return data_call


def _base_service_data(**overrides) -> dict:
    now = datetime.datetime.now()
    base = {
        "provider": "entry_id",
        "model": "test-model",
        "message": "message",
        "store_in_timeline": False,
        "use_memory": False,
        "image_file": None,
        "image_entity": [],
        "video_file": None,
        "event_id": None,
        "interval": 2,
        "duration": 10,
        "max_frames": 3,
        "target_width": 1920,
        "max_tokens": 1000,
        "include_filename": False,
        "expose_images": False,
        "generate_title": False,
        "sensor_entity": "",
        "response_format": "text",
        "structure": None,
        "title_field": "",
        "description_field": "",
        "title": "Title",
        "description": "Description",
        "start_time": now,
        "end_time": now + datetime.timedelta(minutes=1),
        "image_path": "",
        "camera_entity": "",
        "label": "Label",
        "start": now - datetime.timedelta(days=1),
        "end": now,
        "cameras": [],
        "categories": [],
        "labels": [],
        "limit": 100,
        "include_no_activity": True,
    }
    base.update(overrides)
    return base


def _make_hass() -> Mock:
    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.config.path = Mock(return_value="/tmp")
    hass.config_entries = Mock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_update_entry = Mock()
    hass.config_entries.async_entries = Mock(return_value=[])
    hass.config_entries.async_remove = Mock(return_value="scheduled-remove")
    hass.async_create_task = Mock()
    hass.services = Mock()
    hass.services.register = Mock()
    hass.http = Mock()
    hass.http.register_view = Mock()
    hass.states = Mock()
    hass.states.async_set = Mock()
    return hass


@dataclass
class _DummyCall:
    store_in_timeline: bool = True
    image_entities: list[str] | None = None
    video_paths: list[str] | None = None
    response_format: str = "text"
    description_field: str = ""

    def get(self, key, default=None):
        return getattr(self, key, default)


class TestServiceCallData:
    def test_initialization_and_accessors(self):
        data = _base_service_data(model="glimpse-v1-fast")
        data_call = _build_data_call(data)

        call = ServiceCallData(data_call)

        assert call.provider == "entry_id"
        assert call.model == "glimpse-v1-fast"
        assert call.model_is_glimpse() is True
        assert call.get("max_tokens") == 1000
        assert call.get("missing", "fallback") == "fallback"
        assert call.get_service_call_data() is call

    def test_initialization_with_image_video_and_event_ids(self):
        data = _base_service_data(
            image_file="a.jpg\nb.jpg",
            video_file="a.mp4\nb.mp4",
            event_id="id1\nid2",
        )
        call = ServiceCallData(_build_data_call(data))

        assert call.image_paths == ["a.jpg", "b.jpg"]
        assert call.video_paths == ["a.mp4", "b.mp4"]
        assert call.event_id == ["id1", "id2"]

    @pytest.mark.parametrize(
        "value", [1704110400, 1704110400.0, "1704110400", "2024-01-01T12:00:00"]
    )
    def test_convert_time_supported_values(self, value):
        call = ServiceCallData(_build_data_call(_base_service_data()))
        result = call._convert_time_input_to_datetime(value)
        assert isinstance(result, datetime.datetime)

    def test_convert_time_invalid_raises(self):
        call = ServiceCallData(_build_data_call(_base_service_data()))
        with pytest.raises(ValueError):
            call._convert_time_input_to_datetime("not-a-date")
        with pytest.raises(TypeError):
            call._convert_time_input_to_datetime(object())


class TestEntryLifecycle:
    @pytest.mark.anyio
    async def test_async_setup_entry_filters_and_stores(self):
        hass = _make_hass()
        entry = Mock()
        entry.entry_id = "entry1"
        entry.title = "OpenAI"
        entry.data = {
            "provider": "OpenAI",
            "api_key": "key",
            "default_model": None,
            "temperature": 0.7,
        }

        ok = await async_setup_entry(hass, entry)

        assert ok is True
        assert hass.data[DOMAIN]["entry1"]["provider"] == "OpenAI"
        assert "default_model" not in hass.data[DOMAIN]["entry1"]
        assert hass.data[DOMAIN]["entry1"]["temperature"] == 0.7

    @pytest.mark.anyio
    async def test_async_setup_entry_settings_forwards_calendar_and_cleanup(self):
        hass = _make_hass()
        entry = Mock()
        entry.entry_id = "settings"
        entry.title = "Settings"
        entry.data = {"provider": "Settings", "retention_time": 7}
        timeline_instance = Mock()
        timeline_instance._cleanup = AsyncMock()

        with patch(
            "custom_components.llmvision.Timeline", return_value=timeline_instance
        ):
            ok = await async_setup_entry(hass, entry)

        assert ok is True
        hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
            entry, ["calendar"]
        )
        timeline_instance._cleanup.assert_awaited_once()

    @pytest.mark.anyio
    async def test_async_remove_entry_non_settings(self):
        hass = _make_hass()
        hass.data = {DOMAIN: {"entry1": {"provider": "OpenAI"}}}
        entry = Mock()
        entry.entry_id = "entry1"
        entry.title = "OpenAI"
        entry.data = {"provider": "OpenAI"}

        with patch(
            "custom_components.llmvision.async_unload_entry",
            new=AsyncMock(return_value=True),
        ):
            ok = await async_remove_entry(hass, entry)

        assert ok is True
        assert "entry1" not in hass.data[DOMAIN]

    @pytest.mark.anyio
    async def test_async_remove_entry_settings_deletes_db(self):
        hass = _make_hass()
        hass.data = {DOMAIN: {"entry1": {"provider": "Settings"}}}
        entry = Mock()
        entry.entry_id = "entry1"
        entry.title = "Settings"
        entry.data = {"provider": "Settings"}

        with (
            patch(
                "custom_components.llmvision.async_unload_entry",
                new=AsyncMock(return_value=True),
            ),
            patch("custom_components.llmvision.os.path.exists", return_value=True),
            patch("custom_components.llmvision.os.remove") as remove_mock,
        ):
            ok = await async_remove_entry(hass, entry)

        assert ok is True
        remove_mock.assert_called_once()

    @pytest.mark.anyio
    async def test_async_remove_entry_missing_is_noop(self):
        hass = _make_hass()
        hass.data = {}
        entry = Mock()
        entry.entry_id = "missing"
        entry.title = "Missing"
        entry.data = {"provider": "OpenAI"}

        ok = await async_remove_entry(hass, entry)

        assert ok is True

    @pytest.mark.anyio
    async def test_async_unload_entry_with_and_without_calendar(self):
        hass = _make_hass()

        with_calendar = Mock(title="settings")
        with_calendar.data = {"retention_time": 7}
        without_calendar = Mock(title="provider")
        without_calendar.data = {"provider": "OpenAI"}

        assert await async_unload_entry(hass, with_calendar) is True
        assert await async_unload_entry(hass, without_calendar) is True
        hass.config_entries.async_unload_platforms.assert_awaited_once_with(
            with_calendar, ["calendar"]
        )


class TestMigration:
    @pytest.mark.anyio
    async def test_v2_event_calendar_renamed_to_timeline(self):
        hass = _make_hass()
        config_entry = Mock()
        config_entry.title = "Event Calendar"
        config_entry.version = 2
        config_entry.minor_version = 0
        config_entry.data = {"provider": "Event Calendar"}

        ok = await async_migrate_entry(hass, config_entry)

        assert ok is True
        hass.config_entries.async_update_entry.assert_called_once()
        _, kwargs = hass.config_entries.async_update_entry.call_args
        assert kwargs["title"] == "LLM Vision Timeline"
        assert kwargs["data"]["provider"] == "Timeline"
        assert kwargs["version"] == 3

    @pytest.mark.anyio
    async def test_v3_timeline_merges_into_memory_and_schedules_remove(self):
        hass = _make_hass()
        memory_entry = Mock()
        memory_entry.data = {"provider": "Memory"}
        hass.config_entries.async_entries.return_value = [memory_entry]

        config_entry = Mock()
        config_entry.title = "Timeline"
        config_entry.entry_id = "timeline-entry"
        config_entry.version = 3
        config_entry.minor_version = 0
        config_entry.data = {"provider": "Timeline", "retention_time": 5}

        ok = await async_migrate_entry(hass, config_entry)

        assert ok is True
        hass.config_entries.async_update_entry.assert_called_once()
        (updated_entry,) = hass.config_entries.async_update_entry.call_args.args
        assert updated_entry is memory_entry
        assert hass.async_create_task.called

    @pytest.mark.anyio
    async def test_v3_memory_becomes_settings(self):
        hass = _make_hass()
        config_entry = Mock()
        config_entry.title = "Memory"
        config_entry.version = 3
        config_entry.minor_version = 0
        config_entry.data = {"provider": "Memory"}

        ok = await async_migrate_entry(hass, config_entry)

        assert ok is True
        hass.config_entries.async_update_entry.assert_called_once()
        _, kwargs = hass.config_entries.async_update_entry.call_args
        assert kwargs["title"] == "LLM Vision Settings"
        assert kwargs["data"]["provider"] == "Settings"
        assert kwargs["version"] == 4

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        ("provider", "legacy", "expected_key", "extra"),
        [
            ("OpenAI", "openai_api_key", CONF_API_KEY, {}),
            ("Anthropic", "anthropic_api_key", CONF_API_KEY, {}),
            (
                "Azure",
                "azure_api_key",
                CONF_API_KEY,
                {
                    "azure_base_url": "https://x",
                    "azure_deployment": "dep",
                    "azure_version": "2024",
                },
            ),
            ("Groq", "groq_api_key", CONF_API_KEY, {}),
            ("Google", "google_api_key", CONF_API_KEY, {}),
            (
                "LocalAI",
                "localai_api_key",
                CONF_API_KEY,
                {
                    "localai_ip_address": "127.0.0.1",
                    "localai_port": 8080,
                    "localai_https": False,
                },
            ),
            (
                "Ollama",
                "ollama_api_key",
                CONF_API_KEY,
                {
                    "ollama_ip_address": "127.0.0.1",
                    "ollama_port": 11434,
                    "ollama_https": False,
                },
            ),
            (
                "Custom OpenAI",
                "custom_openai_api_key",
                CONF_API_KEY,
                {"custom_openai_endpoint": "http://localhost"},
            ),
            (
                "AWS",
                "aws_access_key_id",
                "aws_access_key_id",
                {"aws_secret_access_key": "secret", "aws_region_name": "eu-west-1"},
            ),
            (
                "OpenWebUI",
                "openwebui_api_key",
                CONF_API_KEY,
                {
                    "openwebui_ip_address": "127.0.0.1",
                    "openwebui_port": 3000,
                    "openwebui_https": False,
                },
            ),
        ],
    )
    async def test_v3_provider_key_migrations(
        self, provider, legacy, expected_key, extra
    ):
        hass = _make_hass()
        data = {"provider": provider, legacy: "legacy-value"}
        data.update(extra)

        config_entry = Mock()
        config_entry.title = provider
        config_entry.version = 3
        config_entry.minor_version = 0
        config_entry.data = data

        ok = await async_migrate_entry(hass, config_entry)

        assert ok is True
        assert hass.config_entries.async_update_entry.called
        _, kwargs = hass.config_entries.async_update_entry.call_args
        assert kwargs["version"] == 4
        assert expected_key in kwargs["data"]
        assert CONF_DEFAULT_MODEL in kwargs["data"]
        assert kwargs["data"]["temperature"] == 0.5
        if provider == "OpenAI":
            assert "top_p" not in kwargs["data"]
        else:
            assert kwargs["data"]["top_p"] == 0.9


class TestCreateEventAndUpdateSensor:
    @pytest.mark.anyio
    async def test_create_event_no_store_in_timeline_noop(self):
        hass = _make_hass()
        call = _DummyCall(store_in_timeline=False)

        await _create_event(
            hass, call, datetime.datetime.now(), {"response_text": "x"}, ""
        )

    @pytest.mark.anyio
    async def test_create_event_requires_settings_entry(self):
        hass = _make_hass()
        call = _DummyCall(store_in_timeline=True)

        with pytest.raises(ServiceValidationError):
            await _create_event(
                hass, call, datetime.datetime.now(), {"response_text": "x"}, ""
            )

    @pytest.mark.anyio
    async def test_create_event_uses_structured_description_and_camera(self):
        hass = _make_hass()
        settings = Mock()
        settings.data = {"provider": "Settings"}
        hass.config_entries.async_entries.return_value = [settings]

        timeline = Mock()
        timeline.create_event = AsyncMock()
        call = _DummyCall(
            store_in_timeline=True,
            image_entities=["camera.front"],
            response_format="json",
            description_field="summary",
        )
        response = {
            "response_text": "fallback",
            "structured_response": {"summary": "from json"},
        }

        with patch("custom_components.llmvision.Timeline", return_value=timeline):
            await _create_event(
                hass, call, datetime.datetime.now(), response, "frame.jpg"
            )

        timeline.create_event.assert_awaited_once()
        kwargs = timeline.create_event.await_args.kwargs
        assert kwargs["description"] == "from json"
        assert kwargs["camera_name"] == "camera.front"
        assert kwargs["title"] == "Motion detected"

    @pytest.mark.anyio
    async def test_update_sensor_boolean_and_number_and_text(self):
        hass = _make_hass()
        hass.states.get.return_value = SimpleNamespace(
            attributes={"options": ["Open", "Closed"]}
        )

        await _update_sensor(hass, "input_boolean.test", "true", "boolean")
        await _update_sensor(hass, "input_number.test", "12.5", "number")
        await _update_sensor(hass, "input_text.test", "abc", "text")
        await _update_sensor(hass, "input_select.test", "open", "option")

        assert hass.states.async_set.call_count == 4

    @pytest.mark.anyio
    async def test_update_sensor_invalid_and_error_paths(self):
        hass = _make_hass()
        hass.states.get.return_value = SimpleNamespace(
            attributes={"options": ["Open", "Closed"]}
        )

        with pytest.raises(ServiceValidationError):
            await _update_sensor(hass, "binary_sensor.test", "maybe", "boolean")
        with pytest.raises(ServiceValidationError):
            await _update_sensor(hass, "input_number.test", "not-number", "number")
        with pytest.raises(ServiceValidationError):
            await _update_sensor(hass, "input_select.test", "other", "option")
        with pytest.raises(ServiceValidationError):
            await _update_sensor(hass, "input_text.test", "a", "unsupported")

        hass.states.async_set.side_effect = RuntimeError("set failed")
        with pytest.raises(RuntimeError):
            await _update_sensor(hass, "input_text.test", "x", "text")


class TestSetupServices:
    def _registered_handlers(self, hass):
        handlers = {}
        for call in hass.services.register.call_args_list:
            _, service_name, handler = call.args[:3]
            handlers[service_name] = handler
        return handlers

    @pytest.mark.anyio
    async def test_image_video_stream_handlers(self):
        hass = _make_hass()
        assert setup(hass, {}) is True
        handlers = self._registered_handlers(hass)

        call_obj = ServiceCallData(_build_data_call(_base_service_data(message="msg")))
        response_obj = {"response_text": "ok"}
        request_obj = Mock()
        request_obj.call = AsyncMock(return_value=response_obj)
        memory_obj = Mock()
        memory_obj._update_memory = AsyncMock()
        processor = Mock()
        processor.key_frame = "frame.jpg"
        processor.add_images = AsyncMock(return_value=request_obj)
        processor.add_videos = AsyncMock(return_value=request_obj)
        processor.add_streams = AsyncMock(return_value=request_obj)

        with (
            patch("custom_components.llmvision.ServiceCallData", return_value=call_obj),
            patch("custom_components.llmvision.Request", return_value=request_obj),
            patch("custom_components.llmvision.MediaProcessor", return_value=processor),
            patch("custom_components.llmvision.Memory", return_value=memory_obj),
            patch(
                "custom_components.llmvision._create_event", new=AsyncMock()
            ) as create_event_mock,
        ):
            image_result = await handlers["image_analyzer"](
                _build_data_call(_base_service_data())
            )
            video_result = await handlers["video_analyzer"](
                _build_data_call(_base_service_data())
            )
            stream_result = await handlers["stream_analyzer"](
                _build_data_call(_base_service_data())
            )

        assert image_result["key_frame"] == "frame.jpg"
        assert video_result["key_frame"] == "frame.jpg"
        assert stream_result["key_frame"] == "frame.jpg"
        assert create_event_mock.await_count == 3

    @pytest.mark.anyio
    async def test_data_analyzer_boolean_and_number_and_text_and_option(self):
        hass = _make_hass()
        assert setup(hass, {}) is True
        handlers = self._registered_handlers(hass)
        data_handler = handlers["data_analyzer"]

        request_obj = Mock()
        request_obj.call = AsyncMock(return_value={"response_text": "on"})
        memory_obj = Mock()
        memory_obj._update_memory = AsyncMock()
        processor = Mock()
        processor.key_frame = ""
        processor.add_visual_data = AsyncMock(return_value=request_obj)
        call_obj = ServiceCallData(
            _build_data_call(_base_service_data(message="status"))
        )

        with (
            patch("custom_components.llmvision.ServiceCallData", return_value=call_obj),
            patch("custom_components.llmvision.Request", return_value=request_obj),
            patch("custom_components.llmvision.MediaProcessor", return_value=processor),
            patch("custom_components.llmvision.Memory", return_value=memory_obj),
            patch("custom_components.llmvision._create_event", new=AsyncMock()),
            patch(
                "custom_components.llmvision._update_sensor", new=AsyncMock()
            ) as update_sensor_mock,
        ):
            hass.states.get.return_value = SimpleNamespace(
                state="on", attributes={"options": ["Open", "Closed"]}
            )
            await data_handler(
                _build_data_call(
                    _base_service_data(sensor_entity="input_boolean.kitchen")
                )
            )

            request_obj.call.return_value = {"response_text": "2.0"}
            hass.states.get.return_value = SimpleNamespace(
                state="1", attributes={"options": ["Open", "Closed"]}
            )
            await data_handler(
                _build_data_call(_base_service_data(sensor_entity="sensor.temp"))
            )

            request_obj.call.return_value = {"response_text": "Open"}
            hass.states.get.return_value = SimpleNamespace(
                state="Open", attributes={"options": ["Open", "Closed"]}
            )
            await data_handler(
                _build_data_call(_base_service_data(sensor_entity="select.door"))
            )

            request_obj.call.return_value = {"response_text": "hello"}
            hass.states.get.return_value = SimpleNamespace(
                state="hello", attributes={"options": ["Open", "Closed"]}
            )
            await data_handler(
                _build_data_call(_base_service_data(sensor_entity="text.status"))
            )

        assert update_sensor_mock.await_count == 4

    @pytest.mark.anyio
    async def test_data_analyzer_unsupported_and_unavailable_raise(self):
        hass = _make_hass()
        assert setup(hass, {}) is True
        handlers = self._registered_handlers(hass)
        data_handler = handlers["data_analyzer"]

        call_obj = ServiceCallData(_build_data_call(_base_service_data()))
        request_obj = Mock()
        request_obj.call = AsyncMock(return_value={"response_text": "x"})
        processor = Mock()
        processor.add_visual_data = AsyncMock(return_value=request_obj)
        memory_obj = Mock()
        memory_obj._update_memory = AsyncMock()

        with (
            patch("custom_components.llmvision.ServiceCallData", return_value=call_obj),
            patch("custom_components.llmvision.Request", return_value=request_obj),
            patch("custom_components.llmvision.MediaProcessor", return_value=processor),
            patch("custom_components.llmvision.Memory", return_value=memory_obj),
        ):
            hass.states.get.return_value = SimpleNamespace(
                state="unavailable", attributes={"options": []}
            )
            with pytest.raises(ServiceValidationError):
                await data_handler(
                    _build_data_call(_base_service_data(sensor_entity="sensor.a"))
                )

            hass.states.get.return_value = SimpleNamespace(
                state="ok", attributes={"options": []}
            )
            with pytest.raises(ServiceValidationError):
                await data_handler(
                    _build_data_call(_base_service_data(sensor_entity="climate.a"))
                )

    @pytest.mark.anyio
    async def test_create_event_and_get_events_handlers(self):
        hass = _make_hass()
        assert setup(hass, {}) is True
        handlers = self._registered_handlers(hass)

        settings = Mock()
        settings.data = {"provider": "Settings"}
        hass.config_entries.async_entries.return_value = [settings]
        timeline = Mock()
        timeline.create_event = AsyncMock()
        timeline.get_events_json = AsyncMock(return_value=[{"id": 1}])

        call_obj = ServiceCallData(
            _build_data_call(_base_service_data(camera_entity="cam.one", label="Alert"))
        )

        with (
            patch("custom_components.llmvision.ServiceCallData", return_value=call_obj),
            patch("custom_components.llmvision.Timeline", return_value=timeline),
        ):
            await handlers["create_event"](_build_data_call(_base_service_data()))
            result = await handlers["get_events"](
                _build_data_call(
                    {
                        "start": datetime.datetime.now() - datetime.timedelta(days=1),
                        "end": datetime.datetime.now(),
                        "cameras": ["CAM.ONE"],
                        "categories": ["MOTION"],
                        "labels": ["PERSON"],
                        "limit": 5,
                        "include_no_activity": False,
                    }
                )
            )

        timeline.create_event.assert_awaited_once()
        timeline.get_events_json.assert_awaited_once()
        assert result == {"events": [{"id": 1}]}

    @pytest.mark.anyio
    async def test_create_event_and_get_events_missing_settings_raise(self):
        hass = _make_hass()
        assert setup(hass, {}) is True
        handlers = self._registered_handlers(hass)

        with pytest.raises(ServiceValidationError):
            await handlers["create_event"](_build_data_call(_base_service_data()))

        with pytest.raises(ServiceValidationError):
            await handlers["get_events"](_build_data_call({}))

    def test_setup_registers_views_and_services(self):
        hass = _make_hass()

        ok = setup(hass, {})

        assert ok is True
        assert hass.services.register.call_count == 6
        hass.http.register_view.assert_any_call(init_module.TimelineEventsView)
        hass.http.register_view.assert_any_call(init_module.TimelineEventView)
        hass.http.register_view.assert_any_call(init_module.TimelineEventCreateView)
