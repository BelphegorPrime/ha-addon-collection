"""Offline unit tests for incremental Needle confidence calibration.

No heavyweight JAX call is performed in CI by these tests; full inference,
checkpoint compatibility and memory footprint need device-level validation.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from local_confidence import (  # noqa: E402
    calibration_end_step, candidate_examples, data_fingerprint,
    main, run_calibration,
)


class HeadTrainingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)

    def test_contrasting_labels_for_all_action_types(self) -> None:
        cases = [
            {"query": "turn on light",
             "tools": [{"name": "turn_on"}, {"name": "turn_off"}],
             "answers": [{"name": "turn_on", "arguments": {}}]},
            {"query": "do not turn on light",
             "tools": [{"name": "turn_on"}, {"name": "turn_off"}],
             "answers": []},
        ]
        examples = candidate_examples(cases)
        self.assertEqual([score for _, score in examples],
                         [1.0, 0.0, 1.0, 0.0])
        self.assertEqual(
            examples[1][0]["answers"],
            [{"name": "turn_off", "arguments": {}}],
        )
        self.assertEqual(examples[2][0]["answers"], [])
        self.assertEqual(
            examples[3][0]["answers"],
            [{"name": "turn_on", "arguments": {}}],
        )

    def test_contrasting_examples_require_competition(self) -> None:
        with self.assertRaisesRegex(ValueError, "two tool alternatives"):
            candidate_examples([
                {"tools": [{"name": "turn_on"}], "answers": []}
            ])

    def test_resume_fingerprint_changes_with_model_or_data(self) -> None:
        inputs = [
            self.work / "checkpoint.safetensors",
            self.work / "adapter.safetensors",
            self.work / "train.jsonl",
        ]
        for path in inputs:
            path.write_bytes(b"unchanged")
        initial = data_fingerprint(*inputs)
        inputs[1].write_bytes(b"changed")
        self.assertNotEqual(initial, data_fingerprint(*inputs))

    def test_checkpoint_not_started_rejects_out_of_range_steps(self) -> None:
        with self.assertRaisesRegex(ValueError, "steps_per_run"):
            run_calibration(self.work, steps_per_run=1000)
        with self.assertRaisesRegex(ValueError, "Invalid epochs"):
            run_calibration(self.work, max_epochs=99)
        # Resource-heavy imports and host data should never be inspected
        # until the explicit limits pass.

    def test_calibrate_all_resumes_without_repeating_saved_steps(self) -> None:
        # Exactly the user's currently saved 40/864 steps remain compatible
        # with switching from a bounded slice to a full one-shot run.
        self.assertEqual(
            calibration_end_step(40, 864, 32, run_to_completion=True), 864
        )
        self.assertEqual(
            calibration_end_step(40, 864, 32), 72
        )
        self.assertEqual(
            calibration_end_step(0, 864, 8, run_to_completion=True), 864
        )
        self.assertEqual(
            calibration_end_step(860, 864, 32), 864
        )
        self.assertEqual(
            calibration_end_step(864, 864, 32, run_to_completion=True), 864
        )

    def test_calibrate_all_rejects_invalid_checkpoint_boundaries(self) -> None:
        for position in (-1, 865):
            with self.subTest(position=position):
                with self.assertRaisesRegex(ValueError, "checkpoint progress"):
                    calibration_end_step(
                        position, 864, 32, run_to_completion=True
                    )
        with self.assertRaisesRegex(ValueError, "steps_per_run"):
            calibration_end_step(40, 864, 33, run_to_completion=True)
        with self.assertRaisesRegex(ValueError, "run_to_completion"):
            calibration_end_step(40, 864, 32, run_to_completion="yes")

    def test_cli_calibrate_all_calls_same_resume_implementation(self) -> None:
        with patch("local_confidence.run_calibration") as calibrate:
            calibrate.return_value = {"finished": False}
            self.assertEqual(
                main([
                    "calibrate", str(self.work),
                    "--steps", "32", "--epochs", "2", "--all",
                ]),
                0,
            )
        calibrate.assert_called_once_with(
            self.work,
            steps_per_run=32, max_epochs=2,
            max_len=384, run_to_completion=True,
        )

    def test_cli_bounded_mode_stays_bounded(self) -> None:
        with patch("local_confidence.run_calibration") as calibrate:
            calibrate.return_value = {"finished": False}
            self.assertEqual(
                main(["calibrate", str(self.work), "--steps", "8"]), 0
            )
        self.assertFalse(calibrate.call_args.kwargs["run_to_completion"])

    def test_cli_export_cannot_accept_calibrate_all_flag(self) -> None:
        with patch("local_confidence.export_calibrated_candidate") as export:
            with self.assertRaises(SystemExit):
                main(["export", str(self.work), "--all"])
        export.assert_not_called()

    def test_cli_does_not_silently_export_partial_head(self) -> None:
        with patch("local_confidence.export_calibrated_candidate") as export:
            self.assertEqual(main(["export", str(self.work)]), 0)
        export.assert_called_once_with(self.work)

    def test_saved_progress_schema_requires_no_python_pickle(self) -> None:
        path = APP / "local_confidence.py"
        contents = path.read_text(encoding="utf-8")
        self.assertIn("allow_pickle=False", contents)
        self.assertIn("os.replace(staged, progress)", contents)
        self.assertIn("if step < total_steps:", contents)
        self.assertIn("candidate-local-confidence.cact", contents)
        self.assertNotIn('output = work / "approved.cact"', contents)


if __name__ == "__main__":
    unittest.main()
