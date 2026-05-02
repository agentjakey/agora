import os
import uuid
import json
import random
import logging
import time
import asyncio
import difflib
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"
RATE_LIMIT_SECONDS = 20
DEDUP_HISTORY = 20
SIMILARITY_THRESHOLD = 0.80
AUTO_REVEAL_SECONDS = 45

rooms: dict = {}

with open("data/fallback_questions.json") as f:
    FALLBACK_QUESTIONS = json.load(f)

SYSTEM_PROMPT = """You are a philosophical dilemma architect trained in the tradition of Socratic dialogue,
Kant's moral philosophy, and the thought experiments of Derek Parfit and Robert Nozick.

Your task is to generate a single Would You Rather question that:

MUST HAVE:
- Two options that are genuinely asymmetric — one is not obviously better
- Real philosophical stakes: something about identity, consciousness, knowledge,
  justice, free will, meaning, time, or power is at stake
- Enough specificity to be imaginable but enough abstraction to be universal
- The capacity to split a thoughtful group of people 40/60 or 50/50
- A framing sentence that names the philosophical tension precisely

MUST NOT HAVE:
- Shock value, body horror, graphic content
- Direct political figures or partisan hot-button issues
- Content inappropriate for anyone over 16
- An obvious 'right answer' that ends the debate before it begins
- Options that differ only in scale (e.g. 'save 1 person vs. save 100')

QUALITY BENCHMARK:
A question passes if, after reading it, a thoughtful person says:
'Oh, that's actually hard. I need to think about that.'

BAD EXAMPLE (too trivial):
Would you rather always be 10 minutes late or always be 20 minutes early?

GOOD EXAMPLE (target quality):
Would you rather spend your life building something that outlasts you but which
you will never see completed, or complete something meaningful within your lifetime
that disappears entirely when you die?

Respond ONLY with a JSON object:
{
  "option_a": "...",
  "option_b": "...",
  "framing": "one precise sentence naming the philosophical tension",
  "flavors": ["1-3 tags from: Consciousness, Identity, Knowledge, Morality, Power, Time, Meaning, Science"]
}"""


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
        "preview_question": None,
        "votes": {},
        "question_history": [],
        "question_texts": [],
        "phase": "lobby",
        "connections": [],
        "last_generated_at": 0.0,
        "timer_task": None,
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


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_duplicate(question: dict, question_texts: list[str]) -> bool:
    candidate = question["option_a"] + " " + question["option_b"]
    for prev in question_texts:
        if _similarity(candidate, prev) >= SIMILARITY_THRESHOLD:
            return True
    return False


def _record_question(room: dict, question: dict):
    text = question["option_a"] + " " + question["option_b"]
    room["question_texts"].append(text)
    if len(room["question_texts"]) > DEDUP_HISTORY:
        room["question_texts"].pop(0)


def _parse_claude_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


async def _call_claude(flavors: list[str]) -> dict | None:
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_message = "Generate a philosophical Would You Rather question."
    if flavors:
        user_message = (
            f"Generate a philosophical Would You Rather question.\n"
            f"This group has indicated interest in: {', '.join(flavors)}.\n"
            f"Prioritize questions that engage these themes, but do not sacrifice quality for specificity."
        )

    for attempt in range(2):
        try:
            response = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            data = _parse_claude_response(response.content[0].text)
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
            logger.error("Malformed JSON on both attempts, using fallback.")
            break
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            break

    return None


async def generate_question(flavors: list[str], question_texts: list[str]) -> dict:
    for attempt in range(3):
        q = await _call_claude(flavors)
        if q is None:
            break
        if not _is_duplicate(q, question_texts):
            return q
        logger.info(f"Duplicate detected on attempt {attempt + 1}, regenerating...")
        if attempt == 2:
            logger.info("Max dedup retries reached, accepting anyway.")
            return q

    fallback = random.choice(FALLBACK_QUESTIONS)
    return {
        "id": str(uuid.uuid4()),
        "option_a": fallback["option_a"],
        "option_b": fallback["option_b"],
        "framing": fallback.get("framing", ""),
        "flavors": fallback.get("flavors", []),
    }


def _check_rate_limit(room: dict) -> bool:
    return (time.time() - room["last_generated_at"]) >= RATE_LIMIT_SECONDS


def _touch_rate_limit(room: dict):
    room["last_generated_at"] = time.time()


def _cancel_timer(room: dict):
    task = room.get("timer_task")
    if task and not task.done():
        task.cancel()
    room["timer_task"] = None


