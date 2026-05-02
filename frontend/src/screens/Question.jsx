import { useState, useEffect, useRef } from 'react'
import { useRoom } from '../context/RoomContext.jsx'
import './Question.css'

const TIMER_SECONDS = 45

export default function Question() {
  const { roomCode, userId, roomState } = useRoom()
  const [voted, setVoted] = useState(null)
  const [hovered, setHovered] = useState(null)
  const [barWidth, setBarWidth] = useState(100)
  const [barDuration, setBarDuration] = useState(0)
  const [barColor, setBarColor] = useState('var(--accent)')

  const colorTimerRef = useRef(null)
  const startTimerRef = useRef(null)

  const question = roomState?.current_question
  const voteUpdate = roomState?._voteUpdate || { A: 0, B: 0, total: 0, voted_ids: [] }
  const connectedCount = Object.values(roomState?.users || {}).filter(u => u.connected).length
  const questionTimestamp = roomState?._questionTimestamp

  useEffect(() => {
    if (!question) return

    setVoted(null)
    setHovered(null)

    clearTimeout(colorTimerRef.current)
    clearTimeout(startTimerRef.current)

    // Calculate remaining time from server timestamp
    const now = Date.now()
    const elapsed = questionTimestamp ? Math.max(0, (now - questionTimestamp) / 1000) : 0
    const remaining = Math.max(0, TIMER_SECONDS - elapsed)

    // Snap bar to 100% with no transition
    setBarWidth(100)
    setBarDuration(0)
    setBarColor(remaining <= 10 ? '#b8580b' : 'var(--accent)')

    // After a frame, start the transition
    startTimerRef.current = setTimeout(() => {
      setBarDuration(remaining)
      setBarWidth(0)
    }, 50)

    // Color change at 10s remaining
    if (remaining > 10) {
      colorTimerRef.current = setTimeout(() => {
        setBarColor('#b8580b')
      }, (remaining - 10) * 1000)
    }

    return () => {
      clearTimeout(colorTimerRef.current)
      clearTimeout(startTimerRef.current)
    }
  }, [question?.id, questionTimestamp])

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

  const canHover = !voted

  return (
    <div className="screen question-screen">
      <div className="timer-top-bar">
        <div
          className="timer-top-fill"
          style={{
            width: `${barWidth}%`,
            transition: barDuration > 0 ? `width ${barDuration}s linear` : 'none',
            background: barColor,
          }}
        />
      </div>

      <div className="question-inner">
        <p className="question-label muted">The Question</p>
        {question.framing && (
          <p className="question-framing">{question.framing}</p>
        )}

        <div className="options-row">
          {/* Option A */}
          <div
            className={[
              'option option-a',
              voted === 'A' ? 'voted' : '',
              voted && voted !== 'A' ? 'dimmed' : '',
              canHover && hovered === 'A' ? 'hovered' : '',
            ].join(' ')}
            onClick={() => castVote('A')}
            onMouseEnter={() => canHover && setHovered('A')}
            onMouseLeave={() => setHovered(null)}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && castVote('A')}
          >
            <span className="option-numeral">I.</span>
            <p className="option-text">{question.option_a}</p>
            <span className="option-intent">
              {voted === 'A' ? 'You have spoken.' : canHover && hovered === 'A' ? 'You would choose this.' : ''}
            </span>
          </div>

          {/* Option B */}
          <div
            className={[
              'option option-b',
              voted === 'B' ? 'voted' : '',
              voted && voted !== 'B' ? 'dimmed' : '',
              canHover && hovered === 'B' ? 'hovered' : '',
            ].join(' ')}
            onClick={() => castVote('B')}
            onMouseEnter={() => canHover && setHovered('B')}
            onMouseLeave={() => setHovered(null)}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && castVote('B')}
          >
            <span className="option-numeral">II.</span>
            <p className="option-text">{question.option_b}</p>
            <span className="option-intent">
              {voted === 'B' ? 'You have spoken.' : canHover && hovered === 'B' ? 'You would choose this.' : ''}
            </span>
          </div>
        </div>

        <p className="question-tally muted">
          {voteUpdate.total} of {connectedCount} {connectedCount === 1 ? 'person has' : 'have'} deliberated
        </p>
      </div>
    </div>
  )
}
