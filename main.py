import os
import uuid
import json
import random
import logging
import time
import asyncio
import difflib
import httpx
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
import anthropic
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONSONANTS = "BCDFGHJKLMNPQRSTVWXYZ"
RATE_LIMIT_SECONDS = 5
DEDUP_HISTORY = 20
SIMILARITY_THRESHOLD = 0.80
AUTO_REVEAL_SECONDS = 90

rooms: dict = {}

with open("data/fallback_questions.json") as f:
    FALLBACK_QUESTIONS = json.load(f)

SYSTEM_PROMPT = """You are a philosophical dilemma architect in the tradition of Socratic dialogue, Kant, Parfit, and Nozick. Your sole function is to generate Would You Rather questions that force genuine reflection on first principles.

WHAT MAKES A QUESTION EARN ITS PLACE:
- Genuine asymmetry: the two options must trade off different things of real value, not the same thing at different magnitudes
- Philosophical stakes: the question must implicate something about identity, consciousness, justice, free will, meaning, time, power, knowledge, or what it means to be a person
- Imaginability: specific enough that the person can actually picture themselves in the scenario
- Divisibility: a thoughtful group of people would split roughly 40/60 or 50/50, not 95/5
- Tension legible in one sentence: the framing must name the exact trade-off being made

WHAT DISQUALIFIES A QUESTION:
- Shock value, body horror, graphic violence, or anything designed to disturb rather than illuminate
- Political figures, real people, or current events
- An obvious right answer that a person of average virtue would choose immediately
- Options that differ only in scale ("save 10 people or save 100")
- Lifestyle preference questions with no philosophical content ("would you rather live in a city or countryside")
- Anything reducible to pure preference with no defensible philosophical stakes

THE QUALITY BENCHMARK:
After reading the question, a thoughtful person should say: "Oh. That's actually hard."

---

BAD EXAMPLE (do not produce this):
option_a: "Be very rich"
option_b: "Be very famous"
Why it fails: no philosophical tension, pure preference, obvious answers based on personality type

BAD EXAMPLE (do not produce this):
option_a: "Always know when people are lying to you"
option_b: "Be able to lie perfectly without being detected"
Why it fails: overused framing, no genuine philosophical stakes beyond social utility

---

GOOD EXAMPLE — TARGET QUALITY:
{
  "option_a": "Live a life of complete moral consistency — every value you hold, you act on without exception — but remain unknown and unmourned when you die",
  "option_b": "Be celebrated as a moral exemplar by millions, shaping how they treat each other for generations, while privately knowing your life was riddled with hypocrisy",
  "framing": "Does moral worth reside in the character of a life as it is lived, or in the effects that life has on the world?",
  "flavors": ["Morality", "Meaning"]
}

GOOD EXAMPLE — TARGET QUALITY:
{
  "option_a": "Know with certainty exactly how and when you will die, but have no ability to change it",
  "option_b": "Have complete freedom over how you die but never know when — it could be today, it could be in seventy years",
  "framing": "Between certainty that forecloses hope and freedom that forecloses peace, which is the better relationship with your own finitude?",
  "flavors": ["Time", "Meaning"]
}

GOOD EXAMPLE — TARGET QUALITY:
{
  "option_a": "Retain every memory of your life but slowly lose all sense of who you are — your preferences, your personality, your values dissolve while the record remains intact",
  "option_b": "Lose all memory of your life but retain exactly who you are — your character, your values, your way of being in the world unchanged, but the events are gone",
  "framing": "Is personal identity constituted by the continuity of psychological states, or by the continuity of the experiential record?",
  "flavors": ["Consciousness", "Identity"]
}

GOOD EXAMPLE — TARGET QUALITY:
{
  "option_a": "Discover a scientific truth so powerful and dangerous that sharing it would probably destroy civilization — and publish it anyway, because truth belongs to everyone",
  "option_b": "Suppress that same truth forever, carrying it alone, because you believe the consequences of release outweigh any principle about the free flow of knowledge",
  "framing": "When knowledge and survival are in conflict, does epistemic duty have limits?",
  "flavors": ["Knowledge", "Science", "Morality"]
}

---

OUTPUT FORMAT:
Respond with ONLY a JSON object. No prose, no explanation, no markdown code fences, no preamble.

{
  "option_a": "...",
  "option_b": "...",
  "framing": "one precise sentence naming the philosophical tension between the two options",
  "flavors": ["1-3 tags chosen only from: Consciousness, Identity, Knowledge, Morality, Power, Time, Meaning, Science"]
}"""

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-5"


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
    """Record for dedup (existing) and for Claude context injection (new)."""
    combined = question["option_a"] + " " + question["option_b"]
    room["question_texts"].append(combined)
    if len(room["question_texts"]) > DEDUP_HISTORY:
        room["question_texts"].pop(0)
    room["question_history"].append({
        "framing": question.get("framing", ""),
        "flavors": question.get("flavors", []),
    })


