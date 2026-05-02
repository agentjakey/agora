import os
import uuid
import json
import random
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"

rooms: dict = {}

with open("data/fallback_questions.json") as f:
    FALLBACK_QUESTIONS = json.load(f)


def generate_room_code() -> str:
    while True:
        code = "".join(random.choices(CONSONANTS, k=4))
        if code not in rooms:
            return code


def make_room(room_code: str, host_id: str, host_name: str, flavors: list[str]) -> dict:
    return {
        "room_code": room_code,
        "host_id": host_id,
        "flavors": flavors,
        "users": {host_id: {"name": host_name, "connected": False}},
        "current_question": None,
        "votes": {},
        "question_history": [],
        "phase": "lobby",
        "connections": [],
    }


def room_state(room: dict) -> dict:
    return {
        "room_code": room["room_code"],
        "host_id": room["host_id"],
        "flavors": room["flavors"],
        "users": room["users"],
        "current_question": room["current_question"],
        "votes": room["votes"],
        "question_history": room["question_history"],
        "phase": room["phase"],
    }


async def broadcast(room: dict, message: dict):
    dead = []
    for ws in room["connections"]:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        room["connections"].remove(ws)


async def generate_question(flavors: list[str]) -> dict:
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    system_prompt = (
        "You are a philosophical dilemma designer in the tradition of Socratic dialogue.\n"
        "Your role is to generate a single 'Would You Rather' question that:\n"
        "- Presents two genuinely asymmetric options — both have real costs and real rewards\n"
        "- Touches on philosophical themes: identity, consciousness, knowledge, justice, time, power, or meaning\n"
        "- Is designed to split a group of thoughtful people and generate real disagreement\n"
        "- Contains no shock value, no graphic content, no political figures, no trauma triggers\n"
        "- Is specific enough to picture but universal enough to apply to any human life\n"
        "- Is appropriate for all ages above 16\n\n"
        'Respond ONLY with a JSON object, no markdown, no backticks, no preamble:\n'
        '{\n'
        '  "option_a": "full text of the first choice",\n'
        '  "option_b": "full text of the second choice",\n'
        '  "framing": "one sentence describing what is philosophically at stake between these two options",\n'
        '  "flavors": [list of 1-3 flavor tags that apply: Consciousness, Identity, Knowledge, Morality, Power, Time, Meaning]\n'
        '}'
    )

    user_message = "Generate a philosophical Would You Rather question."
    if flavors:
        user_message = f"Generate a question emphasizing these philosophical flavors: {', '.join(flavors)}"

    for attempt in range(2):
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            raw = response.content[0].text.strip()
            data = json.loads(raw)
            return {
                "id": str(uuid.uuid4()),
                "option_a": data["option_a"],
                "option_b": data["option_b"],
                "framing": data["framing"],
                "flavors": data.get("flavors", []),
            }
        except json.JSONDecodeError:
            if attempt == 0:
                logger.warning("Malformed JSON from Claude, retrying once...")
                continue
            logger.error("Claude returned malformed JSON on both attempts, using fallback.")
            break
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            break

    fallback = random.choice(FALLBACK_QUESTIONS)
    return {
        "id": str(uuid.uuid4()),
        "option_a": fallback["option_a"],
        "option_b": fallback["option_b"],
        "framing": fallback.get("framing", ""),
        "flavors": fallback.get("flavors", []),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Agora", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateRoomBody(BaseModel):
    host_name: str
    flavors: list[str] = []


class JoinRoomBody(BaseModel):
    room_code: str
    user_name: str
    user_id: Optional[str] = None


class StartRoomBody(BaseModel):
    host_id: str


class VoteBody(BaseModel):
    user_id: str
    vote: str


class NextBody(BaseModel):
    host_id: str


class EndBody(BaseModel):
    host_id: str


@app.post("/room/create")
async def create_room(body: CreateRoomBody):
    host_id = str(uuid.uuid4())
    user_id = host_id
    room_code = generate_room_code()
    rooms[room_code] = make_room(room_code, host_id, body.host_name, body.flavors)
    return {"room_code": room_code, "host_id": host_id, "user_id": user_id}


@app.post("/room/join")
async def join_room(body: JoinRoomBody):
    room_code = body.room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    user_id = body.user_id if body.user_id else str(uuid.uuid4())
    if user_id not in room["users"]:
        room["users"][user_id] = {"name": body.user_name, "connected": False}
    return {"room_code": room_code, "user_id": user_id, "room_state": room_state(room)}


@app.get("/room/{room_code}")
async def get_room(room_code: str):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    return room_state(rooms[room_code])


@app.post("/room/{room_code}/start")
async def start_room(room_code: str, body: StartRoomBody):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != body.host_id:
        raise HTTPException(status_code=403, detail="Only the host can start the session")
    room["phase"] = "question"
    room["votes"] = {}
    question = await generate_question(room["flavors"])
    room["current_question"] = question
    await broadcast(room, {"event": "question_ready", "question": question})
    return {"status": "started", "question": question}


@app.post("/room/{room_code}/vote")
async def vote(room_code: str, body: VoteBody):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if body.vote not in ("A", "B"):
        raise HTTPException(status_code=400, detail="Vote must be 'A' or 'B'")
    room["votes"][body.user_id] = body.vote

    vote_counts = {"A": 0, "B": 0}
    for v in room["votes"].values():
        vote_counts[v] += 1

    voted_ids = list(room["votes"].keys())
    connected_users = [uid for uid, u in room["users"].items() if u.get("connected", False)]
    total_connected = len(connected_users)

    await broadcast(room, {
        "event": "vote_update",
        "votes": {
            "A": vote_counts["A"],
            "B": vote_counts["B"],
            "total": len(voted_ids),
            "voted_ids": voted_ids,
        },
    })

    if total_connected > 0 and len(voted_ids) >= total_connected:
        room["phase"] = "reveal"
        if room["current_question"]:
            room["question_history"].append({
                **room["current_question"],
                "final_votes": vote_counts,
            })
        await broadcast(room, {
            "event": "reveal",
            "final_votes": vote_counts,
            "question": room["current_question"],
        })

    return {"status": "voted"}


@app.post("/room/{room_code}/next")
async def next_question(room_code: str, body: NextBody):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != body.host_id:
        raise HTTPException(status_code=403, detail="Only the host can advance")
    room["votes"] = {}
    room["phase"] = "question"
    question = await generate_question(room["flavors"])
    room["current_question"] = question
    await broadcast(room, {"event": "question_ready", "question": question})
    return {"status": "next", "question": question}


@app.post("/room/{room_code}/end")
async def end_session(room_code: str, body: EndBody):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != body.host_id:
        raise HTTPException(status_code=403, detail="Only the host can end the session")
    room["phase"] = "ended"
    await broadcast(room, {"event": "session_ended"})
    return {"status": "ended"}


@app.websocket("/ws/{room_code}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, user_id: str):
    room_code = room_code.upper()
    await websocket.accept()

    if room_code not in rooms:
        await websocket.close(code=4004, reason="Room not found")
        return

    room = rooms[room_code]

    if user_id not in room["users"]:
        room["users"][user_id] = {"name": "Anonymous", "connected": True}
    else:
        room["users"][user_id]["connected"] = True

    room["connections"].append(websocket)

    await broadcast(room, {
        "event": "user_joined",
        "user": {"id": user_id, "name": room["users"][user_id]["name"]},
    })

    try:
        await websocket.send_json({"event": "room_state", "state": room_state(room)})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for {user_id}: {e}")
    finally:
        if websocket in room["connections"]:
            room["connections"].remove(websocket)
        if user_id in room["users"]:
            room["users"][user_id]["connected"] = False
        await broadcast(room, {"event": "user_left", "user_id": user_id})
