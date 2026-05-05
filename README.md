# AGORA
### *multiplayer philosophical would you rather - for people who ruin dinner*

**[Play Now →](https://agora-production-695a.up.railway.app/)** Built May 2, 2026 · Replit Buildathon /
**Now on [Discord](https://discord.com/oauth2/authorize?client_id=1500962399304552608) as a Verified Activity, Play with your friends today!**

---

## The Origin

My sister and I have this thing. Someone asks a would you rather at the dinner table and two hours later we're still there, cold food, everyone talking over each other, nobody agreeing on anything.

Not "would you rather fight a horse-sized duck" stuff. The kind of question where you pick an answer and then immediately need to explain yourself, you do, you explore a consequence that challenges your initial answer, then you're back at square one. Where someone says *"wait, but what if-"* and suddenly the whole table has a philosophy degree.

We built Agora because that time dilating experience should be shared, and shouldn't be limited by the amount of questions you can think of off the top of your head.

---

## What It Is

```
you and your friends join a room
an AI drops a dilemma designed to split you
everyone votes at the same time
the room reveals - 7 people chose one thing, 3 chose yours
now you have to explain yourself
```

No points. No leaderboard. No wrong answers. Just the conversation.

---

## The Questions

This is the whole product. Everything else is scaffolding for this.

> **Would you rather** spend your life building something that outlasts you
> but never see it finished - **or** complete something meaningful in your
> lifetime that disappears entirely the moment you die?

> **Would you rather** be able to fully understand every person you meet
> but no one can understand you - **or** be completely understood by
> everyone, but lose the capacity to understand others?

> **Would you rather** live in a world where every moral question has a
> correct, knowable answer - **or** one where morality is genuinely
> uncertain, but your choices are entirely your own?

A question earns its place if a thoughtful person reads it and says: *"Oh. That's actually hard."*

The AI is given exactly that instruction. Questions are generated fresh every round, tuned to whatever philosophical territory your group picks: identity, consciousness, time, morality, power, knowledge, meaning.

---

## How a Round Works

```
HOST                             GUESTS
────                             ──────
Create room → get code      →   Join with code
Pick your domains           →   Lobby fills up
Hit "Begin"                 →   Question appears simultaneously

                Vote ←──────────────→ Vote

                         ↓
               Live split bar animates
               "5 chose A  ·  3 chose B"
                         ↓
                Talk. Click Next.
                         ↓
               Next question drops.
```

At the end: a full chronicle of every question, every split, and your group's philosophical fingerprint across the session.

---

## Domains

| Domain | The territory |
|---|---|
| Consciousness & Identity | Who are you, really. What makes you *you*. |
| Knowledge & Perception | What can be known. What's worth knowing. |
| Morality & Justice | Right, wrong, and everything in between. |
| Power & Society | Who decides. Who pays. Who benefits. |
| Time & Existence | Finitude. Legacy. The shape of a life. |
| Science & Discovery | What we should pursue and what we shouldn't. |
| Meaning | Why any of it matters. |

Pick one. Pick all seven. The AI calibrates.

---

## Stack

| | |
|---|---|
| Backend | Python FastAPI |
| Real-time | WebSockets - the split reveal only works if it hits everyone simultaneously |
| Frontend | React + Vite |
| Questions | Anthropic Claude Haiku - ~1.5s per question, $0.000075 a pop |
| Hosting | Replit |

**No database.** Rooms are intentionally ephemeral. When the gathering ends, it's gone. This is a feature.

---

## Design

The app looks like a philosophical debate in antiquity, not a mobile game.

- Fonts: **Cinzel** (carved stone) + **Crimson Text** (manuscript)
- Colors: near-black background · warm parchment text · dark gold accents
- No emojis. No rounded corners. No gamification badges. No shadows.
- A faint Greek meander pattern behind the question screen at 4% opacity
- The constraint is the point - when the UI recedes, the question is all there is

---

## Run It Locally

```bash
git clone https://github.com/agentjakey/agora.git
cd agora

# backend
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=your_key_here" > .env
uvicorn main:app --reload

# frontend (new terminal)
cd frontend && npm install && npm run dev
```

---

## Project Structure

```
agora/
├── main.py                        # rooms, websockets, question engine
├── data/
│   └── fallback_questions.json    # 10 hand-crafted questions if the API goes down
└── frontend/
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

---

**Jacob Ortiz** - AI Researcher · UCSD Physics · Berkeley MIDS (Fall 2026)  
[github.com/agentjakey](https://github.com/agentjakey)

---

## Support

If Agora made for a better dinner table, you can buy me a coffee.
[ko-fi.com/agentjakey](https://ko-fi.com/agentjakey)

---

## License
MIT — see [LICENSE](LICENSE)
