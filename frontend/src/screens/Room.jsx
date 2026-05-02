import { useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useRoom } from '../context/RoomContext.jsx'
import Lobby from './Lobby.jsx'
import Question from './Question.jsx'
import Reveal from './Reveal.jsx'
import Summary from './Summary.jsx'

export default function Room() {
  const { code } = useParams()
  const navigate = useNavigate()
  const {
    userId, roomCode, setRoomCode,
    connectWs, disconnectWs,
    phase, setRoomState, setPhase,
    isHost, setIsHost, setHostId,
  } = useRoom()

  const sessionStartRef = useRef(Date.now())

  useEffect(() => {
    if (!code) { navigate('/'); return }
    const upperCode = code.toUpperCase()
    setRoomCode(upperCode)
    sessionStartRef.current = Date.now()

    async function init() {
      try {
        const res = await fetch(`/room/${upperCode}`)
        if (!res.ok) { navigate('/'); return }
        const data = await res.json()
        data._sessionStart = sessionStartRef.current
        setRoomState(data)
        setPhase(data.phase)
        if (data.host_id === userId) {
          setIsHost(true)
          setHostId(data.host_id)
        }
      } catch {
        navigate('/')
        return
      }
      connectWs(upperCode, userId)
    }

    init()
    return () => { disconnectWs() }
  }, [code])

  switch (phase) {
    case 'lobby':    return <Lobby />
    case 'question': return <Question />
    case 'reveal':   return <Reveal />
    case 'ended':    return <Summary />
    default:         return <Lobby />
  }
}
