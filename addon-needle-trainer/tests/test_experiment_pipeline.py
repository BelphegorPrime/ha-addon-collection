"""Experiment v027 must never touch original outputs or open test early."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import runner  # noqa: E402
from experiment_pipeline import (  # noqa: E402
    ensure_frozen_baselines,
    hash_file,
    start_training_snapshot,
    validate_experiment,
    validate_test_unsealing,
    verify_training_snapshot,
)
from local_evaluate import evaluate, validate_held_out  # noqa: E402

SOURCE = APP / "training" / "scenarios.json"
EXTRAS = APP / "training" / "augmentation_v026.json"


class ExperimentPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "needle-training"
        self.options_file = self.root / "options.json"
        self.options = {
            "mode": "idle",
            "confirm_resource_use": True,
            "confirm_uncalibrated_export": False,
            "memory_limit_mib": 4096,
            "reserve_memory_mib": 2048,
            "cpu_core": 3,
            "epochs": 1,
            "calibration_steps_per_run": 32,
            "calibration_epochs": 2,
        }
        runner.prepare(self.work, SOURCE)
        self.folder = runner.prepare_experiment(self.work, SOURCE, EXTRAS)
        (self.work / "needle3.safetensors").write_bytes(b"base checkpoint" * 100)
        (self.work / "needle3.cact").write_bytes(b"base cact" * 130)
        (self.work / "needle_lora.safetensors").write_bytes(b"old adapter")
        (self.work / "confidence_head.npz").write_bytes(b"old head")
        (self.work / "candidate-local-confidence.cact").write_bytes(b"old export")
        (self.work / "evaluation").mkdir()
        (self.work / "evaluation" / "test-report.json").write_text("old report")
        self.original = {
            path: (self.work / path).read_bytes()
            for path in (
                "needle3.safetensors", "needle3.cact",
                "needle_lora.safetensors", "confidence_head.npz",
                "candidate-local-confidence.cact", "test.jsonl",
                "evaluation/test-report.json",
            )
        }

    def _invoke(self, mode, executor=None):
        self.options_file.write_text(json.dumps({**self.options, "mode": mode}))
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=3),
            patch.object(runner, "run_command", side_effect=executor) as exec_mock,
        ):
            value = runner.run(
                options_path=self.options_file, work=self.work, scenarios=SOURCE
            )
        return value, exec_mock

    def _assert_root_unchanged(self):
        for name, old in self.original.items():
            self.assertEqual((self.work / name).read_bytes(), old, name)
        self.assertFalse((self.work / "approved.cact").exists())
        self.assertFalse((self.work / "approved.json").exists())

    def test_data_manifest_checksums_and_no_test_leakage(self):
        self.assertEqual(validate_experiment(self.work), self.folder)
        self.assertEqual(len(validate_held_out(self.folder, split="validation")), 36)
        self.assertEqual(len(validate_held_out(self.folder, split="test")), 36)
        (self.folder / "train.jsonl").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "Modified"):
            validate_experiment(self.work)

    def test_inference_is_not_allowed_without_training(self):
        with self.assertRaisesRegex(FileNotFoundError, "model_input_snapshot"):
            self._invoke("experiment_calibrate_all")
        self._assert_root_unchanged()

    def test_all_modes_use_separate_outputs_and_seal_test(self):
        def simulated_run(cmd, **kwargs):
            self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
            self.assertEqual(kwargs["env"]["TRANSFORMERS_OFFLINE"], "1")
            self.assertEqual(kwargs["core"], 3)
            self.assertEqual(kwargs["max_ram_mib"], 4096)
            if cmd[:2] == ["needle", "finetune"]:
                self.assertEqual(cmd[2], str(self.folder / "train.jsonl"))
                self.assertEqual(cmd[cmd.index("--checkpoint") + 1],
                                 str(self.work / "needle3.safetensors"))
                self.assertEqual(cmd[cmd.index("--checkpoint-dir") + 1],
                                 str(self.folder / "checkpoints"))
                output = Path(cmd[cmd.index("--out") + 1])
                self.assertEqual(output, self.folder / "needle_lora.safetensors")
                output.write_bytes(b"new experiment adapter")
            elif len(cmd) > 2 and cmd[2] == "/app/local_confidence.py":
                self.assertEqual(cmd[4], str(self.folder))
                if cmd[3] == "calibrate":
                    self.assertIn("--all", cmd)
                    (self.folder / "confidence_head.npz").write_bytes(b"new head")
                elif cmd[3] == "export":
                    (self.folder / "candidate-local-confidence.cact").write_bytes(
                        b"new export" * 150
                    )
            elif len(cmd) > 2 and cmd[2] == "/app/local_evaluate.py":
                self.assertEqual(cmd[3], str(self.folder))
                split = cmd[cmd.index("--split") + 1]
                result = {
                    "dataset": {
                        "path": split + ".jsonl",
                        "sha256": hash_file(self.folder / (split + ".jsonl")),
                    },
                    "candidate": {
                        "weights_sha256": hash_file(
                            self.folder / "candidate-local-confidence.cact"
                        )
                    },
                    "decision": {
                        "verdict": "CANDIDATE_FOR_MANUAL_REVIEW"
                    },
                }
                destination = self.folder / "evaluation" / (split + "-report.json")
                destination.parent.mkdir(exist_ok=True)
                destination.write_text(json.dumps(result))

        value, call = self._invoke("experiment_train", simulated_run)
        self.assertEqual(value, 0)
        self.assertEqual(call.call_count, 2)  # offline tokenizer and LoRA
        self.assertTrue((self.folder / "needle3.safetensors").is_symlink())
        self.assertEqual((self.folder / "needle3.safetensors").resolve(),
                         (self.work / "needle3.safetensors").resolve())
        self._assert_root_unchanged()
        hashes = ensure_frozen_baselines(self.work, self.folder)
        self.assertEqual(
            verify_training_snapshot(self.folder, hashes)["training_epochs"], 1
        )
        with self.assertRaisesRegex(FileExistsError, "already been started"):
            self._invoke("experiment_train", simulated_run)

        value, _ = self._invoke("experiment_calibrate_all", simulated_run)
        self.assertEqual(value, 0)
        self._assert_root_unchanged()

        value, _ = self._invoke("experiment_export", simulated_run)
        self.assertEqual(value, 0)
        with self.assertRaisesRegex(FileExistsError, "already exported"):
            self._invoke("experiment_export", simulated_run)
        self._assert_root_unchanged()

        with self.assertRaises(FileNotFoundError):
            self._invoke("experiment_test", simulated_run)
        value, _ = self._invoke("experiment_validate", simulated_run)
        self.assertEqual(value, 0)
        validate_test_unsealing(self.folder)

        value, _ = self._invoke("experiment_test", simulated_run)
        self.assertEqual(value, 0)
        self._assert_root_unchanged()

    def test_validation_no_go_does_not_unseal_test(self):
        hashes = ensure_frozen_baselines(self.work, self.folder)
        start_training_snapshot(self.folder, hashes, epochs=1)
        (self.folder / "needle_lora.safetensors").write_bytes(b"adapter")
        candidate = self.folder / "candidate-local-confidence.cact"
        candidate.write_bytes(b"candidate" * 160)
        (self.folder / "confidence_head.npz").write_bytes(b"head")
        validation = self.folder / "evaluation"
        validation.mkdir()
        (validation / "validation-report.json").write_text(json.dumps({
            "dataset": {
                "path": "validation.jsonl",
                "sha256": hash_file(self.folder / "validation.jsonl"),
            },
            "candidate": {"weights_sha256": hash_file(candidate)},
            "decision": {"verdict": "NO_GO"},
        }))
        with self.assertRaisesRegex(ValueError, "NO_GO"):
            self._invoke("experiment_test")
        self._assert_root_unchanged()

    def test_mutated_base_fails_before_calibration(self):
        hashes = ensure_frozen_baselines(self.work, self.folder)
        start_training_snapshot(self.folder, hashes, epochs=1)
        (self.folder / "needle_lora.safetensors").write_bytes(b"adapter")
        (self.work / "needle3.cact").write_bytes(b"different" * 200)
        with self.assertRaisesRegex(ValueError, "Original base model has changed"):
            self._invoke("experiment_calibrate_all")


if __name__ == "__main__":
    unittest.main()
