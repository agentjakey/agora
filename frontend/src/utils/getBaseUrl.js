/**
 * Returns the correct base URL for API calls.
 * Inside Discord proxy: use relative paths.
 * In browser: use Railway URL directly.
 */
export function getBaseUrl() {
  if (window.location.hostname.endsWith(".discordsays.com")) {
    return "";
  }
  return "https://agora-production-695a.up.railway.app";
}

/**
 * Returns the correct WebSocket URL for a given room code.
 * Uses window.location.host so it works in both Discord proxy and direct browser.
 */
export function getWsUrl(roomCode) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/${roomCode}`;
}
