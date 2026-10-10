"""Physical-memory guard tests: no RLIMIT_AS, safe RSS cancellation."""

from __future__ import annotations

import os
import resource
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sys import path as sys_path

APP = Path(__file__).resolve().parents[1] / "app"
sys_path.insert(0, str(APP))

import resource_guard as guard  # noqa: E402


class ResourceGuardTests(unittest.TestCase):
    def test_cpu_limits_do_not_set_virtual_address_limit(self) -> None:
        with (
            patch.object(guard.os, "sched_setaffinity") as affinity,
            patch.object(guard.os, "nice") as nice,
            patch.object(guard.resource, "setrlimit") as limit,
        ):
            guard.apply_limits(3)
        affinity.assert_called_once_with(0, {3})
        nice.assert_called_once_with(19)
        limit.assert_called_once_with(guard.resource.RLIMIT_CORE, (0, 0))
        self.assertNotEqual(
            guard.resource.RLIMIT_CORE,
            guard.resource.RLIMIT_AS,
        )

    def test_process_group_rss_includes_jax_helper_workers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for pid, pgrp, kib in [(100, 100, 2048), (101, 100, 3072),
                                    (102, 102, 99999)]:
                d = root / str(pid)
                d.mkdir()
                (d / "stat").write_text(
                    f"{pid} (JAX worker with spaces) S 1 {pgrp} 1 0\n"
                )
                (d / "status").write_text(f"VmRSS:\t{kib} kB\n")
            self.assertAlmostEqual(guard.group_rss_mib(100, root), 5)

    def test_missing_proc_refuses_unmonitored_training(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "Cannot inspect"):
                guard.group_rss_mib(123, Path(temp) / "not-mounted")

    def test_successful_command_uses_new_session_and_monitors_memory(self) -> None:
        process = Mock()
        process.pid = 5678
        # Native Popen.poll() returns the exit status after wait() finishes.
        process.poll.side_effect = [None, 0]
        process.wait.return_value = 0
        process.returncode = 0
        with (
            patch.object(guard.subprocess, "Popen", return_value=process)
            as popen,
            patch.object(guard, "available_ram_mib", return_value=12000),
            patch.object(guard, "group_rss_mib", return_value=256),
        ):
            guard.run_bounded(
                ["needle", "--help"],
                env={"JAX_PLATFORMS": "cpu"},
                max_ram_mib=4096,
                reserve_memory_mib=2048,
                core=2,
            )
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(popen.call_args.kwargs["env"]["JAX_PLATFORMS"], "cpu")
        self.assertEqual(process.wait.call_args.kwargs["timeout"], 0.25)

    def test_worker_is_stopped_before_exceeding_physical_budget(self) -> None:
        process = Mock()
        process.pid = 4321
        process.poll.return_value = None
        with (
            patch.object(guard.subprocess, "Popen", return_value=process),
            patch.object(guard, "available_ram_mib", return_value=14000),
            patch.object(guard, "group_rss_mib", return_value=4200),
            patch.object(guard, "stop_group") as stop,
        ):
            with self.assertRaisesRegex(RuntimeError, "resident RAM"):
                guard.run_bounded(
                    ["needle", "finetune"],
                    env={}, max_ram_mib=4096,
                    reserve_memory_mib=2048, core=2,
                )
        stop.assert_called_once_with(process)

    def test_worker_is_stopped_when_ha_reserve_disappears(self) -> None:
        process = Mock()
        process.pid = 4321
        process.poll.return_value = None
        with (
            patch.object(guard.subprocess, "Popen", return_value=process),
            patch.object(guard, "available_ram_mib",
                         side_effect=[12000, 1800]),
            patch.object(guard, "group_rss_mib", return_value=1000),
            patch.object(guard, "stop_group") as stop,
        ):
            with self.assertRaisesRegex(RuntimeError, "reserve"):
                guard.run_bounded(
                    ["needle", "finetune"],
                    env={}, max_ram_mib=4096,
                    reserve_memory_mib=2048, core=2,
                )
        stop.assert_called_once_with(process)

    def test_insufficient_ram_refuses_to_launch_any_process(self) -> None:
        with (
            patch.object(guard, "available_ram_mib", return_value=2400),
            patch.object(guard.subprocess, "Popen") as popen,
        ):
            with self.assertRaisesRegex(RuntimeError, "Not enough"):
                guard.run_bounded(
                    ["needle"], env={}, max_ram_mib=4096,
                    reserve_memory_mib=2048, core=3,
                )
        popen.assert_not_called()

    def test_large_budget_is_not_required_free_at_start(self) -> None:
        """Cap=6144 is permitted below 8192 available, when reserve holds."""
        process = Mock()
        process.pid = 1234
        process.poll.side_effect = [None, 0]
        process.wait.return_value = 0
        process.returncode = 0
        with (
            patch.object(guard.subprocess, "Popen", return_value=process)
            as launch,
            patch.object(guard, "available_ram_mib",
                         side_effect=[4500, 4300]),
            patch.object(guard, "group_rss_mib", return_value=1126),
        ):
            guard.run_bounded(
                ["needle", "finetune"], env={},
                max_ram_mib=6144, reserve_memory_mib=2048, core=3,
            )
        launch.assert_called_once()

    def test_large_budget_still_stops_when_HA_reserve_is_lost(self) -> None:
        """A permitted launch is never permission to consume all host RAM."""
        process = Mock()
        process.pid = 1234
        process.poll.return_value = None
        with (
            patch.object(guard.subprocess, "Popen", return_value=process)
            as launch,
            patch.object(guard, "available_ram_mib",
                         side_effect=[4500, 1975]),
            patch.object(guard, "group_rss_mib", return_value=2000),
            patch.object(guard, "stop_group") as stop,
        ):
            with self.assertRaisesRegex(RuntimeError, "reserve"):
                guard.run_bounded(
                    ["needle", "finetune"], env={},
                    max_ram_mib=6144, reserve_memory_mib=2048, core=3,
                )
        launch.assert_called_once()
        stop.assert_called_once_with(process)

    def test_minimum_startup_headroom_is_independent_of_RSS_ceiling(self) -> None:
        self.assertEqual(guard.minimum_start_available_mib(2048), 2560)
        with self.assertRaisesRegex(ValueError, "reserve"):
            guard.minimum_start_available_mib(500)

    def test_nonzero_native_exit_is_reported_without_fabrication(self) -> None:
        process = Mock()
        process.pid = 123
        process.poll.return_value = -6
        process.returncode = -6
        with (
            patch.object(guard, "available_ram_mib", return_value=16000),
            patch.object(guard.subprocess, "Popen", return_value=process),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                guard.run_bounded(
                    ["needle", "finetune"], env={},
                    max_ram_mib=4096, reserve_memory_mib=2048, core=2,
                )

    def test_stop_group_terminates_entire_child_session(self) -> None:
        process = Mock()
        process.pid = 111
        process.poll.return_value = None
        process.wait.return_value = 0
        with patch.object(guard.os, "killpg") as kill:
            guard.stop_group(process)
        kill.assert_called_once_with(111, guard.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
