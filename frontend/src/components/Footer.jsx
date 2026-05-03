import './Footer.css'

export default function Footer() {
  return (
    <footer className="site-footer" role="contentinfo">
      <span className="footer-left">Agora &middot; Built May 2, 2026</span>
      <a
        className="footer-support"
        href="https://ko-fi.com/agentjakey"
        target="_blank"
        rel="noopener noreferrer"
      >
        Support This Project
      </a>
      <a
        className="footer-right"
        href="https://github.com/agentjakey/agora"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="View source on GitHub"
      >
        Source
      </a>
    </footer>
  )
}
