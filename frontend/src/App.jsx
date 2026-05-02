import { Routes, Route } from 'react-router-dom'
import Home from './screens/Home.jsx'
import FlavorSelect from './screens/FlavorSelect.jsx'
import Room from './screens/Room.jsx'
import Footer from './components/Footer.jsx'

export default function App() {
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
