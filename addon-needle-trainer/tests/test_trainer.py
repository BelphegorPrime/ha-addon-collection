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
            "calibration_steps_per_run": 8,
            "calibration_epochs": 2,
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
            with self.assertRaisesRegex(FileNotFoundError, "needle3.safetensors"):
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

    def test_download_prepares_persistent_tokenizer_too(self) -> None:
        self.save(mode="download", confirm_resource_use=True)
        self.work.mkdir()
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=0),
            patch.object(runner, "run_command") as execute,
        ):
            def completed(command, **kwargs):
                if command[0] == "needle":
                    (self.work / "needle3.safetensors").write_bytes(
                        b"checkpoint"
                    )
                else:
                    directory = self.work / "tokenizer"
                    directory.mkdir()
                    (directory / "tokenizer.model").write_bytes(b"model")
                    (directory / "tokenizer.vocab").write_bytes(b"vocab")
            execute.side_effect = completed
            self.assertEqual(self.invoke(), 0)
        commands = [call.args[0] for call in execute.call_args_list]
        self.assertEqual(
            commands[0][:3], ["needle", "download", "needle3.safetensors"]
        )
        self.assertEqual(commands[1][3], "download")
        self.assertNotIn("HF_HUB_OFFLINE", execute.call_args.kwargs["env"])

    def test_download_reuses_existing_checkpoint(self) -> None:
        self.save(mode="download", confirm_resource_use=True)
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=0),
            patch.object(runner, "run_command") as execute,
        ):
            def completed(command, **kwargs):
                directory = self.work / "tokenizer"
                directory.mkdir()
                (directory / "tokenizer.model").write_bytes(b"model")
                (directory / "tokenizer.vocab").write_bytes(b"vocab")
            execute.side_effect = completed
            self.assertEqual(self.invoke(), 0)
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0][3], "download")

    def test_explicit_tokenizer_only_download(self) -> None:
        self.save(mode="download_tokenizer", confirm_resource_use=True)
        self.work.mkdir()
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=0),
            patch.object(runner, "run_command") as execute,
        ):
            def completed(command, **kwargs):
                directory = self.work / "tokenizer"
                directory.mkdir()
                (directory / "tokenizer.model").write_bytes(b"model")
                (directory / "tokenizer.vocab").write_bytes(b"vocab")
            execute.side_effect = completed
            self.assertEqual(self.invoke(), 0)
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0][3], "download")

    def test_train_installs_offline_tokenizer_before_jax(self) -> None:
        self.save(mode="train", confirm_resource_use=True)
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        (self.work / "train.jsonl").write_text("{}\n")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=1),
            patch.object(runner, "run_command") as execute,
        ):
            self.assertEqual(self.invoke(), 0)
        commands = [call.args[0] for call in execute.call_args_list]
        self.assertEqual(commands[0][3], "install")
        self.assertEqual(commands[1][:2], ["needle", "finetune"])
        for call in execute.call_args_list:
            self.assertEqual(call.kwargs["env"]["HF_HUB_OFFLINE"], "1")

    def test_auto_affinity_uses_only_one_available_logical_cpu(self) -> None:
        with patch.object(runner.os, "sched_getaffinity", return_value={2, 4, 6}):
            self.assertEqual(runner.choose_cpu(-1), 6)
            self.assertEqual(runner.choose_cpu(4), 4)
            with self.assertRaises(ValueError):
                runner.choose_cpu(1)


    def test_build_requires_separate_approval(self) -> None:
        self.save(mode="build", confirm_resource_use=True)
        with patch.object(runner, "run_command") as executor:
            with self.assertRaisesRegex(
                ValueError, "confirm_uncalibrated_export"
            ):
                self.invoke()
        executor.assert_not_called()

    def test_build_writes_only_uncalibrated_archive(self) -> None:
        self.save(
            mode="build",
            confirm_resource_use=True,
            confirm_uncalibrated_export=True,
        )
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        (self.work / "needle_lora.safetensors").write_bytes(b"adapter")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=0),
            patch.object(runner, "run_command") as executor,
        ):
            def fake_export(*args, **kwargs):
                (self.work / "experimental-uncalibrated.cact").write_bytes(
                    b"uncalibrated-model"
                )
            executor.side_effect = fake_export
            self.assertEqual(self.invoke(), 0)
        args = executor.call_args.args[0]
        self.assertEqual(args[:2], ["needle", "build"])
        self.assertIn("experimental-uncalibrated.cact", args[-1])
        self.assertFalse((self.work / "approved.cact").exists())


    def test_local_confidence_calibration_is_bounded_and_offline(self) -> None:
        self.save(
            mode="calibrate",
            confirm_resource_use=True,
            calibration_steps_per_run=8,
            calibration_epochs=2,
        )
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        (self.work / "needle_lora.safetensors").write_bytes(b"adapter")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=2),
            patch.object(runner, "run_command") as execute,
        ):
            self.assertEqual(self.invoke(), 0)
        cmd = execute.call_args.args[0]
        self.assertEqual(cmd[2:4], [
            "/app/local_confidence.py", "calibrate",
        ])
        self.assertEqual(cmd[cmd.index("--steps") + 1], "8")
        self.assertEqual(cmd[cmd.index("--epochs") + 1], "2")
        env = execute.call_args.kwargs["env"]
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(execute.call_args.kwargs["core"], 2)

    def test_calibrate_all_is_one_manual_offline_run(self) -> None:
        self.save(
            mode="calibrate_all",
            confirm_resource_use=True,
            calibration_steps_per_run=32,
            calibration_epochs=2,
        )
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        (self.work / "needle_lora.safetensors").write_bytes(b"adapter")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=3),
            patch.object(runner, "run_command") as execute,
        ):
            self.assertEqual(self.invoke(), 0)
        # One tokenizer reinstall (offline), one calibration subprocess.
        self.assertEqual(execute.call_count, 2)
        command = execute.call_args.args[0]
        self.assertEqual(command[3], "calibrate")
        self.assertEqual(command[command.index("--steps") + 1], "32")
        self.assertEqual(command[command.index("--epochs") + 1], "2")
        self.assertIn("--all", command)
        self.assertEqual(execute.call_args.kwargs["max_ram_mib"], 4096)
        self.assertEqual(execute.call_args.kwargs["reserve_memory_mib"], 2048)
        self.assertEqual(execute.call_args.kwargs["core"], 3)
        self.assertEqual(execute.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1")
        self.assertEqual(
            execute.call_args.kwargs["env"]["TRANSFORMERS_OFFLINE"], "1"
        )
        self.assertFalse((self.work / "approved.cact").exists())
        self.assertFalse((self.work / "candidate-local-confidence.cact").exists())

    def test_calibrate_all_requires_explicit_confirmation(self) -> None:
        self.save(mode="calibrate_all", confirm_resource_use=False)
        with patch.object(runner, "run_command") as execute:
            with self.assertRaisesRegex(ValueError, "confirm_resource_use"):
                self.invoke()
        execute.assert_not_called()

    def test_calibrate_all_refuses_to_start_without_ram_reserve(self) -> None:
        self.save(mode="calibrate_all", confirm_resource_use=True)
        with (
            patch.object(runner, "available_ram_mib", return_value=4000),
            patch.object(runner, "run_command") as execute,
        ):
            with self.assertRaisesRegex(RuntimeError, "Refusing calibrate_all"):
                self.invoke()
        execute.assert_not_called()

    def test_calibrate_all_refuses_missing_adapter(self) -> None:
        self.save(mode="calibrate_all", confirm_resource_use=True)
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=3),
            patch.object(runner, "run_command") as execute,
        ):
            with self.assertRaisesRegex(FileNotFoundError, "LoRA adapter"):
                self.invoke()
        execute.assert_not_called()

    def test_evaluate_local_runs_offline_and_never_changes_approved(self) -> None:
        self.save(mode="evaluate_local", confirm_resource_use=True)
        self.work.mkdir()
        for name in (
            "needle3.safetensors", "needle_lora.safetensors",
            "needle3.cact", "candidate-local-confidence.cact",
            "confidence_head.npz", "train.jsonl",
            "validation.jsonl", "test.jsonl",
        ):
            (self.work / name).write_bytes(b"input")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=3),
            patch.object(runner, "run_command") as execute,
        ):
            def mock_execution(command, **kwargs):
                if "/app/local_evaluate.py" in command:
                    report = self.work / "evaluation" / "test-report.json"
                    report.parent.mkdir()
                    report.write_text('{"decision":{"verdict":"NO_GO"}}')
            execute.side_effect = mock_execution
            self.assertEqual(self.invoke(), 0)
        self.assertEqual(execute.call_count, 2)
        args = execute.call_args.args[0]
        self.assertEqual(args[2], "/app/local_evaluate.py")
        self.assertEqual(args[3], str(self.work))
        env = execute.call_args.kwargs["env"]
        self.assertEqual(env["HF_HUB_OFFLINE"], "1")
        self.assertEqual(env["TRANSFORMERS_OFFLINE"], "1")
        self.assertEqual(execute.call_args.kwargs["core"], 3)
        self.assertEqual(execute.call_args.kwargs["max_ram_mib"], 4096)
        self.assertFalse((self.work / "approved.cact").exists())
        self.assertFalse((self.work / "approved.json").exists())

    def test_evaluate_local_refuses_missing_export(self) -> None:
        self.save(mode="evaluate_local", confirm_resource_use=True)
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"base")
        (self.work / "needle_lora.safetensors").write_bytes(b"adapter")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=3),
            patch.object(runner, "run_command") as execute,
        ):
            with self.assertRaisesRegex(FileNotFoundError,
                                        "needle3.cact"):
                self.invoke()
        execute.assert_not_called()

    def test_evaluate_local_requires_user_confirmation(self) -> None:
        self.save(mode="evaluate_local", confirm_resource_use=False)
        with patch.object(runner, "run_command") as execute:
            with self.assertRaisesRegex(ValueError, "confirm_resource_use"):
                self.invoke()
        execute.assert_not_called()

    def test_evaluate_local_rejects_memory_pressure(self) -> None:
        self.save(mode="evaluate_local", confirm_resource_use=True)
        with (
            patch.object(runner, "available_ram_mib", return_value=5000),
            patch.object(runner, "run_command") as execute,
        ):
            with self.assertRaisesRegex(RuntimeError, "Refusing evaluate_local"):
                self.invoke()
        execute.assert_not_called()

    def test_calibrated_export_is_local_and_not_auto_approved(self) -> None:
        self.save(mode="export_local", confirm_resource_use=True)
        self.work.mkdir()
        (self.work / "needle3.safetensors").write_bytes(b"checkpoint")
        (self.work / "needle_lora.safetensors").write_bytes(b"adapter")
        with (
            patch.object(runner, "available_ram_mib", return_value=20000),
            patch.object(runner, "choose_cpu", return_value=0),
            patch.object(runner, "run_command") as execute,
        ):
            def fake_export(*args, **kwargs):
                (self.work / "candidate-local-confidence.cact").write_bytes(
                    b"candidate"
                )
            execute.side_effect = fake_export
            self.assertEqual(self.invoke(), 0)
        cmd = execute.call_args.args[0]
        self.assertEqual(cmd[3], "export")
        self.assertEqual(
            execute.call_args.kwargs["env"]["HF_HUB_OFFLINE"], "1"
        )
        self.assertFalse((self.work / "approved.cact").exists())

    def test_invalid_calibration_steps_do_not_launch(self) -> None:
        self.save(
            mode="calibrate", confirm_resource_use=True,
            calibration_steps_per_run=1000,
        )
        with patch.object(runner, "run_command") as execute:
            with self.assertRaisesRegex(ValueError, "calibration_steps_per_run"):
                self.invoke()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
