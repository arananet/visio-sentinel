"""Tests for inference/sampler.py — motion gate and base64 encoding."""

import asyncio
import base64
import sys
import types
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Minimal cv2 stub so tests run without OpenCV installed
# ---------------------------------------------------------------------------
if "cv2" not in sys.modules:
    cv2_stub = types.ModuleType("cv2")
    cv2_stub.VideoCapture = MagicMock
    cv2_stub.COLOR_BGR2RGB = 4
    cv2_stub.COLOR_BGR2GRAY = 6
    cv2_stub.CAP_PROP_FPS = 5
    cv2_stub.cvtColor = lambda frame, code: frame  # identity for testing
    cv2_stub.absdiff = lambda a, b: np.abs(a.astype(int) - b.astype(int)).astype(np.uint8)
    sys.modules["cv2"] = cv2_stub


from inference.sampler import _encode_frame, _pixel_diff


class TestEncodeFrame(unittest.TestCase):
    def test_returns_valid_base64(self) -> None:
        frame = np.zeros((378, 378, 3), dtype=np.uint8)
        result = _encode_frame(frame)
        # Should decode without error
        decoded = base64.b64decode(result)
        img = Image.open(BytesIO(decoded))
        self.assertEqual(img.format, "JPEG")

    def test_non_zero_frame_encodes(self) -> None:
        frame = np.full((100, 100, 3), 128, dtype=np.uint8)
        result = _encode_frame(frame)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class TestPixelDiff(unittest.TestCase):
    def test_identical_frames_zero_diff(self) -> None:
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        diff = _pixel_diff(frame, frame)
        self.assertEqual(diff, 0)

    def test_different_frames_nonzero_diff(self) -> None:
        prev = np.zeros((100, 100, 3), dtype=np.uint8)
        curr = np.full((100, 100, 3), 255, dtype=np.uint8)
        diff = _pixel_diff(prev, curr)
        self.assertGreater(diff, 0)

    def test_motion_gate_threshold(self) -> None:
        prev = np.zeros((100, 100, 3), dtype=np.uint8)
        curr = np.zeros((100, 100, 3), dtype=np.uint8)
        # Only one pixel changed
        curr[0, 0] = [255, 255, 255]
        diff = _pixel_diff(prev, curr)
        # Should be very small (well below a 500000 threshold)
        self.assertLess(diff, 500000)

        # Full white frame should exceed threshold
        curr_full = np.full((100, 100, 3), 255, dtype=np.uint8)
        diff_full = _pixel_diff(prev, curr_full)
        self.assertGreater(diff_full, 100 * 100 // 2)


if __name__ == "__main__":
    unittest.main()
