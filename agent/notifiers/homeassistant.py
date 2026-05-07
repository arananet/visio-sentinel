"""
Optional Home Assistant webhook notifier.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def send_event(result, priority: str) -> None:
    """
    POST a JSON event to HA_WEBHOOK_URL if HA_ENABLED=true.

    Silently skips if HA_ENABLED is false or HA_WEBHOOK_URL is unset.
    Never raises.
    """
    if os.getenv("HA_ENABLED", "false").lower() != "true":
        return

    webhook_url = os.getenv("HA_WEBHOOK_URL", "")
    if not webhook_url:
        logger.warning("HA_WEBHOOK_URL not set — skipping Home Assistant notification")
        return

    payload = {
        "person": result.person,
        "known": result.known,
        "confidence": result.confidence,
        "priority": priority,
        "timestamp": result.timestamp,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        logger.error("Home Assistant webhook failed: %s", exc)


if __name__ == "__main__":
    import asyncio
    from inference.analyzer import AnalysisResult

    async def _demo() -> None:
        result = AnalysisResult(
            person="edu",
            known=True,
            confidence=0.95,
            raw_response="",
            timestamp="2026-05-07T00:00:00Z",
        )
        await send_event(result, "INFO")

    asyncio.run(_demo())
