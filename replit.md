# AGORA

Multiplayer philosophical "Would You Rather" — real-time, room-based, AI-generated dilemmas.

## Architecture

| Layer | Tech |
|---|---|
| Backend | Python FastAPI, port 8000 |
| Real-time | FastAPI WebSockets (built-in) |
| LLM | Anthropic `claude-3-5-haiku-20241022` |
| Frontend | React + Vite, port 5000 (not yet built) |
| Storage | In-memory Python dicts — no database, rooms expire on restart |

## Project Structure

```
agora/
├── main.py                        # FastAPI app: rooms, WebSockets, question engine
├── requirements.txt               # Python dependencies
├── data/
│   └── fallback_questions.json    # 10 hand-crafted fallback questions (used if Claude fails)
└── frontend/                      # React + Vite (to be built)
    └── src/
        ├── context/RoomContext.jsx
        └── screens/
            ├── Home.jsx
            ├── FlavorSelect.jsx
            ├── Lobby.jsx
            ├── Question.jsx
            ├── Reveal.jsx
            └── Summary.jsx
```

## Running

```bash
# Backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend (once built)
cd frontend && npm install && npm run dev
```

## Environment Variables

- `ANTHROPIC_API_KEY` — required for AI question generation. Falls back to `data/fallback_questions.json` if missing or API fails.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/room/create` | Create room, returns room_code + host_id |
| POST | `/room/join` | Join room by code |
| GET | `/room/{room_code}` | Get current room state |
| POST | `/room/{room_code}/start` | Host starts session, generates first question |
| POST | `/room/{room_code}/vote` | Submit vote A or B |
| POST | `/room/{room_code}/next` | Host advances to next question |
| POST | `/room/{room_code}/end` | Host ends session |
| WS | `/ws/{room_code}/{user_id}` | WebSocket for real-time events |

## WebSocket Events (server → client)

- `room_state` — full state snapshot on connect
- `user_joined` / `user_left` — presence updates
- `question_ready` — new question broadcasted to all
- `vote_update` — live vote counts as people vote
- `reveal` — final tally when all connected users have voted
- `session_ended` — host ended the game

## Room Code

4 uppercase consonants only (no vowels) to avoid accidental words. Example: `NZPY`, `YFJM`.
