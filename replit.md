# AGORA

Multiplayer philosophical "Would You Rather" — real-time, room-based, AI-generated dilemmas.

## Architecture

| Layer | Tech |
|---|---|
| Backend | Python FastAPI, `localhost:8000` |
| Real-time | FastAPI WebSockets (built-in) |
| LLM | Anthropic `claude-haiku-4-5-20251001` |
| Frontend | React + Vite, `0.0.0.0:5000` (webview) |
| Storage | In-memory Python dicts — no database, rooms expire on restart |

## Running

Single command starts both services:

```bash
bash start.sh
```

- `uvicorn main:app --host localhost --port 8000` — backend API
- `npm --prefix frontend run dev` — Vite dev server on port 5000

The Vite proxy forwards `/room/*` and `/ws/*` to the backend automatically.

## Project Structure

```
agora/
├── main.py                        # FastAPI: rooms, WebSockets, question engine
├── requirements.txt               # Python deps
├── start.sh                       # Starts backend + frontend together
├── data/
│   └── fallback_questions.json    # 10 hand-crafted questions if Claude fails
└── frontend/
    ├── package.json
    ├── vite.config.js             # Proxy: /room + /ws → localhost:8000
    ├── index.html                 # Cinzel + Crimson Text fonts
    └── src/
        ├── main.jsx
        ├── App.jsx                # React Router: /, /create, /room/:code
        ├── index.css              # Design tokens, global styles
        ├── context/
        │   └── RoomContext.jsx    # Global state + WebSocket lifecycle
        └── screens/
            ├── Home.jsx           # Landing — Begin or Join a Gathering
            ├── FlavorSelect.jsx   # Host picks philosophical domains
            ├── Room.jsx           # Route wrapper — phase state machine
            ├── Lobby.jsx          # Waiting room with live user list
            ├── Question.jsx       # Vote screen with 45s timer
            ├── Reveal.jsx         # Animated split bar + results
            └── Summary.jsx        # Session recap with question history
```

## Environment Variables

- `ANTHROPIC_API_KEY` — stored in Replit Secrets, never in code. Falls back to `data/fallback_questions.json` if missing or API fails.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/room/create` | Create room → `room_code`, `host_id`, `user_id` |
| POST | `/room/join` | Join room by code |
| GET | `/room/{room_code}` | Get current room state |
| POST | `/room/{room_code}/start` | Host starts session, generates first question |
| POST | `/room/{room_code}/vote` | Submit vote A or B |
| POST | `/room/{room_code}/next` | Host advances to next question |
| POST | `/room/{room_code}/end` | Host ends session |
| WS | `/ws/{room_code}/{user_id}` | Real-time events |

## WebSocket Events (server → client)

| Event | When |
|---|---|
| `room_state` | Full snapshot on connect |
| `user_joined` / `user_left` | Presence changes |
| `question_ready` | New question broadcast to all |
| `vote_update` | Live counts as users vote |
| `reveal` | Final tally when all connected users voted |
| `session_ended` | Host ended the game |

## Design Language

- Fonts: **Cinzel** (headings, codes) + **Crimson Text** (body, questions)
- Palette: near-black bg `#0e0c09`, warm parchment text `#e8dfc0`, dark gold accent `#b8860b`
- No rounded corners >2px, no shadows, no emojis — borders and typography only
- 3% noise overlay on body for texture
