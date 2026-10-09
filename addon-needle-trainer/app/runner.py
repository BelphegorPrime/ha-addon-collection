"""One-shot Needle trainer for Home Assistant OS.

Never starts on boot, never calls Home Assistant services, never swaps live
weights. A separate add-on container protects the running Needle playground.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from resource_guard import run_bounded
from training.workflow import LANGUAGES, SPLITS, load_scenarios, prepared_rows, write_jsonl

OPTIONS = Path("/data/options.json")
WORK = Path("/share/needle-training")
SCENARIOS = Path("/app/training/scenarios.json")
MIB = 1024 * 1024


def options_from(path: Path) -> dict:
    options = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(options, dict):
        raise ValueError("options.json must be an object")
    return options


def integer(options: dict, name: str, low: int, high: int) -> int:
    value = options.get(name)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")
    return value


def available_ram_mib() -> int:
    with open("/proc/meminfo", encoding="ascii") as handle:
        for line in handle:
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    raise RuntimeError("Cannot determine available host memory; refusing to train")


def run_command(
    command: list[str], *,
    env: dict[str, str],
    max_ram_mib: int,
    reserve_memory_mib: int,
    core: int,
) -> None:
    """Monitor actual RAM instead of limiting JAX's virtual address space."""
    run_bounded(
        command,
        env=env,
        max_ram_mib=max_ram_mib,
        reserve_memory_mib=reserve_memory_mib,
        core=core,
    )


def choose_cpu(core: int) -> int:
    allowed = sorted(os.sched_getaffinity(0))
    if not allowed:
        raise RuntimeError("No schedulable CPU available")
    if core == -1:
        return allowed[-1]
    if core not in allowed:
        raise ValueError("Selected CPU core is not in the allowed CPU affinity")
    return core


def prepare(work: Path, scenarios_file: Path) -> None:
    scenarios = load_scenarios(scenarios_file)
    work.mkdir(parents=True, exist_ok=True)
    for split in SPLITS:
        rows = prepared_rows(scenarios, split)
        write_jsonl(work / f"{split}.jsonl", rows)
        print(f"{split}: {len(rows)} examples in {len(LANGUAGES)} languages", flush=True)


