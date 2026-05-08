"""
Async frame sampler from USB webcam or RTSP stream with motion gate.
"""

import asyncio
import base64
import logging
import os
from collections.abc import AsyncGenerator
from io import BytesIO
from typing import Union

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_RETRY_DELAY = 5.0


def _encode_frame(frame: np.ndarray) -> str:
    """Encode BGR frame to base64 JPEG string."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode()


def _pixel_diff(prev: np.ndarray, curr: np.ndarray) -> int:
    """Sum of absolute pixel differences between two grayscale frames."""
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    return int(cv2.absdiff(prev_gray, curr_gray).sum())


async def frame_stream(
    source: Union[int, str],
    interval: float,
    motion_threshold: int,
) -> AsyncGenerator[str, None]:
    """
    Yield base64-encoded JPEG frames from source, gated by motion detection.

    Args:
        source: USB camera index (int) or RTSP URL (str).
        interval: Seconds between capture attempts.
        motion_threshold: Pixel-delta sum required to emit a frame.
    """
    prev_frame = None

    while True:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error("Cannot open camera source: %s. Retrying in %ds.", source, int(_RETRY_DELAY))
            await asyncio.sleep(_RETRY_DELAY)
            continue

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.error("Frame read failed from %s. Reconnecting.", source)
                    break

                if prev_frame is not None:
                    diff = _pixel_diff(prev_frame, frame)
                    if diff > motion_threshold:
                        yield _encode_frame(frame)
                else:
                    # Always emit the very first frame so the agent can initialize.
                    yield _encode_frame(frame)

                prev_frame = frame
                await asyncio.sleep(interval)
        finally:
            cap.release()

        await asyncio.sleep(_RETRY_DELAY)


if __name__ == "__main__":
    import sys

    source_raw = os.getenv("CAMERA_SOURCE", "0")
    source: Union[int, str] = int(source_raw) if source_raw.isdigit() else source_raw
    interval = float(os.getenv("FRAME_SAMPLE_INTERVAL", "2"))
    threshold = int(os.getenv("MOTION_PIXEL_THRESHOLD", "500000"))
    count = 0

    async def _run() -> None:
        global count
        async for _ in frame_stream(source, interval, threshold):
            count += 1
            print(f"Frame {count} emitted")
            if count >= 5:
                break

    asyncio.run(_run())
    print(f"Total frames emitted: {count}")
