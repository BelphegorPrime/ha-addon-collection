"""Low-priority CPU runner with physical-memory watchdog for JAX/XLA.

Never use RLIMIT_AS for JAX: it constrains *virtual address mappings* and
can reject an XLA compile even when physical RAM is available. Instead,
observe actual resident memory and the host's available-memory reserve.
This is a best-effort watchdog, NOT a hard kernel-enforced cgroup limit.
"""

from __future__ import annotations

import os
import resource
import signal
import subprocess
from pathlib import Path

MIB = 1024 * 1024


def apply_limits(core: int) -> None:
    """Apply limits that are compatible with XLA's virtual memory mapping."""
    os.sched_setaffinity(0, {core})
    os.nice(19)
    # Crashed native XLA processes must not fill /share with core dumps.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def group_rss_mib(
    group_id: int, proc_root: Path = Path("/proc")
) -> float:
    """Approximate total physical resident memory of a process group.

    Scan /proc because JAX may spawn helper processes. Shared pages can be
    counted more than once; that errs on the side of protecting HA.
    """
    if not proc_root.is_dir():
        raise RuntimeError("Cannot inspect /proc; refusing unmonitored job")
    resident_kib = 0
    for directory in proc_root.iterdir():
        if not directory.name.isdecimal():
            continue
        try:
            stat = (directory / "stat").read_text(encoding="ascii")
            # Process names are inside parentheses and may contain spaces.
            tail = stat[stat.rfind(")") + 2 :].split()
            if len(tail) < 3 or int(tail[2]) != group_id:
                continue
            for line in (directory / "status").read_text(
                encoding="ascii"
            ).splitlines():
                if line.startswith("VmRSS:"):
                    resident_kib += int(line.split()[1])
                    break
        except (FileNotFoundError, ProcessLookupError, PermissionError,
                ValueError, IndexError):
            # Processes may exit while /proc is scanned.
            continue
    return resident_kib / 1024


def available_ram_mib(proc_root: Path = Path("/proc")) -> int:
    with (proc_root / "meminfo").open(encoding="ascii") as handle:
        for line in handle:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    raise RuntimeError("Cannot determine free host RAM")


def stop_group(process: subprocess.Popen) -> None:
    """Stop all JAX workers, including the entire child process group."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def run_bounded(
    command: list[str],
    *,
    env: dict[str, str],
    max_ram_mib: int,
    reserve_memory_mib: int,
    core: int,
    poll_seconds: float = 0.25,
) -> None:
    """Run one native process, terminate on RAM pressure and fail closed.

    RSS polling cannot guarantee a strict instantaneous RAM ceiling. A
    memory.max cgroup controlled by the host is necessary for that. This
    watchdog avoids RLIMIT_AS failures while lowering overload risk.
    """
    if not 2048 <= max_ram_mib <= 12288:
        raise ValueError("Memory budget must be 2048..12288 MiB")
    if reserve_memory_mib < 1024:
        raise ValueError("Host reserve must be >=1024 MiB")
    if poll_seconds <= 0 or poll_seconds > 5:
        raise ValueError("Invalid memory polling interval")
    if available_ram_mib() < max_ram_mib + reserve_memory_mib:
        raise RuntimeError(
            "Not enough available host memory for the job and HA reserve"
        )

    process = subprocess.Popen(
        command, env=env, start_new_session=True,
        preexec_fn=lambda: apply_limits(core),
    )
    max_observed = 0.0
    try:
        while True:
            if process.poll() is not None:
                break
            rss = group_rss_mib(process.pid)
            max_observed = max(max_observed, rss)
            if rss >= max_ram_mib:
                raise RuntimeError(
                    f"Training stopped to protect Home Assistant: JAX "
                    f"uses {rss:.0f} MiB resident RAM "
                    f"(configured budget {max_ram_mib} MiB). "
                    "Use a less busy host or an explicitly larger "
                    "memory budget; steps_per_run does not reduce "
                    "JAX compile-time memory."
                )
            free = available_ram_mib()
            if free < reserve_memory_mib:
                raise RuntimeError(
                    "Training stopped to protect Home Assistant: "
                    f"available host RAM {free} MiB fell below "
                    f"reserve {reserve_memory_mib} MiB."
                )
            try:
                process.wait(timeout=poll_seconds)
                break
            except subprocess.TimeoutExpired:
                continue

        if process.returncode:
            raise subprocess.CalledProcessError(
                process.returncode, command
            )
        print(
            f"Process completed; peak observed physical RSS "
            f"{max_observed:.0f} MiB (budget {max_ram_mib} MiB).",
            flush=True,
        )
    finally:
        if process.poll() is None:
            stop_group(process)
