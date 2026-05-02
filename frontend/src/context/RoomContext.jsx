import { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react'

const RoomContext = createContext(null)

export function RoomProvider({ children }) {
  const [roomCode, setRoomCode] = useState(null)
  const [userId, setUserId] = useState(() => {
    let id = localStorage.getItem('agora_user_id')
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem('agora_user_id', id)
    }
    return id
  })
  const [userName, setUserName] = useState(() => localStorage.getItem('agora_user_name') || '')
  const [isHost, setIsHost] = useState(false)
  const [hostId, setHostId] = useState(null)
  const [roomState, setRoomState] = useState(null)
  const [phase, setPhase] = useState('lobby')
  const [wsConnected, setWsConnected] = useState(false)

  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const reconnectAttempts = useRef(0)

  const connectWs = useCallback((code, uid) => {
    if (wsRef.current && wsRef.current.readyState <= 1) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/${code}/${uid}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setWsConnected(true)
      reconnectAttempts.current = 0
    }

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      handleWsMessage(msg)
    }

    ws.onclose = () => {
      setWsConnected(false)
      const delay = Math.min(2000 * (reconnectAttempts.current + 1), 10000)
      reconnectAttempts.current++
      reconnectTimer.current = setTimeout(() => connectWs(code, uid), delay)
    }

    ws.onerror = () => ws.close()
  }, [])

  const handleWsMessage = useCallback((msg) => {
    switch (msg.event) {
      case 'room_state':
        setRoomState(msg.state)
        setPhase(msg.state.phase)
        break

      case 'user_joined':
        setRoomState(prev => prev ? {
          ...prev,
          users: { ...prev.users, [msg.user.id]: { name: msg.user.name, connected: true } }
        } : prev)
        break

      case 'user_left':
        setRoomState(prev => prev ? {
          ...prev,
          users: {
            ...prev.users,
            [msg.user_id]: { ...(prev.users[msg.user_id] || {}), connected: false }
          }
        } : prev)
        break

      case 'question_ready':
        setRoomState(prev => prev ? {
          ...prev,
          current_question: msg.question,
          votes: {},
          phase: 'question',
          _voteUpdate: { A: 0, B: 0, total: 0, voted_ids: [] },
          _questionTimestamp: msg.server_timestamp || Date.now(),
        } : prev)
        setPhase('question')
        break

      case 'vote_update':
        setRoomState(prev => prev ? { ...prev, _voteUpdate: msg.votes } : prev)
        break

      case 'reveal':
        setRoomState(prev => prev ? {
          ...prev,
          phase: 'reveal',
          _finalVotes: msg.final_votes,
          current_question: msg.question,
        } : prev)
        setPhase('reveal')
        break

      case 'session_ended':
        setPhase('ended')
        setRoomState(prev => prev ? { ...prev, phase: 'ended' } : prev)
        break

      default:
        break
    }
  }, [])

  const disconnectWs = useCallback(() => {
    clearTimeout(reconnectTimer.current)
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
      wsRef.current = null
    }
    setWsConnected(false)
  }, [])

  const saveName = useCallback((name) => {
    setUserName(name)
    localStorage.setItem('agora_user_name', name)
  }, [])

  useEffect(() => () => clearTimeout(reconnectTimer.current), [])

  return (
    <RoomContext.Provider value={{
      roomCode, setRoomCode,
      userId,
      userName, saveName,
      isHost, setIsHost,
      hostId, setHostId,
      roomState, setRoomState,
      phase, setPhase,
      wsConnected,
      connectWs,
      disconnectWs,
    }}>
      {children}
    </RoomContext.Provider>
  )
}

export function useRoom() {
  const ctx = useContext(RoomContext)
  if (!ctx) throw new Error('useRoom must be used within RoomProvider')
  return ctx
}
