import random
import string
import uuid

from flask import Blueprint, redirect, render_template, request, jsonify, url_for
from flask_socketio import emit, join_room as sio_join_room

from poker import db

poker_bp = Blueprint("poker", __name__, url_prefix="/poker")

FIBONACCI = [1, 2, 3, 5, 8, 13, 21, "?", "☕"]


def _generate_room_id(length=6):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _safe_room(room: dict, show_votes: bool) -> dict:
    participants = {}
    for sid, p in room["participants"].items():
        participants[sid] = {
            "name": p["name"],
            "isAdmin": p["isAdmin"],
            "voted": p["vote"] is not None,
            "vote": p["vote"] if show_votes else None,
        }
    return {
        "id": room["id"],
        "revealed": room["revealed"],
        "participants": participants,
        "tickets": room.get("tickets", []),
    }


@poker_bp.route("/")
def home():
    return render_template("poker/home.html")


@poker_bp.route("/create", methods=["POST"])
def create():
    room_id = _generate_room_id()
    admin_token = str(uuid.uuid4())
    db.create_room(room_id, admin_token)
    return jsonify({"roomId": room_id, "adminToken": admin_token})


@poker_bp.route("/room/<room_id>")
def room(room_id):
    room_data = db.get_room(room_id)
    if not room_data:
        return redirect(url_for("poker.home"))
    return render_template("poker/room.html", room_id=room_id, fibonacci=FIBONACCI)


@poker_bp.route("/api/room/<room_id>/tickets", methods=["POST"])
def api_add_tickets(room_id):
    room_data = db.get_room(room_id)
    if not room_data:
        return jsonify({"error": "Room not found"}), 404

    data = request.get_json(silent=True) or {}
    tickets = data.get("tickets", [])
    if not tickets:
        ticket_id = (data.get("ticketId") or "").strip().upper()
        title = (data.get("title") or "").strip()
        if not ticket_id:
            return jsonify({"error": "ticketId is required"}), 400
        tickets = [{"ticketId": ticket_id, "title": title}]

    added = []
    for t in tickets:
        tid = (t.get("ticketId") or "").strip().upper()
        title = (t.get("title") or "").strip()
        if not tid:
            continue
        room_data = db.add_ticket(room_id, tid, title)
        added.append(tid)

    if room_data and added:
        sio = poker_bp.extensions["socketio"]
        sio.emit("room_state", _safe_room(room_data, show_votes=room_data["revealed"]), to=room_id)

    return jsonify({"added": added, "count": len(added)})


def init_poker_socketio(socketio):
    poker_bp.extensions = {"socketio": socketio}

    @socketio.on("join_room")
    def on_join(data):
        room_id = data.get("roomId")
        name = (data.get("name") or "").strip()
        admin_token = data.get("adminToken")

        if not room_id or not name:
            emit("error", {"message": "roomId and name are required"})
            return

        room = db.get_room(room_id)
        if not room:
            emit("error", {"message": "Room not found"})
            return

        is_admin = admin_token == room["adminToken"]
        sid = request.sid

        sio_join_room(room_id)
        room = db.add_participant(room_id, sid, name, is_admin)

        emit("room_state", _safe_room(room, show_votes=room["revealed"]), to=room_id)

    @socketio.on("vote")
    def on_vote(data):
        room_id = data.get("roomId")
        vote = data.get("vote")
        sid = request.sid

        if not room_id:
            return

        room = db.set_vote(room_id, sid, vote)
        if not room:
            return

        emit("room_state", _safe_room(room, show_votes=room["revealed"]), to=room_id)

    @socketio.on("reveal")
    def on_reveal(data):
        room_id = data.get("roomId")
        admin_token = data.get("adminToken")

        room = db.get_room(room_id)
        if not room or room["adminToken"] != admin_token:
            return

        room = db.reveal_room(room_id)
        emit("cards_revealed", _safe_room(room, show_votes=True), to=room_id)

    @socketio.on("rename")
    def on_rename(data):
        room_id = data.get("roomId")
        name = (data.get("name") or "").strip()
        if not room_id or not name:
            return
        room = db.rename_participant(room_id, request.sid, name)
        if not room:
            return
        emit("room_state", _safe_room(room, show_votes=room["revealed"]), to=room_id)

    @socketio.on("reset_round")
    def on_reset(data):
        room_id = data.get("roomId")
        admin_token = data.get("adminToken")

        room = db.get_room(room_id)
        if not room or room["adminToken"] != admin_token:
            return

        room = db.reset_room(room_id)
        next_ticket = db.advance_to_next_ticket(room_id)
        if next_ticket:
            room = db.get_room(room_id)
        payload = _safe_room(room, show_votes=False)
        if next_ticket:
            payload["newTicket"] = next_ticket
        emit("round_reset", payload, to=room_id)

    @socketio.on("add_ticket")
    def on_add_ticket(data):
        room_id = data.get("roomId")
        ticket_id = (data.get("ticketId") or "").strip().upper()
        title = (data.get("title") or "").strip()

        if not room_id or not ticket_id:
            return

        room = db.add_ticket(room_id, ticket_id, title)
        if room:
            emit("room_state", _safe_room(room, show_votes=room["revealed"]), to=room_id)

    @socketio.on("remove_ticket")
    def on_remove_ticket(data):
        room_id = data.get("roomId")
        ticket_uuid = data.get("id")

        room = db.remove_ticket(room_id, ticket_uuid)
        if room:
            emit("room_state", _safe_room(room, show_votes=room["revealed"]), to=room_id)

    @socketio.on("set_active_ticket")
    def on_set_active_ticket(data):
        room_id = data.get("roomId")
        ticket_uuid = data.get("id")

        room = db.set_active_ticket(room_id, ticket_uuid)
        if room:
            emit("room_state", _safe_room(room, show_votes=room["revealed"]), to=room_id)

    @socketio.on("disconnect")
    def on_disconnect():
        sid = request.sid
        all_rooms = db._read()

        for room_id, room in all_rooms.items():
            if sid in room.get("participants", {}):
                updated = db.remove_participant(room_id, sid)
                if updated:
                    emit(
                        "room_state",
                        _safe_room(updated, show_votes=updated["revealed"]),
                        to=room_id,
                    )
                break
