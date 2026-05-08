"""
Main async daemon: sampler → analyzer → rules → log → notify.
"""

import asyncio
import base64
import json
import logging
import logging.handlers
import os
import re
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from dotenv import load_dotenv

load_dotenv()

from inference.analyzer import AnalysisResult, analyze_frame
from inference.sampler import frame_stream
from agent.notifiers.telegram import send_alert
from agent.notifiers.homeassistant import send_event

# ── Logging setup ──────────────────────────────────────────────────────────────

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        return json.dumps(payload)


def _setup_logging(log_path: str) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Console: plain text
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root.addHandler(ch)
    # File: JSON lines
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path)
    fh.setFormatter(_JsonFormatter())
    root.addHandler(fh)


logger = logging.getLogger(__name__)

# ── Skill parser ───────────────────────────────────────────────────────────────

def _parse_skill(path: str) -> dict:
    """Parse home_security.md into a structured dict."""
    text = Path(path).read_text()

    known_persons: list[str] = []
    in_known = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "## Known Persons":
            in_known = True
            continue
        if in_known:
            if stripped.startswith("##"):
                break
            if stripped.startswith("- "):
                known_persons.append(stripped[2:].strip())

    night_start = 22
    night_end = 6
    confidence_min = 0.80
    for line in text.splitlines():
        m = re.match(r"confidence_min:\s*([0-9.]+)", line)
        if m:
            confidence_min = float(m.group(1))
        m = re.match(r"night_start:\s*(\d+)", line)
        if m:
            night_start = int(m.group(1))
        m = re.match(r"night_end:\s*(\d+)", line)
        if m:
            night_end = int(m.group(1))

    return {
        "known_persons": known_persons,
        "confidence_min": confidence_min,
        "night_start": night_start,
        "night_end": night_end,
    }


# ── Rule evaluator ─────────────────────────────────────────────────────────────

def _is_night(skill: dict) -> bool:
    hour = datetime.now(timezone.utc).hour
    start = skill["night_start"]
    end = skill["night_end"]
    if start > end:
        return hour >= start or hour < end
    return start <= hour < end


def evaluate_rules(result: AnalysisResult, skill: dict) -> str:
    """Return priority string: INFO | WARNING | CRITICAL | ERROR."""
    if result.error and result.error != "parse_failed":
        return "ERROR"
    if result.error == "parse_failed":
        return "ERROR"
    if not result.known or result.confidence < skill["confidence_min"]:
        return "CRITICAL" if _is_night(skill) else "WARNING"
    return "INFO"


# ── Snapshot ───────────────────────────────────────────────────────────────────

def _save_snapshot(frame_b64: str, timestamp: str, priority: str) -> str:
    snap_dir = Path(os.getenv("SNAPSHOT_DIR", "./snapshots"))
    snap_dir.mkdir(parents=True, exist_ok=True)
    safe_ts = timestamp.replace(":", "-").replace("T", "_").replace("Z", "")
    path = snap_dir / f"{safe_ts}_{priority}.jpg"
    path.write_bytes(base64.b64decode(frame_b64))
    return str(path)


# ── Event logger ───────────────────────────────────────────────────────────────

def _log_event(result: AnalysisResult, priority: str) -> None:
    record = {
        "ts": result.timestamp,
        "person": result.person,
        "known": result.known,
        "confidence": result.confidence,
        "priority": priority,
        "error": result.error,
    }
    log_path = Path(os.getenv("LOG_PATH", "./logs/events.jsonl"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(record) + "\n")


# ── Alert message ──────────────────────────────────────────────────────────────

def _format_message(result: AnalysisResult, priority: str) -> str:
    status = "known" if result.known else "UNKNOWN"
    return (
        f"Person detected: {result.person} ({status}) "
        f"| confidence: {result.confidence:.2f} | {result.timestamp}"
    )


# ── Main loop ──────────────────────────────────────────────────────────────────

async def run() -> None:
    log_path = os.getenv("LOG_PATH", "./logs/events.jsonl")
    _setup_logging(log_path)

    skill_path = os.getenv("SKILL_PATH", "./agent/skills/home_security.md")
    skill = _parse_skill(skill_path)

    source_raw = os.getenv("CAMERA_SOURCE", "0")
    source: Union[int, str] = int(source_raw) if source_raw.isdigit() else source_raw
    interval = float(os.getenv("FRAME_SAMPLE_INTERVAL", "2"))
    motion_threshold = int(os.getenv("MOTION_PIXEL_THRESHOLD", "500000"))
    ha_enabled = os.getenv("HA_ENABLED", "false").lower() == "true"

    logger.info(
        "visio-sentinel starting | model=%s camera=%s known_persons=%d",
        os.getenv("OLLAMA_MODEL", "home-security"),
        source,
        len(skill["known_persons"]),
    )

    stop = asyncio.Event()

    def _handle_signal(signum, frame) -> None:
        logger.info("Shutdown signal received (%d)", signum)
        stop.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    async def _loop() -> None:
        async for frame_b64 in frame_stream(source, interval, motion_threshold):
            if stop.is_set():
                break

            result = await analyze_frame(frame_b64)
            priority = evaluate_rules(result, skill)
            _log_event(result, priority)

            logger.info(
                "person=%s known=%s conf=%.2f priority=%s error=%s",
                result.person, result.known, result.confidence, priority, result.error,
            )

            if priority in ("WARNING", "CRITICAL"):
                snapshot_path = _save_snapshot(frame_b64, result.timestamp, priority)
                message = _format_message(result, priority)
                await send_alert(message, snapshot_path, priority)
                if ha_enabled:
                    await send_event(result, priority)

    try:
        await asyncio.wait_for(_loop(), timeout=None)
    except asyncio.CancelledError:
        pass

    logger.info("visio-sentinel stopped")


if __name__ == "__main__":
    asyncio.run(run())
