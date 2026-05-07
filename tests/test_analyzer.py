"""Tests for inference/analyzer.py — response parsing and confidence gating."""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


# Patch httpx before import so the module loads without a real HTTP client
import httpx

from inference.analyzer import AnalysisResult, _parse_response


_TIMESTAMP = "2026-05-07T00:00:00Z"


class TestParseResponse(unittest.TestCase):
    def test_known_person_well_formed(self) -> None:
        result = _parse_response("edu | known | confidence 0.95", _TIMESTAMP)
        self.assertEqual(result.person, "edu")
        self.assertTrue(result.known)
        self.assertAlmostEqual(result.confidence, 0.95)
        self.assertIsNone(result.error)

    def test_unknown_person_well_formed(self) -> None:
        result = _parse_response("stranger | unknown | confidence 0.72", _TIMESTAMP)
        self.assertEqual(result.person, "stranger")
        self.assertFalse(result.known)
        self.assertAlmostEqual(result.confidence, 0.72)
        self.assertIsNone(result.error)

    def test_malformed_response_returns_error(self) -> None:
        result = _parse_response("I cannot determine who this is.", _TIMESTAMP)
        self.assertEqual(result.person, "unknown")
        self.assertFalse(result.known)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.error, "parse_failed")

    def test_empty_response_returns_error(self) -> None:
        result = _parse_response("", _TIMESTAMP)
        self.assertEqual(result.error, "parse_failed")

    def test_confidence_below_threshold_forces_unknown(self) -> None:
        # Default threshold is 0.80; confidence 0.50 should force known=False
        with patch.dict(os.environ, {"CONFIDENCE_THRESHOLD": "0.80"}):
            # Re-import to pick up patched env (threshold is module-level const)
            import importlib
            import inference.analyzer as mod
            importlib.reload(mod)
            result = mod._parse_response("edu | known | confidence 0.50", _TIMESTAMP)
            self.assertFalse(result.known)
            self.assertAlmostEqual(result.confidence, 0.50)

    def test_confidence_at_threshold_is_known(self) -> None:
        with patch.dict(os.environ, {"CONFIDENCE_THRESHOLD": "0.80"}):
            import importlib
            import inference.analyzer as mod
            importlib.reload(mod)
            result = mod._parse_response("edu | known | confidence 0.80", _TIMESTAMP)
            self.assertTrue(result.known)


class TestAnalyzeFrameErrorHandling(unittest.IsolatedAsyncioTestCase):
    async def test_returns_result_on_http_error(self) -> None:
        with patch("inference.analyzer.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                side_effect=httpx.ConnectError("refused")
            )
            from inference.analyzer import analyze_frame
            result = await analyze_frame("dummybase64==")
            self.assertFalse(result.known)
            self.assertIsNotNone(result.error)
            self.assertEqual(result.person, "unknown")


if __name__ == "__main__":
    unittest.main()
