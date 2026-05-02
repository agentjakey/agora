import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRoom } from '../context/RoomContext.jsx'
import './Home.css'

export default function Home() {
  const navigate = useNavigate()
  const { saveName, userId, setRoomCode, setIsHost, setHostId, setRoomState, setPhase } = useRoom()

  const [mode, setMode] = useState(null)
  const [name, setName] = useState('')
  const [joinCode, setJoinCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleCreate() {
    if (!name.trim()) { setError('Enter your name to continue.'); return }
    saveName(name.trim())
    navigate('/create')
  }

  async function handleJoin() {
    if (!name.trim()) { setError('Enter your name to continue.'); return }
    if (!joinCode.trim()) { setError('Enter a gathering code.'); return }
    setError('')
    setLoading(true)

    try {
      const res = await fetch('/room/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_code: joinCode.trim().toUpperCase(),
          user_name: name.trim(),
          user_id: userId,
        }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Room not found.'); setLoading(false); return }
      saveName(name.trim())
      setRoomCode(data.room_code)
      setIsHost(false)
      setRoomState(data.room_state)
      setPhase(data.room_state.phase)
      navigate(`/room/${data.room_code}`)
    } catch {
      setError('Could not reach the server. Try again.')
      setLoading(false)
    }
  }

  return (
    <div className="screen home-screen">
      <div className="home-inner">
        <h1 className="home-title">AGORA</h1>
        <p className="home-subtitle">Where questions matter more than answers.</p>

        <div className="divider gold" />

        {!mode && (
          <div className="home-buttons">
            <button className="primary" onClick={() => setMode('create')}>Begin a Gathering</button>
            <button onClick={() => setMode('join')}>Join a Gathering</button>
          </div>
        )}

        {mode && (
          <div className="home-form">
            <input
              type="text"
              placeholder="Your name"
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && (mode === 'create' ? handleCreate() : handleJoin())}
              autoFocus
              maxLength={30}
            />

            {mode === 'join' && (
              <input
                type="text"
                placeholder="Gathering code (e.g. KZJM)"
                value={joinCode}
                onChange={e => setJoinCode(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && handleJoin()}
                maxLength={4}
                style={{ marginTop: 10 }}
              />
            )}

            {error && <p className="error-msg">{error}</p>}

            <div className="home-form-buttons">
              {mode === 'create'
                ? <button className="primary" onClick={handleCreate} disabled={loading}>Enter the Agora</button>
                : <button className="primary" onClick={handleJoin} disabled={loading}>{loading ? 'Joining...' : 'Join'}</button>
              }
              <button onClick={() => { setMode(null); setError('') }}>Back</button>
            </div>
          </div>
        )}

        <p className="home-quote">
          "The unexamined life is not worth living." — Socrates
        </p>
      </div>
    </div>
  )
}
