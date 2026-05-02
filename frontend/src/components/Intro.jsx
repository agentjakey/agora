import { useEffect } from 'react'
import './Intro.css'

export default function Intro({ onDone }) {
  useEffect(() => {
    const t = setTimeout(() => {
      localStorage.setItem('seen_intro', '1')
      onDone()
    }, 2600)
    return () => clearTimeout(t)
  }, [onDone])

  function skip() {
    localStorage.setItem('seen_intro', '1')
    onDone()
  }

  return (
    <div className="intro-overlay" aria-live="polite" aria-label="Intro animation">
      <button className="intro-skip" onClick={skip} aria-label="Skip intro animation">
        Skip
      </button>
      <p className="intro-text">In the beginning, there was a question.</p>
    </div>
  )
}