def run(
    options_path: Path = OPTIONS,
    work: Path = WORK,
    scenarios: Path = SCENARIOS,
) -> int:
    opts = options_from(options_path)
    mode = opts.get("mode", "idle")
    if mode not in (
        "idle", "prepare", "download", "download_tokenizer",
        "download_base", "train", "calibrate", "export_local", "build",
    ):
        raise ValueError("mode must be idle, prepare, download, download_tokenizer, download_base, train, calibrate, export_local or build")
    if mode == "idle":
        print("Idle. Choose a one-shot mode, save options and manually start this add-on.")
        return 0
    if opts.get("confirm_resource_use") is not True:
        raise ValueError(
            "Set confirm_resource_use=true before running a one-shot job. "
            "Reset mode to idle after finishing."
        )
    ram = integer(opts, "memory_limit_mib", 2048, 12288)
    reserve = integer(opts, "reserve_memory_mib", 1024, 16384)
    cpu_core = integer(opts, "cpu_core", -1, 4095)
    epochs = integer(opts, "epochs", 1, 3)
    calibration_steps = integer(opts, "calibration_steps_per_run", 1, 32)
    calibration_epochs = integer(opts, "calibration_epochs", 1, 5)
    if mode == "build" and opts.get("confirm_uncalibrated_export") is not True:
        raise ValueError(
            "Build requires confirm_uncalibrated_export=true because the "
            "resulting model has no calibrated confidence head."
        )
    work.mkdir(parents=True, exist_ok=True)

    if mode == "prepare":
        prepare(work, scenarios)
        print("Prepared data under /share/needle-training.")
        return 0

    if available_ram_mib() < ram + reserve:
        raise RuntimeError(
            f"Refusing {mode}: need >= {ram + reserve} MiB MemAvailable "
            f"({ram} MiB cap plus {reserve} MiB reserved for Home Assistant). "
            "Choose a less busy time or use a separate training host."
        )
    core = choose_cpu(cpu_core)
    env = dict(os.environ)
    # No automatic cloud augmentation or accidental token use.
    for key in ("OPENROUTER_API_KEY", "NEEDLE_API_KEY", "HF_TOKEN"):
        env.pop(key, None)
    env.update({
        "JAX_PLATFORMS": "cpu",
        "JAX_NUM_CPU_DEVICES": "1",
        "JAX_ENABLE_X64": "false",
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "NEEDLE_TELEMETRY": "0",
        "DO_NOT_TRACK": "1",
        "HOME": str(work),
        "HF_HOME": str(work / "hf"),
    })
    checkpoint = work / "needle3.safetensors"

    tokenizer_command = [
        sys.executable, "-u", "/app/tokenizer_assets.py", "download",
        str(work),
    ]
    if mode == "download_tokenizer":
        cmd = tokenizer_command
    elif mode in ("download", "download_base"):
        # Explicit download only; reuse cached checkpoint on subsequent
        # invocations so a missing tokenizer does not redownload 242 MB.
        if mode == "download" and checkpoint.is_file():
            cmd = tokenizer_command
        else:
            target = "needle3.safetensors" if mode == "download" else "needle3"
            cmd = ["needle", "download", target, "--out", str(work)]
    else:
        if not checkpoint.is_file():
            raise FileNotFoundError(
                f"Missing {checkpoint}; run mode=download first."
            )
        if mode == "build":
            # Upstream Needle build *always* downloads the original archive
            # with fetch_weights(force=True), even with a local checkpoint.
            # The built LoRA model drops its confidence head and is NEVER
            # named approved.cact or eligible for automatic deployment.
            adapter = work / "needle_lora.safetensors"
            if not adapter.is_file():
                raise FileNotFoundError(
                    f"Missing {adapter}; run mode=train first."
                )
            cmd = [
                "needle", "build", str(checkpoint),
                "--lora", str(adapter),
                "--out", str(work / "experimental-uncalibrated.cact"),
            ]
        elif mode in ("calibrate", "export_local"):
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
            if not (work / "needle_lora.safetensors").is_file():
                raise FileNotFoundError(
                    "Missing LoRA adapter; run mode=train first."
                )
            if mode == "export_local":
                cmd = [
                    sys.executable, "-u", "/app/local_confidence.py",
                    "export", str(work),
                    "--epochs", str(calibration_epochs),
                ]
            else:
                cmd = [
                    sys.executable, "-u", "/app/local_confidence.py",
                    "calibrate", str(work),
                    "--steps", str(calibration_steps),
                    "--epochs", str(calibration_epochs),
                ]
        else:
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
            train = work / "train.jsonl"
            if not train.is_file():
                raise FileNotFoundError(
                    f"Missing {train}; run mode=prepare first."
                )
            cmd = [
                "needle", "finetune", str(train),
                "--checkpoint", str(checkpoint),
                "--epochs", str(epochs),
                "--batch-size", "1",
                "--max-len", "384",
                "--lora-rank", "4",
                "--lora-alpha", "8",
                "--generate", "0",
                "--workers", "1",
                "--val-split", "0",
                "--seed", "42",
                "--checkpoint-dir", str(work / "checkpoints"),
                "--out", str(work / "needle_lora.safetensors"),
            ]
    print(
        f"Starting one-shot {mode}: CPU #{core}, low priority; physical "
        f"RSS watchdog budget {ram} MiB; {reserve} MiB free-host-RAM reserve. "
        "No RLIMIT_AS (JAX requires a larger virtual address space). "
        "Watchdog sampling is best-effort, not a hard cgroup quota.",
        flush=True,
    )
    if mode in ("train", "calibrate"):
        # Upstream Needle loads tokenizer.model only from its installed
        # package directory. Restore it from persistent /share *before*
        # the expensive JAX startup, with network access still disabled.
        run_command(
            [
                sys.executable, "-u", "/app/tokenizer_assets.py",
                "install", str(work),
            ],
            env=env, max_ram_mib=ram,
            reserve_memory_mib=reserve, core=core,
        )
    run_command(cmd, env=env, max_ram_mib=ram, core=core)
    if mode in ("download", "download_base", "download_tokenizer"):
        if mode in ("download", "download_base"):
            target = (
                "needle3.safetensors"
                if mode == "download" else "needle3.cact"
            )
            expected = work / target
            nested = work / "checkpoints" / target
            if not expected.is_file() and nested.is_file():
                expected.symlink_to(nested.relative_to(work))
            if not expected.is_file():
                raise RuntimeError(
                    f"Download returned without {target}. Check logs."
                )
        if mode == "download":
            # The checkpoint download does not include the tokenizer.
            # The add-on's offline train mode must never implicitly
            # fetch these assets from Hugging Face.
            if cmd != tokenizer_command:
                run_command(
                    tokenizer_command, env=env,
                    max_ram_mib=ram, core=core,
                )
        if mode in ("download", "download_tokenizer"):
            from tokenizer_assets import verify_assets

            verify_assets(work)
    elif mode == "calibrate":
        print(
            "Confidence training slice saved; run calibrate again to "
            "continue, or export_local only after all steps are complete.",
            flush=True,
        )
    elif mode == "export_local":
        if not (work / "candidate-local-confidence.cact").is_file():
            raise RuntimeError("Local export did not produce a .cact model")
        print(
            "Local confidence candidate is ready for separate six-language "
            "evaluation. It is NOT deployed or auto-approved.",
            flush=True,
        )
    elif mode == "build":
        if not (work / "experimental-uncalibrated.cact").is_file():
            raise RuntimeError("Build succeeded without producing a .cact archive")
        print(
            "Experimental uncalibrated .cact built under /share/needle-training. "
            "It will NOT be selected by the live Needle add-on because local "
            "LoRA exports drop the confidence head.",
            flush=True,
        )
    else:
        print(
            "LoRA adapter saved. NOT usable for automatic HA approval: "
            "the locally exported model would have confidence=null.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (ValueError, RuntimeError, FileNotFoundError, OSError,
            subprocess.CalledProcessError) as exc:
        print(f"Needle Trainer: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
