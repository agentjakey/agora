import { useState, useEffect } from 'react'
import { useRoom } from '../context/RoomContext.jsx'
import './Reveal.css'

export default function Reveal() {
  const { roomCode, isHost, hostId, roomState } = useRoom()
  const [barA, setBarA] = useState(0)
  const [advancing, setAdvancing] = useState(false)

  const question = roomState?.current_question
  const finalVotes = roomState?._finalVotes || { A: 0, B: 0 }
  const total = (finalVotes.A || 0) + (finalVotes.B || 0)
  const pctA = total > 0 ? Math.round((finalVotes.A / total) * 100) : 50
  const pctB = 100 - pctA

  useEffect(() => {
    const t = setTimeout(() => setBarA(pctA), 80)
    return () => clearTimeout(t)
  }, [pctA])

  async function handleNext() {
    if (!hostId) return
    setAdvancing(true)
    try {
      await fetch(`/room/${roomCode}/next`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host_id: hostId }),
      })
    } catch {
      setAdvancing(false)
    }
  }

  async function handleEnd() {
    if (!hostId) return
    try {
      await fetch(`/room/${roomCode}/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host_id: hostId }),
      })
    } catch {}
  }

  return (
    <div className="screen reveal-screen">
      <div className="reveal-inner">
        <p className="reveal-label muted">The Verdict</p>

        <div className="reveal-split-bar">
          <div
            className="split-a"
            style={{ width: `${barA}%` }}
          />
          <div
            className="split-b"
            style={{ width: `${100 - barA}%` }}
          />
        </div>

        <div className="reveal-percentages">
          <span className="pct-a">{pctA}%</span>
          <span className="reveal-dot muted">·</span>
          <span className="pct-b">{pctB}%</span>
        </div>

        <div className="reveal-vote-counts muted">
          <span>{finalVotes.A} chose I</span>
          <span className="reveal-dot">·</span>
          <span>{finalVotes.B} chose II</span>
        </div>

        {question?.framing && (
          <p className="reveal-framing">{question.framing}</p>
        )}

        <div className="reveal-options">
          <div className="reveal-option reveal-option-a">
            <span className="reveal-option-numeral">I.</span>
            <p>{question?.option_a}</p>
          </div>
          <div className="reveal-option reveal-option-b">
            <span className="reveal-option-numeral">II.</span>
            <p>{question?.option_b}</p>
          </div>
        </div>

        <div className="divider" />

        {isHost ? (
          <div className="reveal-actions">
            <button className="primary" onClick={handleNext} disabled={advancing}>
              {advancing ? 'Preparing...' : 'Next Question'}
            </button>
            <button onClick={handleEnd}>End Gathering</button>
          </div>
        ) : (
          <p className="muted reveal-waiting">Awaiting the next question...</p>
        )}
      </div>
    </div>
  )
}
