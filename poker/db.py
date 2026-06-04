import json
import os
import threading
import uuid
from datetime import datetime, timezone

_local_data = os.path.join(os.path.dirname(__file__), "..", "data")
DB_DIR = _local_data if os.path.isdir(_local_data) else "/tmp/poker"
DB_PATH = os.path.join(DB_DIR, "rooms.json")

_lock = threading.Lock()


def _ensure_dir():
    os.makedirs(DB_DIR, exist_ok=True)


def _read() -> dict:
    try:
        with open(DB_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    _ensure_dir()
    with open(DB_PATH, "w") as f:
        json.dump(data, f, indent=2)


def get_room(room_id: str) -> dict | None:
    with _lock:
        return _read().get(room_id)


def save_room(room: dict) -> None:
    with _lock:
        data = _read()
        data[room["id"]] = room
        _write(data)


def create_room(room_id: str, admin_token: str) -> dict:
    room = {
        "id": room_id,
        "adminToken": admin_token,
        "revealed": False,
        "chatEnabled": True,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "participants": {},
        "tickets": [],
    }
    save_room(room)
    return room


def add_participant(room_id: str, sid: str, name: str, is_admin: bool) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        room["participants"][sid] = {"name": name, "vote": None, "isAdmin": is_admin}
        _write(data)
        return room


def remove_participant(room_id: str, sid: str) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        room["participants"].pop(sid, None)
        _write(data)
        return room


def set_vote(room_id: str, sid: str, vote) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room or sid not in room["participants"]:
            return None
        room["participants"][sid]["vote"] = vote
        _write(data)
        return room


def reveal_room(room_id: str) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        room["revealed"] = True
        _write(data)
        return room


def add_ticket(room_id: str, ticket_id: str, title: str) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        room.setdefault("tickets", []).append({
            "id": str(uuid.uuid4()),
            "ticketId": ticket_id,
            "title": title,
            "active": False,
        })
        _write(data)
        return room


def remove_ticket(room_id: str, ticket_uuid: str) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        room["tickets"] = [t for t in room.get("tickets", []) if t["id"] != ticket_uuid]
        _write(data)
        return room


def set_active_ticket(room_id: str, ticket_uuid: str | None) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        for t in room.get("tickets", []):
            t["active"] = (t["id"] == ticket_uuid)
        _write(data)
        return room


def rename_participant(room_id: str, sid: str, name: str) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room or sid not in room["participants"]:
            return None
        room["participants"][sid]["name"] = name
        _write(data)
        return room


def advance_to_next_ticket(room_id: str) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        tickets = room.get("tickets", [])
        active_idx = next((i for i, t in enumerate(tickets) if t.get("active")), -1)
        if active_idx == -1 or active_idx + 1 >= len(tickets):
            return None
        next_idx = active_idx + 1
        for i, t in enumerate(tickets):
            t["active"] = (i == next_idx)
        _write(data)
        return tickets[next_idx]


def reset_room(room_id: str) -> dict | None:
    with _lock:
        data = _read()
        room = data.get(room_id)
        if not room:
            return None
        room["revealed"] = False
        for p in room["participants"].values():
            p["vote"] = None
        _write(data)
        return room
