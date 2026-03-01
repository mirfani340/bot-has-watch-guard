import asyncio
import logging
import os
import re
import shlex
import tempfile
from typing import Optional
from urllib.parse import urlparse

import discord
import requests


URL_REGEX = re.compile(r"https?://[^\s<>()\[\]{}\"']+", re.IGNORECASE)
HOST_REGEX = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b", re.IGNORECASE)
IPV4_REGEX = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
SNAP_ENDPOINT = "https://snap.llm.kaveenk.com/api/screenshot"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("watch-guard")


def load_dotenv_file(dotenv_path: str = ".env") -> None:
    dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), dotenv_path)

    if not os.path.exists(dotenv_path):
        return

    with open(dotenv_path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def extract_url_from_text(text: str) -> Optional[str]:
    match = URL_REGEX.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,;:!?)\"]")


def extract_host_from_text(text: str) -> Optional[str]:
    match = HOST_REGEX.search(text)
    if not match:
        return None
    return match.group(0).lower()


def extract_ipv4_from_text(text: str) -> Optional[str]:
    match = IPV4_REGEX.search(text)
    if not match:
        return None
    return match.group(0)


def collect_message_text_parts(message: discord.Message) -> list[str]:
    parts: list[str] = []

    if message.content:
        parts.append(message.content)

    for embed in message.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        if embed.url:
            parts.append(embed.url)
        if embed.footer and embed.footer.text:
            parts.append(embed.footer.text)
        if embed.author and embed.author.name:
            parts.append(embed.author.name)
        for field in embed.fields:
            if field.name:
                parts.append(field.name)
            if field.value:
                parts.append(field.value)

    return parts


def extract_alert_url(message: discord.Message) -> Optional[str]:
    combined = "\n".join(collect_message_text_parts(message))
    return extract_url_from_text(combined)


def extract_alert_host(message: discord.Message) -> Optional[str]:
    direct_url = extract_alert_url(message)
    if direct_url:
        parsed = urlparse(direct_url)
        if parsed.netloc:
            return parsed.netloc

    combined = "\n".join(collect_message_text_parts(message))
    host = extract_host_from_text(combined)
    if host:
        return host

    return extract_ipv4_from_text(combined)


def is_down_alert(message: discord.Message) -> bool:
    alert_text = "\n".join(collect_message_text_parts(message)).lower()

    up_markers = [
        "monitor is up",
        " is up:",
        " is up!",
        " is up ",
        "it was down for",
        "status: up",
        "✅",
    ]
    if any(marker in alert_text for marker in up_markers):
        return False

    down_markers = [
        "🔴",
        "monitor is down",
        "went down",
        " is down",
        "status: down",
        "❌",
    ]
    return any(marker in alert_text for marker in down_markers)


def get_domain(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or "unknown-domain"


async def run_command(command: list[str], timeout: int = 30) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return 124, "", f"Command timed out after {timeout}s"

    return process.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def format_command_result(command: list[str], code: int, stdout: str, stderr: str) -> str:
    command_str = " ".join(shlex.quote(part) for part in command)
    stdout_text = (stdout or "(empty)").strip()
    stderr_text = (stderr or "(empty)").strip()
    if len(stdout_text) > 1500:
        stdout_text = f"{stdout_text[:1500]}..."
    if len(stderr_text) > 800:
        stderr_text = f"{stderr_text[:800]}..."

    return (
        f"Command: `{command_str}`\n"
        f"Exit code: `{code}`\n"
        f"STDOUT:\n```\n{stdout_text}\n```\n"
        f"STDERR:\n```\n{stderr_text}\n```"
    )


async def run_ping_test(host: str) -> tuple[int, str, str, list[str]]:
    command = ["ping", "-c", "4", "-W", "2", host]
    code, stdout, stderr = await run_command(command, timeout=25)
    return code, stdout, stderr, command


async def run_curl_resolution_check(url: str) -> tuple[bool, int, str, str, list[str]]:
    command = [
        "curl",
        "-I",
        "--max-time",
        "12",
        "--connect-timeout",
        "6",
        "-L",
        url,
    ]
    code, stdout, stderr = await run_command(command, timeout=20)
    combined = f"{stdout}\n{stderr}".lower()
    unresolved = "could not resolve host" in combined or "name or service not known" in combined
    resolved = code == 0 and not unresolved
    return resolved, code, stdout, stderr, command


def fetch_screenshot(url: str, snap_key: str, output_path: str) -> None:
    headers = {
        "Authorization": f"Bearer {snap_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "full_page": True,
        "block_ads": True,
    }

    with requests.post(
        SNAP_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=40,
        stream=True,
    ) as response:
        if response.status_code == 429:
            raise RuntimeError("SnapService rate limit exceeded (429).")
        response.raise_for_status()

        with open(output_path, "wb") as file_obj:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)


