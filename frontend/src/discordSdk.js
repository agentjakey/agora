import { DiscordSDK } from "@discord/embedded-app-sdk";

// Only initialize if running inside Discord's iframe
const isDiscord = window.location.hostname.endsWith(".discordsays.com");

export const discordSdk = isDiscord
  ? new DiscordSDK(import.meta.env.VITE_DISCORD_CLIENT_ID)
  : null;

export async function setupDiscordSdk() {
  if (!discordSdk) return null; // Not in Discord — skip silently

  await discordSdk.ready();

  const { code } = await discordSdk.commands.authorize({
    client_id: import.meta.env.VITE_DISCORD_CLIENT_ID,
    response_type: "code",
    state: "",
    prompt: "none",
    scope: ["identify", "guilds", "rpc.activities.write"],
  });

  const response = await fetch("/api/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });

  const { access_token } = await response.json();

  const auth = await discordSdk.commands.authenticate({ access_token });

  return auth;
}
