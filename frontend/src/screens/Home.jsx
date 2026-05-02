import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRoom } from '../context/RoomContext.jsx'
import NameModal from '../components/NameModal.jsx'
import Intro from '../components/Intro.jsx'
import './Home.css'

export default function Home() {
  const navigate = useNavigate()
  const { userName, userId, setRoomCode, setIsHost, setHostId, setRoomState, setPhase } = useRoom()

  const [introDone, setIntroDone] = useState(() => !!localStorage.getItem('seen_intro'))
  const [mode, setMode] = useState(null)
  const [joinCode, setJoinCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [pendingMode, setPendingMode] = useState(null)
  const [shareMsg, setShareMsg] = useState('')

  const handleIntroDone = useCallback(() => setIntroDone(true), [])

  function requestMode(m) {
    if (!userName) {
      setPendingMode(m)
      setShowModal(true)
    } else {
      setMode(m)
    }
  }

  function handleModalComplete() {
    setShowModal(false)
    setMode(pendingMode)
    setPendingMode(null)
  }

  function handleChangeName() {
    setPendingMode(mode)
    setShowModal(true)
  }

  async function handleJoin() {
    if (!joinCode.trim()) { setError('Enter a gathering code.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/room/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          room_code: joinCode.trim().toUpperCase(),
          user_name: userName,
          user_id: userId,
        }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || 'Room not found.'); setLoading(false); return }
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

  function handleShare() {
    const url = window.location.origin
    navigator.clipboard.writeText(url).then(() => {
      setShareMsg('Link copied to clipboard.')
      setTimeout(() => setShareMsg(''), 2000)
    }).catch(() => {
      setShareMsg('Copy: ' + url)
      setTimeout(() => setShareMsg(''), 4000)
    })
  }

  return (
    <>
      {!introDone && <Intro onDone={handleIntroDone} />}
      <div className="screen home-screen">
        {showModal && <NameModal onComplete={handleModalComplete} />}

        <div className="home-inner">
          <h1 className="home-title">AGORA</h1>
          <p className="home-subtitle">Where questions matter more than answers.</p>
          <div className="divider gold" />

          {!mode && (
            <>
              <div className="home-buttons">
                <button className="primary" onClick={() => requestMode('create')}>
                  Begin a Gathering
                </button>
                <button onClick={() => requestMode('join')}>
                  Join a Gathering
                </button>
              </div>
              {userName && (
                <p className="home-identity muted">
                  Entering as <strong>{userName}</strong> ·{' '}
                  <button className="link-btn" onClick={handleChangeName} aria-label="Change your name">
                    Not you?
                  </button>
                </p>
              )}
            </>
          )}

          {mode === 'create' && (
            <div className="home-form">
              <div className="home-who muted">
                Entering as <strong style={{ color: 'var(--text-primary)' }}>{userName}</strong> ·{' '}
                <button className="link-btn" onClick={handleChangeName} aria-label="Change your name">
                  Not you?
                </button>
              </div>
              <div className="home-form-buttons">
                <button className="primary" onClick={() => navigate('/create')}>
                  Enter the Agora
                </button>
                <button onClick={() => { setMode(null); setError('') }}>Back</button>
              </div>
            </div>
          )}

          {mode === 'join' && (
            <div className="home-form">
              <div className="home-who muted">
                Entering as <strong style={{ color: 'var(--text-primary)' }}>{userName}</strong> ·{' '}
                <button className="link-btn" onClick={handleChangeName} aria-label="Change your name">
                  Not you?
                </button>
              </div>
              <input
                type="text"
                placeholder="Gathering code (e.g. KZJM)"
                value={joinCode}
                onChange={e => setJoinCode(e.target.value.toUpperCase())}
                onKeyDown={e => e.key === 'Enter' && handleJoin()}
                maxLength={4}
                aria-label="Room code"
                autoFocus
              />
              {error && <p className="error-msg">{error}</p>}
              <div className="home-form-buttons">
                <button className="primary" onClick={handleJoin} disabled={loading}>
                  {loading ? 'Joining...' : 'Join'}
                </button>
                <button onClick={() => { setMode(null); setError('') }}>Back</button>
              </div>
            </div>
          )}

          <p className="home-quote">
            "The unexamined life is not worth living." — Socrates
          </p>

          <div className="home-share">
            <button className="link-btn" onClick={handleShare} aria-label="Copy link to share Agora">
              Share Agora
            </button>
            {shareMsg && <span className="share-confirm" role="status">{shareMsg}</span>}
          </div>
        </div>
      </div>
    </>
  )
}
