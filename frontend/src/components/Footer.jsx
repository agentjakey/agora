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
      <div className="footer-links">
        <a className="footer-right" href="/privacy">Privacy</a>
        <a className="footer-right" href="/terms">Terms</a>
        <a
          className="footer-right"
          href="https://github.com/agentjakey/agora"
          target="_blank"
          rel="noopener noreferrer"
          aria-label="View source on GitHub"
        >
          Source
        </a>
        &middot;
        <a
          className="footer-right"
          href="https://discord.com/oauth2/authorize?client_id=1500962399304552608"
          target="_blank"
          rel="noopener noreferrer"
        >
          Discord
        </a>
      </div>
    </footer>
  )
}
