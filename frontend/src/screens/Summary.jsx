import { useRoom } from '../context/RoomContext.jsx'
import { useNavigate } from 'react-router-dom'
import './Summary.css'

export default function Summary() {
  const { roomCode, roomState } = useRoom()
  const navigate = useNavigate()

  const history = roomState?.question_history || []
  const total = history.length
  const splits = history.filter(q => {
    const a = q.final_votes?.A || 0
    const b = q.final_votes?.B || 0
    const t = a + b
    if (t === 0) return false
    const pct = Math.max(a, b) / t
    return pct < 0.8
  }).length
  const agreed = total - splits

  function copyLink() {
    const url = `${window.location.origin}/room/${roomCode}`
    navigator.clipboard.writeText(url).catch(() => {})
  }

  return (
    <div className="screen summary-screen">
      <div className="summary-inner">
        <h2 className="summary-heading">The Gathering Has Closed</h2>

        <div className="divider gold" />

        <div className="summary-stats">
          <div className="summary-stat">
            <span className="stat-number">{total}</span>
            <span className="stat-label">question{total !== 1 ? 's' : ''} debated</span>
          </div>
          <div className="summary-stat">
            <span className="stat-number">{splits}</span>
            <span className="stat-label">divided the room</span>
          </div>
          <div className="summary-stat">
            <span className="stat-number">{agreed}</span>
            <span className="stat-label">reached consensus</span>
          </div>
        </div>

        {history.length > 0 && (
          <div className="summary-history">
            <p className="summary-history-label muted">Questions debated</p>
            {history.map((q, i) => {
              const a = q.final_votes?.A || 0
              const b = q.final_votes?.B || 0
              const t = a + b
              const pctA = t > 0 ? Math.round((a / t) * 100) : 50
              const pctB = 100 - pctA
              return (
                <div key={q.id || i} className="summary-question">
                  <div className="summary-q-options">
                    <span className="sq-a">I. {q.option_a}</span>
                    <span className="sq-vs muted">vs.</span>
                    <span className="sq-b">II. {q.option_b}</span>
                  </div>
                  <div className="sq-split">
                    <span className="sq-pct-a">{pctA}%</span>
                    <div className="sq-bar">
                      <div className="sq-bar-a" style={{ width: `${pctA}%` }} />
                      <div className="sq-bar-b" style={{ width: `${pctB}%` }} />
                    </div>
                    <span className="sq-pct-b">{pctB}%</span>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <p className="summary-quote">
          "He who thinks he knows, knows nothing. He who knows he knows nothing, knows something."
        </p>

        <div className="summary-actions">
          <button className="primary" onClick={copyLink}>Copy Room Link</button>
          <button onClick={() => navigate('/')}>Return Home</button>
        </div>
      </div>
    </div>
  )
}
