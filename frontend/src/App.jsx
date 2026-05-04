import { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import Home from './screens/Home.jsx'
import FlavorSelect from './screens/FlavorSelect.jsx'
import Room from './screens/Room.jsx'
import Footer from './components/Footer.jsx'
import { setupDiscordSdk } from './discordSdk'

export default function App() {
  const [discordAuth, setDiscordAuth] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    setupDiscordSdk()
      .then((auth) => {
        setDiscordAuth(auth)
        setReady(true)
      })
      .catch(() => {
        setReady(true)
      })
  }, [])

  if (!ready) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        backgroundColor: '#0a0a0a',
        color: '#d4af37',
        fontFamily: 'Cinzel, serif',
        fontSize: '1.5rem',
      }}>
        Entering the Agora...
      </div>
    )
  }

  return (
    <>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/create" element={<FlavorSelect />} />
        <Route path="/room/:code" element={<Room />} />
      </Routes>
      <Footer />
    </>
  )
}
