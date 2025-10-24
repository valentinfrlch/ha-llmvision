import requests

BASE_URL = ""
TOKEN = ""
with open("tests/.instance") as f:
    BASE_URL = f.read().strip()

with open("tests/.token") as f:
    TOKEN = f.read().strip()

LIST_URL = f"{BASE_URL}/api/llmvision/timeline/events"
CREATE_URL = f"{BASE_URL}/api/llmvision/timeline/events/new"
EVENT_URL_BASE = f"{BASE_URL}/api/llmvision/timeline/event"


def _auth_headers():
    if not TOKEN or TOKEN.startswith("REPLACE_WITH"):
        raise AssertionError(
            "Set TOKEN in tests/test_api.py to a valid Home Assistant long-lived access token."
        )
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }


def _pick_event_id(event):
    if not isinstance(event, dict):
        return None
    for k in ("uid", "id", "event_id"):
        if k in event and event[k] is not None:
            return str(event[k])
    return None


def _create_event(session, label="car", camera_name="camera.demo_camera"):
    resp = session.post(
        CREATE_URL,
        json={
            "title": "Test Event from API",
            "description": "This is a test event created during API testing.",
            "key_frame": "frame_001.jpg",
            "label": label,
            "camera_name": camera_name,
        },
        timeout=10,
    )
    assert resp.status_code == 200, f"Create failed: {resp.status_code} {resp.text}"
    body = resp.json()
    event = body.get("event")

    if not event:
        # Fallback to most recent
        lst = session.get(LIST_URL, json={"limit": 1}, timeout=10)
        assert (
            lst.status_code == 200
        ), f"List after create failed: {lst.status_code} {lst.text}"
        events = lst.json().get("events", [])
        assert events, "No events returned after create"
        event = events[0]

    event_id = _pick_event_id(event)
    assert event_id, f"Unable to determine event_id from event payload: {event}"
    return event_id, event


def _get_event(session, event_id):
    resp = session.get(f"{EVENT_URL_BASE}/{event_id}", timeout=10)
    return resp


def _update_event(session, event_id, payload):
    resp = session.post(f"{EVENT_URL_BASE}/{event_id}", json=payload, timeout=10)
    return resp


def _delete_event(session, event_id):
    resp = session.delete(f"{EVENT_URL_BASE}/{event_id}", timeout=10)
    return resp


def test_list_events_basic():
    s = requests.Session()
    s.headers.update(_auth_headers())

    # Basic list
    r = s.get(LIST_URL, timeout=10)
    assert r.status_code == 200, f"List failed: {r.status_code} {r.text}"
    data = r.json()
    assert "events" in data and isinstance(data["events"], list)

    # List with limit
    r = s.get(LIST_URL+"?limit=1", timeout=10)
    assert r.status_code == 200, f"List with limit failed: {r.status_code} {r.text}"
    events = r.json().get("events", [])
    assert isinstance(events, list) and len(events) <= 1

    # List with invalid days (should still succeed)
    r = s.get(LIST_URL+"?days=not-a-number", timeout=10)
    assert (
        r.status_code == 200
    ), f"List with invalid days failed: {r.status_code} {r.text}"


def test_event_lifecycle_create_get_update_delete():
    s = requests.Session()
    s.headers.update(_auth_headers())

    # Create
    event_id, created = _create_event(
        s,
        label="Car",
        camera_name="camera.demo_camera",
    )

    # Get
    r = _get_event(s, event_id)
    assert r.status_code == 200, f"Get after create failed: {r.status_code} {r.text}"
    evt = r.json().get("event")
    assert evt and _pick_event_id(evt) == event_id

    # Update label only (backend uses existing start/end)
    new_label = "Person"
    r = _update_event(s, event_id, {"label": new_label})
    if r.status_code == 501:
        # Backend doesn't support update; accept and end test early
        return
    assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"

    # Verify update
    body = r.json()
    updated_evt = body.get("event")
    if updated_evt:
        assert (
            updated_evt.get("label") == new_label
        ), f"Updated label mismatch: {updated_evt}"
    else:
        # If response didn't include event, fetch it
        r2 = _get_event(s, event_id)
        assert (
            r2.status_code == 200
        ), f"Get after update failed: {r2.status_code} {r2.text}"
        evt2 = r2.json().get("event")
        assert evt2 and evt2.get("label") == new_label.lower()

    # Delete
    r = _delete_event(s, event_id)
    assert r.status_code == 200, f"Delete failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("status") == "deleted"

    # Ensure it's gone
    r = _get_event(s, event_id)
    assert (
        r.status_code == 404
    ), f"Expected 404 after delete, got {r.status_code} {r.text}"


def test_list_with_filters_and_days():
    s = requests.Session()
    s.headers.update(_auth_headers())

    # Create two events to ensure there is data
    e1_id, _ = _create_event(s, label="Nature", camera_name="CamA")
    e2_id, _ = _create_event(s, label="Person", camera_name="CamB")

    try:
        # Apply filters; we only assert the API works and returns a list
        r = s.get(
            LIST_URL,
            json={
                "cameras": ["camera.demo_camera"],
                "days": 1,
                "limit": 5,
            },
            timeout=10,
        )
        assert r.status_code == 200, f"Filtered list failed: {r.status_code} {r.text}"
        data = r.json()
        assert "events" in data and isinstance(data["events"], list)
    finally:
        # Cleanup
        _delete_event(s, e1_id)
        _delete_event(s, e2_id)


def test_update_nonexistent_event():
    s = requests.Session()
    s.headers.update(_auth_headers())

    bogus_id = "nonexistent-event-id-for-tests"
    r = _update_event(s, bogus_id, {"label": "won't matter"})
    # Expect either 404 (not found) or 501 (update not supported)
    assert r.status_code in (
        404,
        501,
    ), f"Unexpected status for updating nonexistent event: {r.status_code} {r.text}"
