"""
Telegram Bot notifier — sends text alerts and optional snapshot images.
"""

import logging
import os

from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)

_PRIORITY_PREFIX = {
    "INFO": "[INFO]",
    "WARNING": "[WARNING ⚠️]",
    "CRITICAL": "[CRITICAL 🚨]",
    "ERROR": "[ERROR]",
}


async def send_alert(message: str, snapshot_path: str | None, priority: str) -> None:
    """
    Send a text alert to the configured Telegram chat.

    If snapshot_path is provided and exists, attaches it as a photo.
    Never raises — failures are logged and swallowed to protect the agent loop.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing)")
        return

    prefix = _PRIORITY_PREFIX.get(priority, f"[{priority}]")
    full_message = f"{prefix} {message}"

    try:
        bot = Bot(token=token)
        if snapshot_path and os.path.exists(snapshot_path):
            with open(snapshot_path, "rb") as photo:
                await bot.send_photo(chat_id=chat_id, photo=photo, caption=full_message)
        else:
            await bot.send_message(chat_id=chat_id, text=full_message)
    except TelegramError as exc:
        logger.error("Telegram send failed: %s", exc)
    except Exception as exc:
        logger.error("Telegram unexpected error: %s", exc)


if __name__ == "__main__":
    import asyncio

    async def _demo() -> None:
        await send_alert("Test alert from visio-sentinel", None, "INFO")

    asyncio.run(_demo())
