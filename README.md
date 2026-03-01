# bot-has-watch-guard

Discord downtime assistant bot for Uptime Kuma/UptimeRobot alerts.

## What it does

- Monitors two Discord channels with different incident workflows:
	- `LAYER4_CHANNEL_ID`: run `ping` diagnostics for host/IP alerts.
	- `LAYER7_CHANNEL_ID`: run `curl` resolution check, then capture screenshot.
- Parses alert text from both message content and embed parts (title/description/fields).
- Handles DOWN signals and ignores UP notifications.
- Creates a public thread on the alert message: `Down Alert: [target]`.
- Mentions `Dev Admin` in the thread and reacts on the source message with `👀` and `✅` after checks.

## Architecture snapshot

- Entry point: `main()` in `bot.py`
- Runtime class: `WatchGuardBot(discord.Client)`
- Routing: `on_message()` -> `handle_layer4_alert()` or `handle_layer7_alert()`
- External calls:
	- `ping -c 4 -W 2 <host>`
	- `curl -I --max-time 12 --connect-timeout 6 -L <url>`
	- SnapService API: `https://snap.llm.kaveenk.com/api/screenshot`

## Requirements

- Python 3.10+
- Discord bot with permissions:
	- Read message content
	- Create public threads
	- Send messages/files in threads
	- Add reactions
- SnapService API key

## Setup

1. Install dependencies:

	 ```bash
	 pip install -r requirements.txt
	 ```

2. Copy env template:

	 ```bash
	 cp .env.example .env
	 ```

3. Configure `.env`:

	 ```env
	 DISCORD_TOKEN=your_discord_bot_token
	 SNAPSERVICE_KEY=your_snapservice_api_key
	 LAYER4_CHANNEL_ID=123456789012345678
	 LAYER7_CHANNEL_ID=987654321098765432
	 ENABLE_MESSAGE_CONTENT_INTENT=true
	 ```

4. Enable **Message Content Intent** in Discord Developer Portal.

5. Run:

	 ```bash
	 python3 bot.py
	 ```

## Operational notes

- Layer 7 applies a 5-second delay before screenshot capture.
- SnapService is rate-limited (~2/min); failures (including `429`) are handled without crashing.
- There are no automated tests yet; validate using simulated DOWN/UP alerts in both channels.

## Public mirror policy

- **GitLab** is the source-of-truth repository and includes `.github/`.
- **GitHub** is a public mirror branch that excludes `.github/`.
- Publish flow is scripted in `scripts/publish_github_public.sh` and documented in `docs/MIRRORING.md`.

## Security

- Never commit `.env` or real tokens.
- If secrets were ever committed historically, rotate them and rewrite history before public release.
- Report vulnerabilities via `SECURITY.md`.
