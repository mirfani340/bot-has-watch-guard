# Discord Watch Guard Bot

Python Discord bot that listens for downtime alerts from Uptime Kuma/UptimeRobot and handles Layer 4 and Layer 7 checks in separate Discord channels.

## Features

- Monitors 2 channels:
	- `LAYER4_CHANNEL_ID`: runs `ping` against the extracted host
	- `LAYER7_CHANNEL_ID`: runs `curl` resolution check, then takes screenshot
- Detects down alerts for Uptime Kuma/UptimeRobot and ignores UP status alerts
- Extracts URL/host from message content and embed fields
- Creates a public thread on the alert message named `Down Alert: [Domain]`
- Waits 5 seconds before screenshot capture for Layer 7
- Uploads screenshot as `alert.png` in the Layer 7 thread
- Handles SnapService errors gracefully (including rate limiting / `429`)

## Requirements

- Python 3.10+
- A Discord bot token with permission to:
  - Read message content
  - Create public threads
  - Send messages/files in threads
- SnapService API key

## Setup

1. Install dependencies:

	```bash
	pip install -r requirements.txt
	```

2. Create your environment file:

	```bash
	cp .env.example .env
	```

3. Fill in `.env` values:

	```env
	DISCORD_TOKEN=your_discord_bot_token
	SNAPSERVICE_KEY=your_snapservice_api_key
	LAYER4_CHANNEL_ID=123456789012345678
	LAYER7_CHANNEL_ID=987654321098765432
	ENABLE_MESSAGE_CONTENT_INTENT=true
	```

	- For Uptime Kuma/Uptime Robot alerts, keep `ENABLE_MESSAGE_CONTENT_INTENT=true`.
	- Enable **Message Content Intent** in Discord Developer Portal for your bot app.

4. Run the bot:

	```bash
	python3 bot.py
	```

## Notes on rate limits

SnapService allows only 2 screenshots/minute. When that limit is exceeded, the bot catches the error and posts a failure note in the thread instead of crashing.