async def _auto_reveal(room_code: str, question_id: str):
    try:
        await asyncio.sleep(AUTO_REVEAL_SECONDS)
    except asyncio.CancelledError:
        return

    room = rooms.get(room_code)
    if not room:
        return
    if room.get("phase") != "question":
        return
    q = room.get("current_question") or {}
    if q.get("id") != question_id:
        return

    vote_counts = {"A": 0, "B": 0}
    for v in room["votes"].values():
        vote_counts[v] += 1

    room["phase"] = "reveal"
    room["timer_task"] = None
    if room["current_question"]:
        room["question_history"].append({
            **room["current_question"],
            "final_votes": vote_counts,
        })

    logger.info(f"Auto-reveal fired for room {room_code} question {question_id}")
    await broadcast(room, {
        "event": "reveal",
        "final_votes": vote_counts,
        "question": room["current_question"],
    })


def _start_timer(room: dict):
    _cancel_timer(room)
    room_code = room["room_code"]
    question_id = room["current_question"]["id"]
    room["timer_task"] = asyncio.create_task(
        _auto_reveal(room_code, question_id)
    )


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


class AcceptPreviewBody(BaseModel):
    host_id: str


def _broadcast_question(room: dict, question: dict) -> dict:
    return {
        "event": "question_ready",
        "question": question,
        "server_timestamp": int(time.time() * 1000),
    }


@app.post("/room/create")
async def create_room(body: CreateRoomBody):
    host_id = str(uuid.uuid4())
    room_code = generate_room_code()
    rooms[room_code] = make_room(room_code, host_id, body.host_name, body.flavors)
    return {"room_code": room_code, "host_id": host_id, "user_id": host_id}


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

    if not _check_rate_limit(room) and room["current_question"]:
        return {"status": "rate_limited", "question": room["current_question"]}

    _touch_rate_limit(room)
    room["phase"] = "question"
    room["votes"] = {}

    question = room.pop("preview_question", None) or await generate_question(
        room["flavors"], room["question_texts"]
    )
    _record_question(room, question)
    room["current_question"] = question

    _start_timer(room)
    await broadcast(room, _broadcast_question(room, question))
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
        _cancel_timer(room)
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

    if not _check_rate_limit(room) and room["current_question"]:
        room["votes"] = {}
        room["phase"] = "question"
        _start_timer(room)
        await broadcast(room, _broadcast_question(room, room["current_question"]))
        return {"status": "rate_limited", "question": room["current_question"]}

    _touch_rate_limit(room)
    room["votes"] = {}
    room["phase"] = "question"

    question = room.pop("preview_question", None) or await generate_question(
        room["flavors"], room["question_texts"]
    )
    _record_question(room, question)
    room["current_question"] = question

    _start_timer(room)
    await broadcast(room, _broadcast_question(room, question))
    return {"status": "next", "question": question}


@app.post("/room/{room_code}/end")
async def end_session(room_code: str, body: EndBody):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != body.host_id:
        raise HTTPException(status_code=403, detail="Only the host can end the session")
    _cancel_timer(room)
    room["phase"] = "ended"
    await broadcast(room, {"event": "session_ended"})
    return {"status": "ended"}


@app.get("/room/{room_code}/preview_question")
async def preview_question(room_code: str, host_id: str):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != host_id:
        raise HTTPException(status_code=403, detail="Only the host can preview questions")
    question = await generate_question(room["flavors"], room["question_texts"])
    room["preview_question"] = question
    return {"question": question}


@app.post("/room/{room_code}/accept_preview")
async def accept_preview(room_code: str, body: AcceptPreviewBody):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != body.host_id:
        raise HTTPException(status_code=403, detail="Only the host can accept a preview")
    if not room.get("preview_question"):
        raise HTTPException(status_code=400, detail="No preview question available")
    if not _check_rate_limit(room):
        raise HTTPException(status_code=429, detail="Rate limit: wait before generating another question")

    _touch_rate_limit(room)
    question = room.pop("preview_question")
    _record_question(room, question)
    room["current_question"] = question
    room["votes"] = {}
    room["phase"] = "question"
    _start_timer(room)
    await broadcast(room, _broadcast_question(room, question))
    return {"status": "accepted", "question": question}


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
        state = room_state(room)
        await websocket.send_json({"event": "room_state", "state": state})
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


# Serve built frontend — must come after all API routes
_dist = "frontend/dist"
_assets = f"{_dist}/assets"

if os.path.isdir(_assets):
    app.mount("/assets", StaticFiles(directory=_assets), name="assets")


@app.get("/", include_in_schema=False)
async def serve_root():
    index = f"{_dist}/index.html"
    if os.path.exists(index):
        return FileResponse(index)
    return {"detail": "Frontend not built. Run: cd frontend && npm run build"}


@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all(full_path: str):
    file_path = f"{_dist}/{full_path}"
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    index = f"{_dist}/index.html"
    if os.path.exists(index):
        return FileResponse(index)
    return {"detail": "Frontend not built. Run: cd frontend && npm run build"}