class WatchGuardBot(discord.Client):
    def __init__(self, layer4_channel_id: int, layer7_channel_id: int, snap_key: str, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.layer4_channel_id = layer4_channel_id
        self.layer7_channel_id = layer7_channel_id
        self.snap_key = snap_key

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "n/a")
        if not self.intents.message_content:
            logger.warning(
                "Message Content intent is disabled. Uptime Kuma alert text may be hidden; "
                "enable it in Discord Developer Portal and set ENABLE_MESSAGE_CONTENT_INTENT=true."
            )

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot and message.author.id == self.user.id:
            return
        if message.channel.id not in {self.layer4_channel_id, self.layer7_channel_id}:
            return

        logger.info(
            "Received message in monitored channel: id=%s channel=%s author=%s webhook_id=%s content_len=%s embeds=%s",
            message.id,
            message.channel.id,
            getattr(message.author, "id", "n/a"),
            message.webhook_id,
            len(message.content or ""),
            len(message.embeds),
        )

        if not is_down_alert(message):
            logger.info("Message %s ignored: not detected as Down alert", message.id)
            return

        if message.channel.id == self.layer4_channel_id:
            await self.handle_layer4_alert(message)
            return

        if message.channel.id == self.layer7_channel_id:
            await self.handle_layer7_alert(message)
            return

    async def _notify_dev_admin(self, thread: discord.Thread, source_message: discord.Message, target: str) -> None:
        mention_text = "@Dev Admin"
        role = discord.utils.get(source_message.guild.roles, name="Dev Admin") if source_message.guild else None
        allowed_mentions = discord.AllowedMentions.none()

        if role:
            mention_text = role.mention
            allowed_mentions = discord.AllowedMentions(roles=True)

        await thread.send(
            f"🚨 {mention_text} there is downtime on `{target}`, sir. Please check immediately.",
            allowed_mentions=allowed_mentions,
        )

    async def _mark_alert_checked(self, source_message: discord.Message) -> None:
        for emoji in ("👀", "✅"):
            try:
                await source_message.add_reaction(emoji)
            except Exception:
                logger.exception("Failed to add reaction %s on message %s", emoji, source_message.id)

    async def _create_alert_thread(self, message: discord.Message, name: str) -> Optional[discord.Thread]:
        if message.thread:
            return message.thread

        try:
            return await message.create_thread(name=name)
        except Exception:
            logger.exception("Failed to create thread for message %s", message.id)
            return None

    async def handle_layer4_alert(self, message: discord.Message) -> None:
        host = extract_alert_host(message)
        if not host:
            logger.warning("Layer 4 down alert detected, but no host found in message %s", message.id)
            return

        thread_name = f"Down Alert: {host}"
        thread = await self._create_alert_thread(message, thread_name)
        if not thread:
            return

        await thread.send(f"Layer 4 alert detected for `{host}`. Running ping test...")

        code, stdout, stderr, command = await run_ping_test(host)
        result = format_command_result(command, code, stdout, stderr)

        if code == 0:
            await thread.send(f"Ping test succeeded for `{host}`.\n{result}")
        else:
            await thread.send(f"Ping test failed for `{host}`.\n{result}")

        await self._notify_dev_admin(thread, message, host)
        await self._mark_alert_checked(message)

    async def handle_layer7_alert(self, message: discord.Message) -> None:
        down_url = extract_alert_url(message)
        host = extract_alert_host(message)

        if not down_url and host:
            down_url = f"https://{host}"

        if not down_url:
            logger.warning("Layer 7 down alert detected, but no URL/host found in message %s", message.id)
            return

        domain = get_domain(down_url) if down_url.startswith(("http://", "https://")) else (host or "unknown-domain")
        thread_name = f"Down Alert: {domain}"
        thread = await self._create_alert_thread(message, thread_name)
        if not thread:
            return

        await thread.send(f"Layer 7 alert detected for: {down_url}\nRunning curl resolution check...")

        resolved, code, stdout, stderr, command = await run_curl_resolution_check(down_url)
        curl_result = format_command_result(command, code, stdout, stderr)

        if not resolved:
            await thread.send(
                f"Curl check indicates host is not resolved or unreachable. Screenshot skipped.\n{curl_result}"
            )
            await self._notify_dev_admin(thread, message, domain)
            await self._mark_alert_checked(message)
            return

        await thread.send(f"Curl check passed for {down_url}. Capturing screenshot in 5 seconds...")

        await asyncio.sleep(5)

        with tempfile.TemporaryDirectory() as tmp_dir:
            alert_path = os.path.join(tmp_dir, "alert.png")
            try:
                await asyncio.to_thread(fetch_screenshot, down_url, self.snap_key, alert_path)
                await thread.send(file=discord.File(alert_path, filename="alert.png"))
                await thread.send(f"Screenshot captured successfully.\n{curl_result}")
            except Exception as error:
                logger.exception("Screenshot request failed for URL: %s", down_url)
                await thread.send(
                    f"Could not capture screenshot right now ({error}). "
                    "This may be due to SnapService rate limits."
                )

        await self._notify_dev_admin(thread, message, domain)
        await self._mark_alert_checked(message)


