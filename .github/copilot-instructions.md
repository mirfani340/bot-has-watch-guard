# Copilot Instructions for `bot-has-watch-guard`

## Project shape and intent
- This is a **single-process Discord bot** focused on downtime alert handling.
- Core implementation is centralized in `bot.py`; there is no package layout yet.
- The bot listens to **two Discord channels** with different workflows:
  - `LAYER4_CHANNEL_ID`: run ping diagnostics for host/IP alerts.
  - `LAYER7_CHANNEL_ID`: run curl resolution check, then screenshot via SnapService.

## Runtime flow (read before changing behavior)
- Entry point: `main()` in `bot.py`.
- Config loading: `load_dotenv_file()` reads `.env` directly (no `python-dotenv` dependency).
- Message routing: `WatchGuardBot.on_message()` filters monitored channels, then dispatches:
  - `handle_layer4_alert()` for Layer 4.
  - `handle_layer7_alert()` for Layer 7.
- Both flows create a thread on the source alert message (`message.create_thread(...)`), notify Dev Admin, then react with 👀 and ✅.

## Alert parsing conventions in this repo
- Reuse existing extractors before adding new regex:
  - `extract_alert_url()` (URLs from message content + embed parts)
  - `extract_alert_host()` (URL host → domain → IPv4 fallback)
- Keep down/up detection centralized in `is_down_alert()`.
- Current pattern includes Uptime Kuma/UptimeRobot style alerts and explicitly ignores UP notifications.
- If adding new monitor formats, update only parser/detector helpers first, not channel handlers.

## External integrations and boundaries
- Discord API via `discord.py` (`discord.Client`, threads, reactions, role mention by name `Dev Admin`).
- Network diagnostics are shell commands executed asynchronously:
  - ping: `ping -c 4 -W 2 <host>`
  - curl: `curl -I --max-time 12 --connect-timeout 6 -L <url>`
- Screenshot API: `https://snap.llm.kaveenk.com/api/screenshot` in `fetch_screenshot()`.
- SnapService is rate-limited; failures (including 429) must remain non-fatal and user-visible in thread.

## Change rules for agents
- Preserve channel-specific responsibilities (L4 = ping only, L7 = curl + screenshot).
- Keep blocking I/O off the event loop (use `asyncio.to_thread(...)` like existing screenshot call).
- Keep command output formatting through `format_command_result()` for consistent thread logs.
- Keep the 5-second delay before Layer 7 screenshot capture (`asyncio.sleep(5)`).
- Do not hardcode secrets; use env vars from `.env.example`.

## Developer workflow in this repo
- Install: `pip install -r requirements.txt`
- Run: `python3 bot.py`
- Required env vars (see `.env.example`):
  - `DISCORD_TOKEN`, `SNAPSERVICE_KEY`, `LAYER4_CHANNEL_ID`, `LAYER7_CHANNEL_ID`
  - `ENABLE_MESSAGE_CONTENT_INTENT=true` is expected for webhook alert text parsing
- There are no formal tests yet; validate changes by posting real/simulated DOWN and UP alerts in both channels.