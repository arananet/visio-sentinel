"""
Async Ollama client — sends frames to the local model, returns structured results.
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "home-security")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.80"))

_PROMPT = (
    "Who is in this image? Is this person a known family member? "
    "Reply with: NAME | known/unknown | confidence 0.0-1.0"
)
_PATTERN = re.compile(
    r"^(?P<name>[^|]+)\s*\|\s*(?P<status>known|unknown)\s*\|\s*confidence\s*(?P<conf>[0-9.]+)",
    re.IGNORECASE,
)


@dataclass
class AnalysisResult:
    person: str
    known: bool
    confidence: float
    raw_response: str
    timestamp: str
    error: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_response(text: str, timestamp: str) -> AnalysisResult:
    m = _PATTERN.match(text.strip())
    if not m:
        return AnalysisResult(
            person="unknown",
            known=False,
            confidence=0.0,
            raw_response=text,
            timestamp=timestamp,
            error="parse_failed",
        )
    name = m.group("name").strip()
    status = m.group("status").lower()
    conf = float(m.group("conf"))
    known = status == "known" and conf >= CONFIDENCE_THRESHOLD
    return AnalysisResult(
        person=name,
        known=known,
        confidence=conf,
        raw_response=text,
        timestamp=timestamp,
    )


async def analyze_frame(frame_b64: str) -> AnalysisResult:
    """
    Send a base64-encoded JPEG frame to Ollama and return a structured result.

    Never raises — error field is populated on failure.
    """
    timestamp = _now_iso()
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": _PROMPT,
        "images": [frame_b64],
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "")
            return _parse_response(raw, timestamp)
    except Exception as exc:
        logger.error("Ollama request failed: %s", exc)
        return AnalysisResult(
            person="unknown",
            known=False,
            confidence=0.0,
            raw_response="",
            timestamp=timestamp,
            error=str(exc),
        )


if __name__ == "__main__":
    import base64

    async def _demo() -> None:
        # Encode a 1x1 white JPEG as a smoke test.
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="JPEG")
        frame_b64 = base64.b64encode(buf.getvalue()).decode()
        result = await analyze_frame(frame_b64)
        print(result)

    asyncio.run(_demo())