def _parse_claude_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


async def _call_claude(flavors: list[str], question_history: list[dict], question_count: int) -> dict | None:
    """
    Generate a question via Claude.
    - Haiku for Q1-10, Sonnet for Q11+ (higher ceiling for long sessions)
    - temperature=1.0 for maximum conceptual and lexical diversity
    - Injects last 8 question framings so Claude avoids covered territory
    - Detects overused flavor domains and deprioritizes them
    """
    from collections import Counter

    model = SONNET_MODEL if question_count >= 10 else HAIKU_MODEL
    client = anthropic.AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    if flavors:
        flavor_str = ", ".join(flavors)
        flavor_instruction = f"Prioritize these philosophical themes without sacrificing question quality: {flavor_str}."
    else:
        flavor_instruction = "Explore any philosophical territory."

    flavor_counts = Counter()
    for q in question_history:
        for f in q.get("flavors", []):
            flavor_counts[f] += 1
    overused = [f for f, c in flavor_counts.most_common(2) if c >= 3]
    overuse_str = f"\nDeprioritize these themes — they have dominated this session already: {', '.join(overused)}." if overused else ""

    recent = question_history[-8:]
    if recent:
        framing_lines = "\n".join(f"  - {q['framing']}" for q in recent if q.get("framing"))
        history_block = f"""
The following questions have already been asked this session. Generate something conceptually distinct — different philosophical territory, different structure, different core tension:
{framing_lines}
"""
    else:
        history_block = ""

    user_message = f"""Generate a philosophical Would You Rather question.

{flavor_instruction}{overuse_str}
{history_block}
Return only the JSON object. No prose, no markdown, no explanation."""

    for attempt in range(2):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=600,
                temperature=1.0,
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
                continue
            break
        except Exception:
            break
    return None


