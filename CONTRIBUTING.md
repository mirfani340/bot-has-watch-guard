# Contributing

Thanks for contributing to.

## Development setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy env template and configure values:

   ```bash
   cp .env.example .env
   ```

3. Run locally:

   ```bash
   python3 bot.py
   ```

## Project conventions

- Core logic lives in `bot.py`.
- Keep channel responsibilities separate:
  - Layer 4: ping diagnostics only.
  - Layer 7: curl resolution check + screenshot flow.
- Extend parsing helpers (`extract_alert_url`, `extract_alert_host`, `is_down_alert`) before changing handlers.
- Keep blocking operations off the event loop (`asyncio.to_thread` for blocking I/O).

## Pull request expectations

- Keep changes focused and minimal.
- Update docs when behavior/configuration changes.
- Include sample alert payloads in PR description when modifying parsing logic.