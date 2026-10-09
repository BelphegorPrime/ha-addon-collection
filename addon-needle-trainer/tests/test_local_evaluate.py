"""Offline safety and scoring regression tests for evaluate_local.

The native fake has only complete(); any attempt to execute HA actions by
calling run() deliberately fails. The CI Docker smoke also checks that a
real, pinned Needle-3 engine is baked into the trainer image.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from local_evaluate import (  # noqa: E402
    _head_metrics, _native_result, describe_distribution, evaluate,
    native_confidence_groups, score_native_model, validate_held_out,
    verdict_for, write_report,
)


def make_dataset(root: Path) -> list[dict]:
    test = []
    for group in range(6):
        for locale in ("de", "en", "fr", "es", "it", "nl"):
            test.append({
                "scenario_id": f"heldout-{group}",
                "locale": locale,
                "risk": "critical" if group in (2, 3) else "normal",
                "family": "power",
                "query": f"{locale} act-{group}",
                "tools": [
                    {"name": "turn_on", "description": "Switch on",
                     "parameters": {"type": "object", "properties": {}}},
                    {"name": "turn_off", "description": "Switch off",
                     "parameters": {"type": "object", "properties": {}}},
                ],
                "answers": [] if group in (2, 3) else [
                    {"name": "turn_on", "arguments": {}}
                ],
            })
    for split, examples in (
        ("test", test),
        ("train", [{**test[0], "scenario_id": "train-only"}]),
        ("validation", [{**test[0], "scenario_id": "validation-only"}]),
    ):
        (root / f"{split}.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in examples),
            encoding="utf-8",
        )
    return test


class FakeNeedle:
    instances = []
    fail_baseline = False

    def __init__(self, *, tools, weights, stateless, auto_date):
        assert stateless and auto_date is False
        assert all(isinstance(x, dict) and not callable(x) for x in tools)
        self.weights = str(weights)
        self.tool_names = {x["name"] for x in tools}
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def complete(self, query, max_new_tokens):
        assert max_new_tokens <= 128
        group = int(query.split("act-")[1])
        is_baseline = self.weights.endswith("/needle3.cact")
        if is_baseline and self.fail_baseline:
            raise RuntimeError("simulated native engine failure")
        expected = None if group in (2, 3) else "turn_on"
        # Baseline refuses everything, candidate correctly handles actions.
        action = None if is_baseline else expected
        return {
            "success": True, "validation": {},
            "function_calls": (
                [] if action is None else
                [{"name": action, "arguments": {}}]
            ),
            "confidence": 0.9,
        }

    def run(self, *args, **kwargs):
        raise AssertionError("evaluate_local must never invoke Needle.run()")


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.dataset = make_dataset(self.work)
        FakeNeedle.instances = []
        FakeNeedle.fail_baseline = False
        for name in ("needle3.cact", "candidate-local-confidence.cact"):
            (self.work / name).write_bytes(b"mocked cact!" * 100)
        (self.work / "confidence_head.npz").write_bytes(b"progress")
        # Ensure candidate was exported after completed progress.
        os.utime(self.work / "candidate-local-confidence.cact", None)

    def test_split_disjointness_and_six_languages(self):
        rows = validate_held_out(self.work)
        self.assertEqual(len(rows), 36)
        self.assertEqual(len({x["scenario_id"] for x in rows}), 6)

    def test_reject_overlapping_train_test_scenarios(self):
        rows = [*self.dataset, {
            **self.dataset[0], "scenario_id": "train-only", "locale": "de",
        }]
        (self.work / "test.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in rows)
        )
        with self.assertRaisesRegex(ValueError, "contamination"):
            validate_held_out(self.work)

    def test_reject_duplicate_and_missing_languages(self):
        rows = [*self.dataset[:-1], self.dataset[0]]
        (self.work / "test.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in rows)
        )
        with self.assertRaisesRegex(ValueError, "Repeated"):
            validate_held_out(self.work)

    def test_native_uses_only_tool_descriptions_and_complete(self):
        native = score_native_model(
            self.dataset, self.work / "candidate-local-confidence.cact",
            needle_cls=FakeNeedle,
        )
        self.assertEqual(native["metrics"]["overall"]["unsafe_approvals"], 0)
        self.assertEqual(native["metrics"]["overall"]["approved_correct"], 24)
        self.assertEqual(native["metrics"]["overall"]["correct_rejections"], 12)
        self.assertEqual(native["metrics"]["overall"]["transport_errors"], 0)
        self.assertEqual(len(FakeNeedle.instances), 1)

    def test_errors_cannot_be_counted_as_correct_rejections(self):
        FakeNeedle.fail_baseline = True
        native = score_native_model(
            self.dataset, self.work / "needle3.cact", needle_cls=FakeNeedle,
        )
        self.assertEqual(native["metrics"]["overall"]["transport_errors"], 36)
        self.assertEqual(native["metrics"]["overall"]["correct_rejections"], 0)

    def test_gate_rejects_low_confidence_and_wrong_tools(self):
        row = self.dataset[0]
        correct = {"success": True, "validation": {},
                   "function_calls": [{"name": "turn_on", "arguments": {}}],
                   "confidence": 0.8}
        self.assertEqual(_native_result(row, correct, None, 1.0, gate=0.8)["approved"],
                         "turn_on")
        self.assertIsNone(_native_result(row, {
            **correct, "confidence": 0.79
        }, None, 1.0, gate=0.8)["approved"])
        self.assertIsNone(_native_result(row, {
            **correct, "validation": {"negation": True}
        }, None, 1.0, gate=0.8)["approved"])

    def test_head_metrics_have_independent_positive_negative_counts(self):
        vals = [
            {"locale": "de", "positive": .9, "negative": .1},
            {"locale": "en", "positive": .7, "negative": .2},
        ]
        result = _head_metrics(vals)
        self.assertEqual(result["paired_ranking_accuracy"], 1.0)
        self.assertEqual(result["binary_accuracy_at_gate"], .75)
        self.assertEqual(result["correct_completion"]["count"], 2)
        self.assertEqual(result["wrong_completion"]["above_gate"], 0)

    def test_full_evaluation_reports_and_never_approves(self):
        def fake_head(work, rows):
            self.assertEqual(len(rows), 36)
            return _head_metrics([
                {"locale": x["locale"], "positive": .9, "negative": .1}
                for x in rows
            ])

        report = evaluate(
            self.work, needle_cls=FakeNeedle, head_scorer=fake_head,
        )
        self.assertEqual(
            report["decision"]["verdict"], "CANDIDATE_FOR_MANUAL_REVIEW"
        )
        self.assertEqual(report["candidate"]["metrics"]["overall"]["approved_correct"], 24)
        self.assertEqual(report["baseline"]["metrics"]["overall"]["approved_correct"], 0)
        path = self.work / "evaluation" / "test-report.json"
        self.assertEqual(json.loads(path.read_text())["dataset"]["cases"], 36)
        self.assertFalse((self.work / "approved.json").exists())
        self.assertFalse((self.work / "approved.cact").exists())

    def test_same_quality_is_no_go_even_with_good_head(self):
        class SameNeedle(FakeNeedle):
            def complete(self, query, max_new_tokens):
                self.weights = self.weights.replace("candidate-local-confidence.cact",
                                                    "needle3.cact")
                return super().complete(query, max_new_tokens)
        report = evaluate(
            self.work, needle_cls=SameNeedle,
            head_scorer=lambda work, rows: _head_metrics([
                {"locale": x["locale"], "positive": .9, "negative": .1}
                for x in rows
            ]),
        )
        self.assertEqual(report["decision"]["verdict"], "NO_GO")
        self.assertIn("No increase in correctly approved actions versus base",
                      report["decision"]["reasons"])

    def test_missing_head_diagnostic_is_no_go_but_writes_report(self):
        def failed(*args):
            raise RuntimeError("simulated JAX error")
        report = evaluate(self.work, needle_cls=FakeNeedle,
                          head_scorer=failed)
        self.assertEqual(report["decision"]["verdict"], "NO_GO")
        self.assertIsNotNone(report["posthoc_head_error"])
        self.assertTrue((self.work / "evaluation" / "test-report.json").is_file())

    def test_no_engine_in_offline_container_fails_closed(self):
        with patch.dict(os.environ, {"NEEDLE3_LIB_PATH": "/missing/needle3.so"}):
            with self.assertRaisesRegex(RuntimeError, "Offline Needle 3 engine"):
                evaluate(self.work)

    def test_stale_candidate_refused(self):
        os.utime(self.work / "candidate-local-confidence.cact", (1, 1))
        with self.assertRaisesRegex(ValueError, "older than head checkpoint"):
            evaluate(self.work, needle_cls=FakeNeedle)


if __name__ == "__main__":
    unittest.main()