async def generate_question(flavors: list[str], question_texts: list[str], question_history: list[dict]) -> dict:
    """
    Outer retry loop. Up to 3 attempts to get a non-duplicate question.
    question_history: list of {"framing": str, "flavors": list[str]} for context injection.
    """
    question_count = len(question_history)

    for attempt in range(3):
        q = await _call_claude(flavors, question_history, question_count)
        if q is None:
            break
        if not _is_duplicate(q, question_texts):
            return q
        if attempt == 2:
            fallback = random.choice(FALLBACK_QUESTIONS)
            return {
                "id": str(uuid.uuid4()),
                "option_a": fallback["option_a"],
                "option_b": fallback["option_b"],
                "framing": fallback["framing"],
                "flavors": fallback.get("flavors", []),
            }

    fallback = random.choice(FALLBACK_QUESTIONS)
    return {
        "id": str(uuid.uuid4()),
        "option_a": fallback["option_a"],
        "option_b": fallback["option_b"],
        "framing": fallback["framing"],
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
    allow_origins=[
        "https://agora-production-695a.up.railway.app",
        "https://*.discordsays.com",
        "http://localhost:5173",
        "http://localhost:8000",
    ],
    allow_origin_regex=r"https://.*\.discordsays\.com",
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
        room["flavors"], room["question_texts"], room["question_history"]
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

    room.pop("preview_question", None)
    question = await generate_question(room["flavors"], room["question_texts"], room["question_history"])
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


class SkipBody(BaseModel):
    host_id: str


@app.post("/room/{room_code}/skip")
async def skip_to_reveal(room_code: str, body: SkipBody):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != body.host_id:
        raise HTTPException(status_code=403, detail="Only the host can skip")
    if room["phase"] != "question":
        return {"status": "not_in_question_phase"}

    _cancel_timer(room)
    room["phase"] = "reveal"

    vote_counts = {"A": 0, "B": 0}
    for v in room["votes"].values():
        vote_counts[v] += 1

    await broadcast(room, {
        "event": "reveal",
        "final_votes": vote_counts,
        "question": room["current_question"],
    })
    return {"status": "skipped"}


@app.get("/room/{room_code}/preview_question")
async def preview_question(room_code: str, host_id: str):
    room_code = room_code.upper()
    if room_code not in rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = rooms[room_code]
    if room["host_id"] != host_id:
        raise HTTPException(status_code=403, detail="Only the host can preview questions")
    question = await generate_question(room["flavors"], room["question_texts"], room["question_history"])
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


@app.get("/api/token", include_in_schema=False)
async def token_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/")


class TokenRequest(BaseModel):
    code: str


@app.post("/api/token")
async def exchange_token(request: TokenRequest):
    """Exchange Discord OAuth2 authorization code for access token."""
    client_id = os.environ.get("DISCORD_CLIENT_ID", "")
    client_secret = os.environ.get("DISCORD_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        # Not configured for Discord — return gracefully
        return {"access_token": None}

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://discord.com/api/oauth2/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": request.code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if response.status_code != 200:
        return {"access_token": None, "error": "Token exchange failed"}

    data = response.json()
    return {"access_token": data.get("access_token")}


_PRIVACY_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Agora Privacy Policy</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400;1,600&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: #0a0a0a;
      color: #c8b97a;
      font-family: 'Crimson Text', Georgia, serif;
      font-size: 1.15rem;
      line-height: 1.75;
      padding: 3rem 1.5rem 5rem;
    }
    .container {
      max-width: 720px;
      margin: 0 auto;
    }
    h1 {
      font-family: 'Cinzel', serif;
      font-size: 2rem;
      font-weight: 700;
      color: #d4af37;
      letter-spacing: 0.04em;
      margin-bottom: 0.4rem;
    }
    .updated {
      font-size: 0.95rem;
      color: #6b5f3a;
      margin-bottom: 3rem;
      font-style: italic;
    }
    h2 {
      font-family: 'Cinzel', serif;
      font-size: 1.1rem;
      font-weight: 600;
      color: #d4af37;
      letter-spacing: 0.03em;
      margin-top: 2.2rem;
      margin-bottom: 0.6rem;
    }
    p {
      color: #c8b97a;
    }
    a {
      color: #d4af37;
      text-decoration: none;
      border-bottom: 1px solid #4a3f1f;
    }
    a:hover {
      border-bottom-color: #d4af37;
    }
    hr {
      border: none;
      border-top: 1px solid #1e1a10;
      margin: 3rem 0 0;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Agora Privacy Policy</h1>
    <p class="updated">Last updated: May 4, 2026</p>

    <h2>1. Overview</h2>
    <p>Agora is a multiplayer philosophical debate game. We are committed to protecting your privacy.</p>

    <h2>2. Data We Collect</h2>
    <p>When you use Agora via Discord, we temporarily receive your Discord username and user ID through the Discord OAuth2 flow. We do not store this data. All game state (rooms, votes, questions) is held in server memory and is permanently deleted when the session ends or the server restarts. We do not use cookies, analytics, or tracking of any kind.</p>

    <h2>3. Data We Do Not Collect</h2>
    <p>We do not collect email addresses, passwords, payment information, location data, or any personally identifiable information beyond what Discord provides during authentication.</p>

    <h2>4. Third-Party Services</h2>
    <p>Agora uses the Anthropic API to generate philosophical questions. No user data is sent to Anthropic &mdash; only the request for a question. Agora uses Discord's Embedded App SDK for in-voice-channel functionality, subject to Discord's own Privacy Policy.</p>

    <h2>5. Data Retention</h2>
    <p>No user data is retained. All session data is ephemeral and exists only in memory during an active game session.</p>

    <h2>6. Your Rights</h2>
    <p>Since we store no personal data, there is nothing to request deletion of. If you have questions, contact us at: <a href="mailto:jakemyguy@gmail.com">jakemyguy@gmail.com</a></p>

    <h2>7. Changes</h2>
    <p>We may update this policy. The date at the top reflects the latest revision.</p>

    <hr />
  </div>
</body>
</html>"""


@app.get("/privacy", include_in_schema=False)
async def privacy_policy():
    return HTMLResponse(content=_PRIVACY_HTML)


_TERMS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Agora Terms of Service</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400;1,600&display=swap" rel="stylesheet" />
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: #0a0a0a;
      color: #c8b97a;
      font-family: 'Crimson Text', Georgia, serif;
      font-size: 1.15rem;
      line-height: 1.75;
      padding: 3rem 1.5rem 5rem;
    }
    .container {
      max-width: 720px;
      margin: 0 auto;
    }
    h1 {
      font-family: 'Cinzel', serif;
      font-size: 2rem;
      font-weight: 700;
      color: #d4af37;
      letter-spacing: 0.04em;
      margin-bottom: 0.4rem;
    }
    .updated {
      font-size: 0.95rem;
      color: #6b5f3a;
      margin-bottom: 3rem;
      font-style: italic;
    }
    h2 {
      font-family: 'Cinzel', serif;
      font-size: 1.1rem;
      font-weight: 600;
      color: #d4af37;
      letter-spacing: 0.03em;
      margin-top: 2.2rem;
      margin-bottom: 0.6rem;
    }
    p {
      color: #c8b97a;
    }
    a {
      color: #d4af37;
      text-decoration: none;
      border-bottom: 1px solid #4a3f1f;
    }
    a:hover {
      border-bottom-color: #d4af37;
    }
    hr {
      border: none;
      border-top: 1px solid #1e1a10;
      margin: 3rem 0 0;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Agora Terms of Service</h1>
    <p class="updated">Last updated: May 4, 2026</p>

    <h2>1. Acceptance</h2>
    <p>By using Agora, you agree to these terms and Discord's Terms of Service at <a href="https://discord.com/terms">discord.com/terms</a>.</p>

    <h2>2. Use of Service</h2>
    <p>Agora is a game for entertainment and discussion. You must be at least 13 years old to use Discord and therefore Agora. You agree not to use Agora to harass, abuse, or harm other users.</p>

    <h2>3. Content</h2>
    <p>Questions are AI-generated for philosophical discussion. We are not responsible for how users interpret or respond to questions during gameplay.</p>

    <h2>4. Availability</h2>
    <p>Agora is provided as-is. We may change, pause, or discontinue the service at any time.</p>

    <h2>5. Limitation of Liability</h2>
    <p>Agora is a free service. We are not liable for any damages arising from use of the service.</p>

    <h2>6. Contact &amp; Reporting</h2>
    <p>To report issues or violations, contact: <a href="mailto:jakemyguy@gmail.com">jakemyguy@gmail.com</a></p>

    <hr />
  </div>
</body>
</html>"""


@app.get("/terms", include_in_schema=False)
async def terms_of_service():
    return HTMLResponse(content=_TERMS_HTML)


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
