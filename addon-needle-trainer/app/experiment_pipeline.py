"""Immutable-input boundaries for the isolated v026 Needle experiment.

Only experiment-local outputs can be written. Root weights and the original
evaluation stay intact. Never relabel the original held-out test data or auto
approve a trained .cact candidate.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from training.workflow import read_jsonl

EXPERIMENT = Path("experiments/v026")
SOURCE_FILES = ("train.jsonl", "validation.jsonl", "test.jsonl", "scenarios.json")
COUNTS = {"train": 312, "validation": 36, "test": 36}


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_input(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing experiment input: {path}")
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"Expected immutable ordinary experiment input: {path}")


def validate_experiment(root: Path) -> Path:
    """Verify the staged dataset was not modified or tainted by old tests."""
    folder = root / EXPERIMENT
    if folder.is_symlink() or not folder.is_dir():
        raise FileNotFoundError(f"Run prepare_experiment first: {folder}")
    meta = folder / "data_manifest.json"
    _regular_input(meta)
    info = json.loads(meta.read_text(encoding="utf-8"))
    if (info.get("version") != "v026" or info.get("experiment_only") is not True
        or info.get("old_root_untouched") is not True
        or info.get("counts") != COUNTS):
        raise ValueError("Unexpected v026 experiment manifest")
    expected = info.get("sha256")
    if not isinstance(expected, dict) or set(expected) != set(SOURCE_FILES):
        raise ValueError("Incomplete experiment input checksums")
    for name in SOURCE_FILES:
        path = folder / name
        _regular_input(path)
        if hash_file(path) != expected[name]:
            raise ValueError(f"Modified v026 experiment input: {name}")

    # A previous root-run may have touched original data: never silently
    # compare an altered candidate to a different test dataset.
    original = root / "test.jsonl"
    if not original.is_file() or original.read_bytes() != (folder / "test.jsonl").read_bytes():
        raise ValueError("Original held-out test dataset changed since staging")
    if any(len(read_jsonl(folder / f"{split}.jsonl")) != count
           for split, count in COUNTS.items()):
        raise ValueError("Experiment row counts do not match source manifest")
    return folder


def ensure_frozen_baselines(root: Path, folder: Path) -> dict[str, str]:
    """Link only the immutable BASE files; all trainable outputs stay local."""
    fingerprints = {}
    for name in ("needle3.safetensors", "needle3.cact"):
        source = root / name
        if not source.is_file() or source.stat().st_size < 1024:
            raise FileNotFoundError(f"Download the base model first: {source}")
        target = folder / name
        if target.is_symlink():
            if target.resolve(strict=True) != source.resolve(strict=True):
                raise ValueError(f"Experiment base link was redirected: {target}")
        elif target.exists():
            raise ValueError(f"Experiment base must be a symlink, not a file: {target}")
        else:
            # It is never safe to write outputs to these links. All model
            # producers use the distinct experiment-local LoRA/output paths.
            target.symlink_to(os.path.relpath(source, start=folder))
        fingerprints[name] = hash_file(source)
    return fingerprints


def _snapshot_path(folder: Path) -> Path:
    return folder / "model_input_snapshot.json"


def start_training_snapshot(
    folder: Path, model_hashes: dict[str, str], *, epochs: int,
) -> None:
    """Persist model/data provenance before first training, once only."""
    output = _snapshot_path(folder)
    if output.exists():
        raise FileExistsError(f"Experiment has already been started: {output}")
    if (folder / "needle_lora.safetensors").exists():
        raise FileExistsError("Experiment adapter exists; never retrain over it")
    checkpoint_dir = folder / "checkpoints"
    if checkpoint_dir.exists() and any(checkpoint_dir.iterdir()):
        raise FileExistsError("Experiment contains earlier training checkpoints")
    manifest = {
        "version": "v027",
        "training_epochs": epochs,
        "original_base_sha256": model_hashes,
        "source_sha256": {name: hash_file(folder / name)
                          for name in SOURCE_FILES},
        "approved": False,
    }
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def verify_training_snapshot(
    folder: Path, hashes: dict[str, str],
) -> dict[str, Any]:
    output = _snapshot_path(folder)
    _regular_input(output)
    data = json.loads(output.read_text(encoding="utf-8"))
    if data.get("version") != "v027" or data.get("original_base_sha256") != hashes:
        raise ValueError("Original base model has changed since experiment training")
    if data.get("approved") is not False:
        raise ValueError("Invalid experiment approval marker")
    actual = {name: hash_file(folder / name) for name in SOURCE_FILES}
    if data.get("source_sha256") != actual:
        raise ValueError("Experiment data changed after training started")
    return data


def validate_test_unsealing(folder: Path) -> None:
    """Require independently approved *validation* report before opening test."""
    from local_evaluate import sha256_file

    report_file = folder / "evaluation" / "validation-report.json"
    _regular_input(report_file)
    report = json.loads(report_file.read_text(encoding="utf-8"))
    model = folder / "candidate-local-confidence.cact"
    if (report.get("dataset", {}).get("path") != "validation.jsonl"
        or report.get("dataset", {}).get("sha256") != sha256_file(folder / "validation.jsonl")
        or report.get("candidate", {}).get("weights_sha256") != sha256_file(model)
        or report.get("decision", {}).get("verdict") != "CANDIDATE_FOR_MANUAL_REVIEW"):
        raise ValueError(
            "Validation is missing, stale or NO_GO: do not run held-out test"
        )
