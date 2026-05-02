import { useState, useEffect, useRef } from 'react'
import { useRoom } from '../context/RoomContext.jsx'
import './NameModal.css'

export default function NameModal({ onComplete }) {
  const { saveName } = useRoom()
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const inputRef = useRef(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  function handleSubmit() {
    const trimmed = value.trim()
    if (!trimmed) { setError('A name is required to enter.'); return }
    saveName(trimmed)
    onComplete(trimmed)
  }

  return (
    <div className="name-modal-overlay" role="dialog" aria-modal="true" aria-label="Enter your name">
      <div className="name-modal-card">
        <h2 className="name-modal-heading">Who enters the Agora?</h2>
        <div className="divider gold" />
        <input
          ref={inputRef}
          type="text"
          className="name-modal-input"
          placeholder="Your name"
          value={value}
          maxLength={24}
          onChange={e => { setValue(e.target.value); setError('') }}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          aria-label="Your name"
        />
        {error && <p className="error-msg">{error}</p>}
        <button className="primary name-modal-btn" onClick={handleSubmit}>
          Enter
        </button>
      </div>
    </div>
  )
}
