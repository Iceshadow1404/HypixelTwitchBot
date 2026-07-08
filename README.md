# Twitch Bot for Hypixel SkyBlock Streams

A Twitch chat bot that answers Hypixel SkyBlock stat commands (skills, dungeons, slayers,
networth, ...) and automatically joins all live Minecraft streams with "Hypixel SkyBlock"
in the title.

Feel free to contact me on Discord "Iceshadow_" if you have any questions.

## Commands

Default prefix is `#`. Most commands accept `<ign> [profile]` and fall back to your linked
IGN (see `#link`).

- Skills: `#skills`/`#sa`, `#oskill` (overflow), `#skilllevel <skill>`, `#sblvl`
- Dungeons: `#cata`, `#classaverage`/`#ca`, `#secrets`, `#currdungeon`,
  `#rtca` (runs till class average), `#rtcl` (runs till class level), `#runstillcata`/`#rtc`
- Combat: `#kuudra`, `#slayer`, `#essence`
- Mining: `#hotm`, `#powder`, `#nucleus`
- Economy: `#bank`/`#purse`, `#networth`/`#nw`, `#auctions`/`#ah`
- Player: `#link <ign>`, `#unlink`, `#guild`, `#whatdoing`/`#wd`
- Server: `#mayor`, `#status`
- Fun: `#coinflip`, `#roll [min] [max]`, `#help`

## Architecture

- `bot/` — Python package (twitchio 2.x). Entry point: `python -m bot`.
- `networth.js` — small Node.js service wrapping [skyhelper-networth](https://www.npmjs.com/package/skyhelper-networth)
  on `localhost:3000` (`POST /calculate-networth`, `GET /health`).
- Both processes run in one container via `start.sh`.

## Configuration

All configuration comes from environment variables (locally via `.env`, see `.env.example`):

| Variable | Required | Description |
|---|---|---|
| `TWITCH_OAUTH_TOKEN` | yes | Bot account token (`oauth:...`) |
| `TWITCH_NICKNAME` | yes | Bot account username |
| `TWITCH_CHANNELS` | yes | Comma-separated channels the bot always joins |
| `TWITCH_CLIENT_ID` / `TWITCH_CLIENT_SECRET` | unless `LOCAL_MODE` | Dev app credentials for live-stream discovery |
| `HYPIXEL_API_KEY` | yes | From the Hypixel developer dashboard |
| `PREFIX` | no | Command prefix (default `#`) |
| `LOCAL_MODE` | no | `true` skips live-stream discovery/monitoring |
| `LOG_LEVEL` | no | `DEBUG`/`INFO`/`WARNING`/`ERROR` (default `INFO`) |
| `DATA_DIR` | no | Persistence dir for `user_links.json` (default `./data`, Docker `/config`) |
| `NODE_SERVICE_URL` | no | Networth service URL (default `http://localhost:3000`) |

## Self-hosting with Docker

```yaml
services:
  twitchbot:
    container_name: TwitchBot
    image: ghcr.io/iceshadow1404/hypixelskyblock:latest
    network_mode: bridge
    environment:
      - TWITCH_OAUTH_TOKEN=oauth:YOUR_OAUTH_TOKEN_HERE
      - TWITCH_NICKNAME=YOUR_BOT_TWITCH_NAME
      - TWITCH_CHANNELS=channel1,channel2,channel3
      - TWITCH_CLIENT_ID=YOUR_TWITCH_CLIENT_ID
      - TWITCH_CLIENT_SECRET=YOUR_TWITCH_CLIENT_SECRET
      - HYPIXEL_API_KEY=YOUR_HYPIXEL_API_KEY
      - TZ=Europe/Berlin
    volumes:
      - ./config:/config:rw   # persists user links
```

## Local development

Requires [uv](https://docs.astral.sh/uv/) and Node.js 18+.

```bash
uv sync                       # install Python deps
npm ci                        # install Node deps
cp .env.example .env          # fill in your tokens, set LOCAL_MODE=true
node networth.js &            # start the networth service
uv run python -m bot          # start the bot
```

Checks:

```bash
uv run ruff check bot tests
uv run pyrefly check
uv run pytest
```
