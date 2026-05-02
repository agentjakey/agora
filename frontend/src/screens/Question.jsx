import { useState, useEffect, useRef } from 'react'
import { useRoom } from '../context/RoomContext.jsx'
import './Question.css'

const TIMER_SECONDS = 45

export default function Question() {
  const { roomCode, userId, roomState } = useRoom()
  const [voted, setVoted] = useState(null)
  const [timeLeft, setTimeLeft] = useState(TIMER_SECONDS)
  const timerRef = useRef(null)

  const question = roomState?.current_question
  const voteUpdate = roomState?._voteUpdate || { A: 0, B: 0, total: 0, voted_ids: [] }
  const connectedCount = Object.values(roomState?.users || {}).filter(u => u.connected).length

  useEffect(() => {
    setVoted(null)
    setTimeLeft(TIMER_SECONDS)
    clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) { clearInterval(timerRef.current); return 0 }
        return t - 1
      })
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [question?.id])

  async function castVote(choice) {
    if (voted) return
    setVoted(choice)
    try {
      await fetch(`/room/${roomCode}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, vote: choice }),
      })
    } catch {
      setVoted(null)
    }
  }

  if (!question) {
    return (
      <div className="screen">
        <p className="muted" style={{ fontStyle: 'italic' }}>The question is being prepared...</p>
      </div>
    )
  }

  const timerPct = (timeLeft / TIMER_SECONDS) * 100

  return (
    <div className="screen question-screen">
      <div className="question-inner">
        <p className="question-label muted">The Question</p>
        {question.framing && (
          <p className="question-framing">{question.framing}</p>
        )}

        <div className="options-row">
          <div
            className={`option option-a${voted === 'A' ? ' voted' : ''}${voted && voted !== 'A' ? ' dimmed' : ''}`}
            onClick={() => castVote('A')}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && castVote('A')}
          >
            <span className="option-numeral">I.</span>
            <p className="option-text">{question.option_a}</p>
          </div>

          <div
            className={`option option-b${voted === 'B' ? ' voted' : ''}${voted && voted !== 'B' ? ' dimmed' : ''}`}
            onClick={() => castVote('B')}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && castVote('B')}
          >
            <span className="option-numeral">II.</span>
            <p className="option-text">{question.option_b}</p>
          </div>
        </div>

        <div className="timer-bar-wrap">
          <div className="timer-bar" style={{ width: `${timerPct}%` }} />
        </div>

        <p className="question-tally muted">
          {voteUpdate.total} of {connectedCount} {connectedCount === 1 ? 'person has' : 'have'} deliberated
        </p>
      </div>
    </div>
  )
}
