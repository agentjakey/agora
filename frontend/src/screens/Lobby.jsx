import { useState } from 'react'
import { useRoom } from '../context/RoomContext.jsx'
import NameModal from '../components/NameModal.jsx'
import './Lobby.css'

export default function Lobby() {
  const { roomCode, userId, isHost, hostId, roomState, userName } = useRoom()
  const [starting, setStarting] = useState(false)
  const [showModal, setShowModal] = useState(false)

  const users = roomState?.users || {}
  const flavors = roomState?.flavors || []
  const connectedUsers = Object.entries(users).filter(([, u]) => u.connected)

  async function handleBegin() {
    if (!hostId) return
    setStarting(true)
    try {
      await fetch(`/room/${roomCode}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host_id: hostId }),
      })
    } catch {
      setStarting(false)
    }
  }

  return (
    <div className="screen lobby-screen">
      {showModal && <NameModal onComplete={() => setShowModal(false)} />}

      <div className="lobby-inner">
        <p className="lobby-label muted">The Gathering</p>
        <h1 className="lobby-code">AGORA · {roomCode}</h1>
        <p className="lobby-share muted">Share this code with your companions.</p>

        <div className="divider" />

        <div className="lobby-users" role="list" aria-label="Connected participants">
          {connectedUsers.length === 0 && (
            <p className="muted" style={{ fontStyle: 'italic', fontSize: 16 }}>Awaiting companions...</p>
          )}
          {connectedUsers.map(([uid, user]) => (
            <div key={uid} className="lobby-user-row" role="listitem">
              <div
                className="lobby-user-initial"
                aria-hidden="true"
              >
                {user.name.charAt(0).toUpperCase()}
              </div>
              <span className="lobby-user-name">
                {user.name}
                {uid === userId && <span className="lobby-you"> (you)</span>}
                {uid === roomState?.host_id && <span className="lobby-host"> · host</span>}
              </span>
            </div>
          ))}
        </div>

        <p className="lobby-change-name muted">
          Entering as <strong>{userName}</strong> ·{' '}
          <button
            className="link-btn"
            onClick={() => setShowModal(true)}
            aria-label="Change your display name"
          >
            Not you? Change name
          </button>
        </p>

        {flavors.length > 0 && (
          <div className="lobby-flavors" aria-label="Selected philosophical domains">
            {flavors.map(f => (
              <span key={f} className="lobby-flavor-tag">{f}</span>
            ))}
          </div>
        )}

        <div className="divider" />

        {isHost ? (
          <div className="lobby-host-actions">
            <button
              className="primary"
              onClick={handleBegin}
              disabled={starting || connectedUsers.length < 1}
              aria-label="Begin the philosophical gathering"
            >
              {starting ? 'Opening the question...' : 'Begin'}
            </button>
            {connectedUsers.length < 2 && (
              <p className="muted" style={{ fontSize: 14, fontStyle: 'italic', marginTop: 10 }}>
                You may begin alone, or wait for others to join.
              </p>
            )}
          </div>
        ) : (
          <p className="muted lobby-waiting">Awaiting the host to begin...</p>
        )}
      </div>
    </div>
  )
}
