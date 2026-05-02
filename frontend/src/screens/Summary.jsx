import { useRef } from 'react'
import { useRoom } from '../context/RoomContext.jsx'
import { useNavigate } from 'react-router-dom'
import './Summary.css'

function MiniBar({ pctA }) {
  return (
    <div
      className="sq-bar"
      role="img"
      aria-label={`${pctA}% chose option I, ${100 - pctA}% chose option II`}
    >
      <div className="sq-bar-a" style={{ width: `${pctA}%` }} />
      <div className="sq-bar-b" style={{ width: `${100 - pctA}%` }} />
    </div>
  )
}

function truncate(str, n) {
  if (!str) return ''
  return str.length > n ? str.slice(0, n).trimEnd() + '…' : str
}

export default function Summary() {
  const { roomState, setPhase, setRoomCode, setIsHost, setHostId, setRoomState } = useRoom()
  const navigate = useNavigate()
  const startRef = useRef(roomState?._sessionStart || Date.now())

  const history = roomState?.question_history || []
  const total = history.length
  const durationMs = Date.now() - startRef.current
  const minutes = Math.max(1, Math.round(durationMs / 60000))

  // Build philosophical profile from flavor tags
  const flavorVotes = {}
  const flavorSplitScore = {}
  history.forEach(q => {
    const a = q.final_votes?.A || 0
    const b = q.final_votes?.B || 0
    const t = a + b
    const closeness = t > 0 ? 1 - Math.abs(a - b) / t : 0
    ;(q.flavors || []).forEach(tag => {
      flavorVotes[tag] = (flavorVotes[tag] || 0) + t
      flavorSplitScore[tag] = (flavorSplitScore[tag] || 0) + closeness
    })
  })

  const topFlavors = Object.entries(flavorVotes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([tag]) => tag)

  const dividedFlavors = Object.entries(flavorSplitScore)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([tag]) => tag)

  function buildCopyText() {
    const lines = [
      'AGORA — Session Chronicle',
      `${total} question${total !== 1 ? 's' : ''} · ${minutes} minute${minutes !== 1 ? 's' : ''} together`,
      '',
    ]
    history.forEach((q, i) => {
      const a = q.final_votes?.A || 0
      const b = q.final_votes?.B || 0
      const t = a + b
      const pctA = t > 0 ? Math.round((a / t) * 100) : 50
      const pctB = 100 - pctA
      lines.push(`${i + 1}. ${q.framing || '(no framing)'}`)
      lines.push(`   I.  ${q.option_a}`)
      lines.push(`   II. ${q.option_b}`)
      lines.push(`   ${pctA}% · ${pctB}%`)
      lines.push('')
    })
    return lines.join('\n')
  }

  function copyChronicles() {
    navigator.clipboard.writeText(buildCopyText()).catch(() => {})
  }

  function handleNewGathering() {
    setPhase('lobby')
    setRoomCode(null)
    setIsHost(false)
    setHostId(null)
    setRoomState(null)
    navigate('/')
  }

  return (
    <div className="screen summary-screen">
      <div className="summary-inner">
        <h1 className="summary-heading">The Gathering Has Closed</h1>
        <p className="summary-sub muted">
          {total} {total === 1 ? 'question' : 'questions'} debated &middot; {minutes} {minutes === 1 ? 'minute' : 'minutes'} together
        </p>

        <div className="divider gold" />

        {/* Chronicle of Questions */}
        {history.length > 0 && (
          <section className="summary-chronicle" aria-label="Chronicle of Questions">
            <h2 className="summary-section-title">Chronicle of Questions</h2>
            <div className="chronicle-list">
              {history.map((q, i) => {
                const a = q.final_votes?.A || 0
                const b = q.final_votes?.B || 0
                const t = a + b
                const pctA = t > 0 ? Math.round((a / t) * 100) : 50
                const pctB = 100 - pctA
                const aligned = t > 0 && Math.max(a, b) / t >= 0.7
                return (
                  <div key={q.id || i} className="chronicle-entry">
                    {q.framing && (
                      <p className="chronicle-framing">{q.framing}</p>
                    )}
                    <div className="chronicle-options">
                      <span className="chr-opt chr-opt-a">I. {truncate(q.option_a, 60)}</span>
                      <span className="chr-opt chr-opt-b">II. {truncate(q.option_b, 60)}</span>
                    </div>
                    <div className="chronicle-split">
                      <span className="chr-pct chr-pct-a">{pctA}%</span>
                      <MiniBar pctA={pctA} />
                      <span className="chr-pct chr-pct-b">{pctB}%</span>
                      <span className={`chr-verdict ${aligned ? 'aligned' : 'divided'}`}>
                        {aligned ? 'Aligned' : 'Divided'}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </section>
        )}

        {/* Philosophical Profile */}
        {(topFlavors.length > 0 || dividedFlavors.length > 0) && (
          <section className="summary-profile" aria-label="Philosophical Profile">
            <div className="divider" />
            <h2 className="summary-section-title">Philosophical Profile</h2>
            {topFlavors.length > 0 && (
              <p className="profile-line">
                Your group leaned toward:{' '}
                <span className="profile-tags">{topFlavors.join(', ')}</span>
              </p>
            )}
            {dividedFlavors.length > 0 && (
              <p className="profile-line">
                Your deepest divisions were in:{' '}
                <span className="profile-tags">{dividedFlavors.join(', ')}</span>
              </p>
            )}
          </section>
        )}

        <div className="divider" />

        <div className="summary-actions">
          <button className="primary" onClick={handleNewGathering}>
            Begin a New Gathering
          </button>
          <button onClick={copyChronicles} aria-label="Copy plain-text summary of all questions to clipboard">
            Copy the Chronicles
          </button>
        </div>
      </div>
    </div>
  )
}
