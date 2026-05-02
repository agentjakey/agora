import { useState, useEffect, useRef } from 'react'
import { useRoom } from '../context/RoomContext.jsx'
import './Reveal.css'

export default function Reveal() {
  const { roomCode, isHost, hostId, roomState } = useRoom()
  const [advancing, setAdvancing] = useState(false)

  // Animation state
  const [barA, setBarA] = useState(50)
  const [showPct, setShowPct] = useState(false)
  const [showFraming, setShowFraming] = useState(false)
  const [showControls, setShowControls] = useState(false)

  const timerRefs = useRef([])

  const question = roomState?.current_question
  const finalVotes = roomState?._finalVotes || { A: 0, B: 0 }
  const total = (finalVotes.A || 0) + (finalVotes.B || 0)
  const pctA = total > 0 ? Math.round((finalVotes.A / total) * 100) : 50
  const pctB = 100 - pctA

  useEffect(() => {
    // Clear any existing timers
    timerRefs.current.forEach(clearTimeout)
    timerRefs.current = []

    // Reset
    setBarA(50)
    setShowPct(false)
    setShowFraming(false)
    setShowControls(false)
    setAdvancing(false)

    // Step 1: after 100ms, animate bar to actual split (1.5s ease-out)
    timerRefs.current.push(setTimeout(() => setBarA(pctA), 100))

    // Step 2: after 1.6s (100 + 1500), fade in percentages
    timerRefs.current.push(setTimeout(() => setShowPct(true), 1600))

    // Step 3: after 2.1s (1600 + 500), fade in framing
    timerRefs.current.push(setTimeout(() => setShowFraming(true), 2100))

    // Step 4: after 2.5s, show controls
    timerRefs.current.push(setTimeout(() => setShowControls(true), 2500))

    return () => timerRefs.current.forEach(clearTimeout)
  }, [question?.id])

  async function handleNext() {
    if (!hostId || advancing) return
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

        {/* Animated split bar — starts 50/50, animates to actual */}
        <div className="reveal-split-bar">
          <div
            className="split-a"
            style={{
              width: `${barA}%`,
              transition: 'width 1.5s ease-out',
            }}
          />
          <div
            className="split-b"
            style={{
              width: `${100 - barA}%`,
              transition: 'width 1.5s ease-out',
            }}
          />
        </div>

        {/* Percentages — fade in after bar settles */}
        <div className={`reveal-percentages${showPct ? ' visible' : ''}`}>
          <span className="pct-a">{pctA}%</span>
          <span className="reveal-dot muted">·</span>
          <span className="pct-b">{pctB}%</span>
        </div>

        <div className={`reveal-vote-counts muted${showPct ? ' visible' : ''}`}>
          <span>{finalVotes.A} chose I</span>
          <span className="reveal-dot">·</span>
          <span>{finalVotes.B} chose II</span>
        </div>

        {/* Framing — fades in after percentages */}
        {question?.framing && (
          <p className={`reveal-framing${showFraming ? ' visible' : ''}`}>
            {question.framing}
          </p>
        )}

        {/* Option recap */}
        <div className={`reveal-options${showFraming ? ' visible' : ''}`}>
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

        {/* Controls — host vs guest */}
        {showControls && (
          isHost ? (
            <div className="reveal-actions">
              <button className="primary" onClick={handleNext} disabled={advancing}>
                {advancing ? 'Preparing...' : 'Next Question'}
              </button>
              <button className="reveal-end-btn" onClick={handleEnd}>
                End Gathering
              </button>
            </div>
          ) : (
            <p className="reveal-waiting">Awaiting the next question...</p>
          )
        )}
      </div>
    </div>
  )
}
