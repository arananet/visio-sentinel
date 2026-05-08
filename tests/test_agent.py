"""Tests for agent/agent.py — rule evaluator logic."""

import unittest
from unittest.mock import patch

from inference.analyzer import AnalysisResult
from agent.agent import evaluate_rules, _is_night


def _make_result(known: bool, confidence: float, error: str | None = None) -> AnalysisResult:
    return AnalysisResult(
        person="edu" if known else "unknown",
        known=known,
        confidence=confidence,
        raw_response="",
        timestamp="2026-05-07T14:00:00Z",
        error=error,
    )


_SKILL = {
    "known_persons": ["edu", "person_b"],
    "confidence_min": 0.80,
    "night_start": 22,
    "night_end": 6,
}


class TestEvaluateRules(unittest.TestCase):
    def test_known_person_is_info(self) -> None:
        result = _make_result(known=True, confidence=0.95)
        self.assertEqual(evaluate_rules(result, _SKILL), "INFO")

    def test_unknown_person_daytime_is_warning(self) -> None:
        result = _make_result(known=False, confidence=0.30)
        with patch("agent.agent._is_night", return_value=False):
            self.assertEqual(evaluate_rules(result, _SKILL), "WARNING")

    def test_unknown_person_nighttime_is_critical(self) -> None:
        result = _make_result(known=False, confidence=0.30)
        with patch("agent.agent._is_night", return_value=True):
            self.assertEqual(evaluate_rules(result, _SKILL), "CRITICAL")

    def test_low_confidence_known_treated_as_unknown_daytime(self) -> None:
        # Name parsed as 'edu' but confidence below threshold → treat as unknown
        result = _make_result(known=False, confidence=0.55)
        with patch("agent.agent._is_night", return_value=False):
            self.assertEqual(evaluate_rules(result, _SKILL), "WARNING")

    def test_low_confidence_known_treated_as_unknown_nighttime(self) -> None:
        result = _make_result(known=False, confidence=0.55)
        with patch("agent.agent._is_night", return_value=True):
            self.assertEqual(evaluate_rules(result, _SKILL), "CRITICAL")

    def test_parse_error_is_error(self) -> None:
        result = _make_result(known=False, confidence=0.0, error="parse_failed")
        self.assertEqual(evaluate_rules(result, _SKILL), "ERROR")

    def test_http_error_is_error(self) -> None:
        result = _make_result(known=False, confidence=0.0, error="Connection refused")
        self.assertEqual(evaluate_rules(result, _SKILL), "ERROR")


class TestIsNight(unittest.TestCase):
    def _check(self, hour: int, skill: dict, expected: bool) -> None:
        from datetime import datetime, timezone
        with patch("agent.agent.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 7, hour, 0, 0, tzinfo=timezone.utc)
            mock_dt.now.side_effect = lambda tz=None: datetime(2026, 5, 7, hour, 0, 0, tzinfo=timezone.utc)
            result = _is_night(skill)
        self.assertEqual(result, expected)

    def test_midnight_is_night(self) -> None:
        from datetime import datetime, timezone
        with patch("agent.agent.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 7, 0, 0, 0, tzinfo=timezone.utc)
            self.assertTrue(_is_night(_SKILL))

    def test_noon_is_daytime(self) -> None:
        from datetime import datetime, timezone
        with patch("agent.agent.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)
            self.assertFalse(_is_night(_SKILL))

    def test_hour_22_is_night(self) -> None:
        from datetime import datetime, timezone
        with patch("agent.agent.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 7, 22, 0, 0, tzinfo=timezone.utc)
            self.assertTrue(_is_night(_SKILL))

    def test_hour_6_is_daytime(self) -> None:
        from datetime import datetime, timezone
        with patch("agent.agent.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 5, 7, 6, 0, 0, tzinfo=timezone.utc)
            self.assertFalse(_is_night(_SKILL))


if __name__ == "__main__":
    unittest.main()
