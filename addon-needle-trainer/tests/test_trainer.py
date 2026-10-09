"""Safety checks for manually triggered Needle trainer add-on."""

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
from training.workflow import load_scenarios, prepared_rows  # noqa: E402


class TrainerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "output"
        self.config = self.root / "options.json"
        self.options = {
            "mode": "idle",
            "confirm_resource_use": False,
            "memory_limit_mib": 4096,
            "reserve_memory_mib": 2048,
            "cpu_core": -1,
            "epochs": 1,
        }

    def save(self, **override) -> None:
        self.config.write_text(
            json.dumps({**self.options, **override}), encoding="utf-8"
        )

    def invoke(self) -> int:
        return runner.run(
            options_path=self.config,
            work=self.work,
            scenarios=APP / "training" / "scenarios.json",
        )

    def test_idle_does_not_create_data_or_start_process(self) -> None:
        self.save()
        with patch.object(runner, "run_command") as executor:
            self.assertEqual(self.invoke(), 0)
        executor.assert_not_called()
        self.assertFalse(self.work.exists())

    def test_training_requires_explicit_confirmation(self) -> None:
        self.save(mode="train")
        with self.assertRaisesRegex(ValueError, "confirm_resource_use"):
            self.invoke()

    def test_prepare_generates_valid_disjoint_splits(self) -> None:
        self.save(mode="prepare", confirm_resource_use=True)
        self.assertEqual(self.invoke(), 0)
        for name, count in (("train", 216), ("validation", 36), ("test", 36)):
            self.assertEqual(
                len((self.work / f"{name}.jsonl").read_text().splitlines()),
                count,
            )
        scenarios = load_scenarios(APP / "training" / "scenarios.json")
        splits = [
            {row["scenario_id"] for row in prepared_rows(scenarios, split)}
            for split in ("train", "validation", "test")
        ]
        self.assertFalse(splits[0] & splits[1])
        self.assertFalse(splits[0] & splits[2])
        self.assertFalse(splits[1] & splits[2])

    def test_train_requires_prepared_data_and_checkpoint(self) -> None:
        self.save(mode="train", confirm_resource_use=True)
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=0),
        ):
            with self.assertRaisesRegex(FileNotFoundError, "checkpoint"):
                self.invoke()

    def test_train_is_strictly_low_resource_and_offline(self) -> None:
        self.save(mode="train", confirm_resource_use=True)
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        (self.work / "train.jsonl").write_text("{}\n")
        with (
            patch.object(runner, "available_ram_mib", return_value=16000),
            patch.object(runner, "choose_cpu", return_value=3),
            patch.object(runner, "run_command") as execute,
        ):
            self.assertEqual(self.invoke(), 0)
        args = execute.call_args.args[0]
        kwargs = execute.call_args.kwargs
        self.assertEqual(args[:3], [
            "needle", "finetune", str(self.work / "train.jsonl")
        ])
        self.assertEqual(args[args.index("--generate") + 1], "0")
        self.assertEqual(args[args.index("--workers") + 1], "1")
        self.assertEqual(args[args.index("--batch-size") + 1], "1")
        self.assertEqual(kwargs["max_ram_mib"], 4096)
        self.assertEqual(kwargs["core"], 3)
        self.assertEqual(kwargs["env"]["HF_HUB_OFFLINE"], "1")
        self.assertNotIn("NEEDLE_API_KEY", kwargs["env"])

    def test_training_fails_with_insufficient_spare_memory(self) -> None:
        self.save(mode="train", confirm_resource_use=True)
        with (
            patch.object(runner, "available_ram_mib", return_value=6000),
            patch.object(runner, "run_command") as execute,
        ):
            with self.assertRaisesRegex(RuntimeError, "Refusing train"):
                self.invoke()
        execute.assert_not_called()

    def test_invalid_configuration_never_launches_training(self) -> None:
        self.save(
            mode="train", confirm_resource_use=True, epochs=100
        )
        with patch.object(runner, "run_command") as execute:
            with self.assertRaisesRegex(ValueError, "epochs"):
                self.invoke()
        execute.assert_not_called()

    def test_download_is_explicit_and_single_purpose(self) -> None:
        self.save(mode="download", confirm_resource_use=True)
        self.work.mkdir()
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=0),
            patch.object(runner, "run_command") as execute,
        ):
            # Pretend download has written the expected artifact.
            def completed(*args, **kwargs):
                (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
            execute.side_effect = completed
            self.assertEqual(self.invoke(), 0)
        cmd = execute.call_args.args[0]
        self.assertEqual(cmd[:3], ["needle", "download", "needle3.safetensors"])
        self.assertNotIn("HF_HUB_OFFLINE", execute.call_args.kwargs["env"])

    def test_auto_affinity_uses_only_one_available_logical_cpu(self) -> None:
        with patch.object(runner.os, "sched_getaffinity", return_value={2, 4, 6}):
            self.assertEqual(runner.choose_cpu(-1), 6)
            self.assertEqual(runner.choose_cpu(4), 4)
            with self.assertRaises(ValueError):
                runner.choose_cpu(1)


if __name__ == "__main__":
    unittest.main()