def main() -> None:
    load_dotenv_file()

    token = os.getenv("DISCORD_TOKEN")
    snap_key = os.getenv("SNAPSERVICE_KEY")
    layer4_channel_id_raw = os.getenv("LAYER4_CHANNEL_ID")
    layer7_channel_id_raw = os.getenv("LAYER7_CHANNEL_ID")
    enable_message_content_intent = (
        os.getenv("ENABLE_MESSAGE_CONTENT_INTENT", "true").strip().lower() in {"1", "true", "yes", "on"}
    )

    if not token:
        raise RuntimeError("Missing environment variable: DISCORD_TOKEN")
    if not snap_key:
        raise RuntimeError("Missing environment variable: SNAPSERVICE_KEY")
    if not layer4_channel_id_raw:
        raise RuntimeError("Missing environment variable: LAYER4_CHANNEL_ID")
    if not layer7_channel_id_raw:
        raise RuntimeError("Missing environment variable: LAYER7_CHANNEL_ID")

    try:
        layer4_channel_id = int(layer4_channel_id_raw)
        layer7_channel_id = int(layer7_channel_id_raw)
    except ValueError as exc:
        raise RuntimeError("LAYER4_CHANNEL_ID and LAYER7_CHANNEL_ID must be integer Discord channel IDs") from exc

    intents = discord.Intents.default()
    intents.message_content = enable_message_content_intent

    client = WatchGuardBot(
        layer4_channel_id=layer4_channel_id,
        layer7_channel_id=layer7_channel_id,
        snap_key=snap_key,
        intents=intents,
    )
    client.run(token)


if __name__ == "__main__":
    main()