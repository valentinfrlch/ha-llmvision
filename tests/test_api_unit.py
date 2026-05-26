"""Unit tests for api.py timeline views."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest

from custom_components.llmvision.api import (
    TimelineEventCreateView,
    TimelineEventsView,
    TimelineEventView,
    async_get_settings_entry,
)


pytestmark = pytest.mark.unit


def _make_request(hass, query=None, json_body=None, json_exception=None):
    request = Mock()
    request.app = {"hass": hass}
    request.query = query or {}
    request.json = AsyncMock()
    if json_exception is not None:
        request.json.side_effect = json_exception
    else:
        request.json.return_value = json_body or {}
    return request


def _response_payload(response):
    return json.loads(response.text)


class TestAsyncGetSettingsEntry:
    """Tests for async_get_settings_entry."""

    @pytest.mark.asyncio
    async def test_returns_settings_entry(self, mock_hass):
        settings_entry = Mock()
        settings_entry.data = {"provider": "Settings"}
        other_entry = Mock()
        other_entry.data = {"provider": "OpenAI"}
        mock_hass.config_entries.async_entries.return_value = [other_entry, settings_entry]

        result = await async_get_settings_entry(mock_hass)

        assert result is settings_entry

    @pytest.mark.asyncio
    async def test_returns_none_when_settings_missing(self, mock_hass):
        mock_hass.config_entries.async_entries.return_value = []

        result = await async_get_settings_entry(mock_hass)

        assert result is None


class TestTimelineEventsView:
    """Tests for TimelineEventsView."""

    @pytest.mark.asyncio
    async def test_returns_404_without_settings_entry(self, mock_hass):
        request = _make_request(mock_hass)

        response = await TimelineEventsView().get(request)

        assert response.status == 404
        assert _response_payload(response)["message"] == "Settings config entry not found"

    @pytest.mark.asyncio
    async def test_passes_filters_and_hours_to_timeline(self, mock_hass, mock_config_entry):
        request = _make_request(
            mock_hass,
            query={
                "limit": "500",
                "cameras": " Front Door , Backyard ",
                "categories": "person, vehicle",
                "days": "7",
                "hours": "2",
                "include_no_activity": "YeS",
            },
        )
        timeline = Mock()
        timeline.get_events_json = AsyncMock(return_value=[{"uid": "event-1"}])
        now = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline), patch(
            "custom_components.llmvision.api.dt_util.now", return_value=now
        ):
            response = await TimelineEventsView().get(request)

        assert response.status == 200
        assert _response_payload(response) == {"events": [{"uid": "event-1"}]}
        timeline.get_events_json.assert_awaited_once_with(
            limit=500,
            cameras=["Front Door", "Backyard"],
            categories=["person", "vehicle"],
            start=(now - timedelta(hours=2)).isoformat(),
            end=now.isoformat(),
            include_no_activity=True,
        )

    @pytest.mark.asyncio
    async def test_uses_default_limit_and_ignores_invalid_ranges(self, mock_hass, mock_config_entry):
        request = _make_request(
            mock_hass,
            query={
                "limit": "invalid",
                "cameras": " , ",
                "categories": None,
                "days": "not-a-number",
                "include_no_activity": "false",
            },
        )
        timeline = Mock()
        timeline.get_events_json = AsyncMock(return_value=[])

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventsView().get(request)

        assert response.status == 200
        timeline.get_events_json.assert_awaited_once_with(
            limit=10,
            cameras=None,
            categories=None,
            start=None,
            end=None,
            include_no_activity=False,
        )


class TestTimelineEventCreateView:
    """Tests for TimelineEventCreateView."""

    @pytest.mark.asyncio
    async def test_returns_404_without_settings_entry(self, mock_hass):
        request = _make_request(mock_hass, json_body={})

        response = await TimelineEventCreateView().post(request)

        assert response.status == 404
        assert _response_payload(response)["message"] == "Settings config entry not found"

    @pytest.mark.asyncio
    async def test_returns_400_for_invalid_json(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_exception=ValueError("boom"))

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ):
            response = await TimelineEventCreateView().post(request)

        assert response.status == 400
        assert _response_payload(response)["message"] == "Invalid JSON body"

    @pytest.mark.asyncio
    async def test_creates_event_with_defaults_and_lowercase_label(self, mock_hass, mock_config_entry):
        request = _make_request(
            mock_hass,
            json_body={
                "title": "Visitor",
                "description": "Someone at the door",
                "key_frame": "snapshot.jpg",
                "camera_entity": "camera.front_door",
                "label": "Person",
            },
        )
        timeline = Mock()
        timeline.create_event = AsyncMock()
        now = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline), patch(
            "custom_components.llmvision.api.dt_util.now", return_value=now
        ):
            response = await TimelineEventCreateView().post(request)

        assert response.status == 200
        assert _response_payload(response) == {"status": "created"}
        timeline.create_event.assert_awaited_once_with(
            start=now,
            end=now + timedelta(minutes=1),
            title="Visitor",
            description="Someone at the door",
            key_frame="snapshot.jpg",
            camera_name="camera.front_door",
            label="person",
        )

    @pytest.mark.asyncio
    async def test_creates_event_from_explicit_times(self, mock_hass, mock_config_entry):
        start = "2024-01-15T12:00:00+00:00"
        end = "2024-01-15T12:05:00+00:00"
        request = _make_request(
            mock_hass,
            json_body={
                "start": start,
                "end": end,
            },
        )
        timeline = Mock()
        timeline.create_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventCreateView().post(request)

        assert response.status == 200
        call = timeline.create_event.await_args.kwargs
        assert call["start"].isoformat() == start
        assert call["end"].isoformat() == end

    @pytest.mark.asyncio
    async def test_creates_event_fromisoformat_fallback(self, mock_hass, mock_config_entry):
        request = _make_request(
            mock_hass,
            json_body={
                "start": "2024-01-15 12:00:00",
                "end": "2024-01-15 12:05:00",
            },
        )
        timeline = Mock()
        timeline.create_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline), patch(
            "custom_components.llmvision.api.dt_util.parse_datetime", return_value=None
        ):
            response = await TimelineEventCreateView().post(request)

        assert response.status == 200
        call = timeline.create_event.await_args.kwargs
        assert call["start"] == datetime(2024, 1, 15, 12, 0, 0)
        assert call["end"] == datetime(2024, 1, 15, 12, 5, 0)

    @pytest.mark.asyncio
    async def test_creates_event_from_timestamps(self, mock_hass, mock_config_entry):
        start_timestamp = 1705320000
        end_timestamp = 1705320300
        request = _make_request(
            mock_hass,
            json_body={
                "start": start_timestamp,
                "end": end_timestamp,
            },
        )
        timeline = Mock()
        timeline.create_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventCreateView().post(request)

        assert response.status == 200
        call = timeline.create_event.await_args.kwargs
        assert call["start"] == datetime.fromtimestamp(start_timestamp)
        assert call["end"] == datetime.fromtimestamp(end_timestamp)

    @pytest.mark.asyncio
    async def test_returns_500_when_create_fails(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_body={})
        timeline = Mock()
        timeline.create_event = AsyncMock(side_effect=RuntimeError("db error"))

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventCreateView().post(request)

        assert response.status == 500
        assert _response_payload(response)["message"] == "Error creating event"


class TestTimelineEventView:
    """Tests for TimelineEventView."""

    @pytest.mark.asyncio
    async def test_get_returns_404_without_settings_entry(self, mock_hass):
        request = _make_request(mock_hass)

        response = await TimelineEventView().get(request, "event-1")

        assert response.status == 404
        assert _response_payload(response)["message"] == "Settings config entry not found"

    @pytest.mark.asyncio
    async def test_get_returns_event(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass)
        timeline = Mock()
        timeline.get_event = AsyncMock(return_value={"uid": "event-1", "title": "Test"})

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().get(request, "event-1")

        assert response.status == 200
        assert _response_payload(response) == {"event": {"uid": "event-1", "title": "Test"}}

    @pytest.mark.asyncio
    async def test_get_returns_404_when_event_missing(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass)
        timeline = Mock()
        timeline.get_event = AsyncMock(return_value=None)

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().get(request, "missing")

        assert response.status == 404
        assert _response_payload(response)["message"] == "Event not found"

    @pytest.mark.asyncio
    async def test_delete_returns_deleted_status(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass)
        timeline = Mock()
        timeline.delete_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().delete(request, "event-1")

        assert response.status == 200
        assert _response_payload(response) == {"event_id": "event-1", "status": "deleted"}

    @pytest.mark.asyncio
    async def test_delete_returns_404_without_settings_entry(self, mock_hass):
        request = _make_request(mock_hass)

        response = await TimelineEventView().delete(request, "event-1")

        assert response.status == 404
        assert _response_payload(response)["message"] == "Settings config entry not found"

    @pytest.mark.asyncio
    async def test_delete_returns_500_when_delete_fails(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass)
        timeline = Mock()
        timeline.delete_event = AsyncMock(side_effect=RuntimeError("delete failed"))

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().delete(request, "event-1")

        assert response.status == 500
        assert _response_payload(response)["message"] == "Error deleting event"

    @pytest.mark.asyncio
    async def test_post_updates_event_and_returns_updated_event(self, mock_hass, mock_config_entry):
        request = _make_request(
            mock_hass,
            json_body={
                "description": "Updated description",
                "camera_entity": "camera.backyard",
                "label": "Vehicle",
            },
        )
        existing = {
            "title": "Original",
            "description": "Old description",
            "key_frame": "frame.jpg",
            "camera_name": "camera.front_door",
            "label": "person",
            "start": "2024-01-15T12:00:00+00:00",
            "end": "2024-01-15T12:05:00+00:00",
        }
        updated = {"uid": "event-1", "label": "vehicle"}
        timeline = Mock()
        timeline.get_event = AsyncMock(side_effect=[existing, updated])
        timeline.update_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 200
        assert _response_payload(response) == {"event": updated}
        timeline.update_event.assert_awaited_once()
        call = timeline.update_event.await_args.kwargs
        assert call["uid"] == "event-1"
        assert call["title"] == "Original"
        assert call["description"] == "Updated description"
        assert call["camera_name"] == "camera.backyard"
        assert call["label"] == "vehicle"
        assert call["start"].isoformat() == existing["start"]
        assert call["end"].isoformat() == existing["end"]

    @pytest.mark.asyncio
    async def test_post_returns_404_without_settings_entry(self, mock_hass):
        request = _make_request(mock_hass, json_body={})

        response = await TimelineEventView().post(request, "event-1")

        assert response.status == 404
        assert _response_payload(response)["message"] == "Settings config entry not found"

    @pytest.mark.asyncio
    async def test_post_returns_status_when_updated_event_is_missing(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_body={})
        existing = {
            "title": "Original",
            "description": "Desc",
            "key_frame": "frame.jpg",
            "camera_name": "camera.front_door",
            "label": "person",
            "start": datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
            "end": datetime(2024, 1, 15, 12, 5, tzinfo=timezone.utc),
        }
        timeline = Mock()
        timeline.get_event = AsyncMock(side_effect=[existing, None])
        timeline.update_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 200
        assert _response_payload(response) == {"event_id": "event-1", "status": "updated"}

    @pytest.mark.asyncio
    async def test_post_accepts_timestamp_times(self, mock_hass, mock_config_entry):
        start_timestamp = 1705320000
        end_timestamp = 1705320300
        request = _make_request(
            mock_hass,
            json_body={
                "start": start_timestamp,
                "end": end_timestamp,
            },
        )
        existing = {
            "title": "Original",
            "description": "Desc",
            "key_frame": "frame.jpg",
            "camera_name": "camera.front_door",
            "label": "person",
            "start": "2024-01-15T12:00:00+00:00",
            "end": "2024-01-15T12:05:00+00:00",
        }
        updated = {"uid": "event-1"}
        timeline = Mock()
        timeline.get_event = AsyncMock(side_effect=[existing, updated])
        timeline.update_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 200
        call = timeline.update_event.await_args.kwargs
        assert call["start"] == datetime.fromtimestamp(start_timestamp)
        assert call["end"] == datetime.fromtimestamp(end_timestamp)

    @pytest.mark.asyncio
    async def test_post_returns_400_for_invalid_json(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_exception=ValueError("bad json"))

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 400
        assert _response_payload(response)["message"] == "Invalid JSON body"

    @pytest.mark.asyncio
    async def test_post_returns_500_when_existing_lookup_fails(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_body={})
        timeline = Mock()
        timeline.get_event = AsyncMock(side_effect=RuntimeError("lookup failed"))

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 500
        assert _response_payload(response)["message"] == "Error retrieving event"

    @pytest.mark.asyncio
    async def test_post_returns_404_when_existing_event_missing(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_body={})
        timeline = Mock()
        timeline.get_event = AsyncMock(return_value=None)

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 404
        assert _response_payload(response)["message"] == "Event not found"

    @pytest.mark.asyncio
    async def test_post_returns_400_for_invalid_times(self, mock_hass, mock_config_entry):
        request = _make_request(
            mock_hass,
            json_body={"start": "not-a-time"},
        )
        timeline = Mock()
        timeline.get_event = AsyncMock(
            return_value={
                "title": "Original",
                "description": "Desc",
                "key_frame": "frame.jpg",
                "camera_name": "camera.front_door",
                "label": "person",
                "start": "2024-01-15T12:00:00+00:00",
                "end": "2024-01-15T12:05:00+00:00",
            }
        )

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 400
        assert _response_payload(response)["message"] == "Invalid start/end time"

    @pytest.mark.asyncio
    async def test_post_returns_500_when_update_fails(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_body={})
        timeline = Mock()
        timeline.get_event = AsyncMock(
            return_value={
                "title": "Original",
                "description": "Desc",
                "key_frame": "frame.jpg",
                "camera_name": "camera.front_door",
                "label": "person",
                "start": "2024-01-15T12:00:00+00:00",
                "end": "2024-01-15T12:05:00+00:00",
            }
        )
        timeline.update_event = AsyncMock(side_effect=RuntimeError("update failed"))

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 500
        assert _response_payload(response)["message"] == "Error updating event"

    @pytest.mark.asyncio
    async def test_post_returns_status_when_updated_event_cannot_be_loaded(self, mock_hass, mock_config_entry):
        request = _make_request(mock_hass, json_body={})
        existing = {
            "title": "Original",
            "description": "Desc",
            "key_frame": "frame.jpg",
            "camera_name": "camera.front_door",
            "label": "person",
            "start": datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
            "end": datetime(2024, 1, 15, 12, 5, tzinfo=timezone.utc),
        }
        timeline = Mock()
        timeline.get_event = AsyncMock(side_effect=[existing, RuntimeError("reload failed")])
        timeline.update_event = AsyncMock()

        with patch(
            "custom_components.llmvision.api.async_get_settings_entry",
            new=AsyncMock(return_value=mock_config_entry),
        ), patch("custom_components.llmvision.api.Timeline", return_value=timeline):
            response = await TimelineEventView().post(request, "event-1")

        assert response.status == 200
        assert _response_payload(response) == {"event_id": "event-1", "status": "updated"}
