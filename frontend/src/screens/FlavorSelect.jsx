import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRoom } from '../context/RoomContext.jsx'
import './FlavorSelect.css'

const FLAVORS = [
  { id: 'Consciousness', label: 'Consciousness & Identity', desc: 'Who are you, really. What makes you you across time, memory, and change.' },
  { id: 'Knowledge', label: 'Knowledge & Perception', desc: 'What can be known. What is worth knowing. The limits of the knowable.' },
  { id: 'Morality', label: 'Morality & Justice', desc: 'Right, wrong, and the vast gray country between them.' },
  { id: 'Power', label: 'Power & Society', desc: 'Who decides. Who pays. Who benefits. The architecture of authority.' },
  { id: 'Time', label: 'Time & Existence', desc: 'Finitude. Legacy. The shape of a life and what remains.' },
  { id: 'Meaning', label: 'Meaning', desc: 'Why any of it matters. Whether it has to. What we do if it does not.' },
]

export default function FlavorSelect() {
  const navigate = useNavigate()
  const { userId, userName, setRoomCode, setIsHost, setHostId, setRoomState, setPhase } = useRoom()
  const [selected, setSelected] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function toggle(id) {
    setSelected(prev => prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id])
  }

  async function handleEnter() {
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/room/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host_name: userName || 'Host',
          flavors: selected,
        }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Could not create room.'); setLoading(false); return }

      setRoomCode(data.room_code)
      setIsHost(true)
      setHostId(data.host_id)

      const roomRes = await fetch(`/room/${data.room_code}`)
      const roomData = await roomRes.json()
      setRoomState(roomData)
      setPhase(roomData.phase)

      navigate(`/room/${data.room_code}`)
    } catch {
      setError('Could not reach the server.')
      setLoading(false)
    }
  }

  return (
    <div className="screen flavor-screen">
      <div className="flavor-inner">
        <h2 className="flavor-heading">What shall we contemplate?</h2>
        <p className="flavor-sub muted">
          Select one or more domains. Your questions will be drawn from these wells.
        </p>

        <div className="divider" />

        <div className="flavor-grid">
          {FLAVORS.map(f => (
            <div
              key={f.id}
              className={`flavor-card${selected.includes(f.id) ? ' selected' : ''}`}
              onClick={() => toggle(f.id)}
            >
              <h4 className="flavor-card-title">{f.label}</h4>
              <p className="flavor-card-desc">{f.desc}</p>
            </div>
          ))}
        </div>

        {error && <p className="error-msg" style={{ textAlign: 'center', marginTop: 16 }}>{error}</p>}

        <div className="flavor-actions">
          <button onClick={() => navigate('/')}>Back</button>
          <button className="primary" onClick={handleEnter} disabled={loading}>
            {loading ? 'Opening the Agora...' : 'Enter the Agora'}
          </button>
        </div>

        {selected.length === 0 && (
          <p className="muted" style={{ textAlign: 'center', fontSize: 14, marginTop: 12, fontStyle: 'italic' }}>
            No selection — all domains will be considered.
          </p>
        )}
      </div>
    </div>
  )
}
