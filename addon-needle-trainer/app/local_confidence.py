"""Fully local, resumable Needle 3 confidence-head calibration and model export.

Only a standalone Home Assistant *trainer* add-on may run this module. Never
approve an action or replace a production model here. Upstream local LoRA
discards the confidence head; this trains it against matching/mismatching
tool-call completions and exports it with the merged adapter instead.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import numpy as np


def candidate_examples(rows: list[dict[str, Any]]) -> list[tuple[dict, float]]:
    """Construct correct and deliberately incorrect *completed* tool calls.

    The post-hoc confidence head reads both the prompt and the actual call.
    Off-topic/negated user requests must have an empty-call positive example.
    """
    examples: list[tuple[dict, float]] = []
    for row in rows:
        answers = row["answers"]
        available = [tool["name"] for tool in row["tools"]]
        if len(available) < 2:
            raise ValueError("Need at least two tool alternatives")
        examples.append((row, 1.0))
        if answers:
            alternatives = [name for name in available if name != answers[0]["name"]]
            if not alternatives:
                raise ValueError("No incorrect competing tool available")
            wrong = [{"name": alternatives[0], "arguments": {}}]
        else:
            wrong = [{"name": available[0], "arguments": {}}]
        examples.append(({**row, "answers": wrong}, 0.0))
    return examples


def data_fingerprint(
    checkpoint: Path, adapter: Path, dataset: Path
) -> str:
    """Reject stale/resumed calibration when source weights or data change."""
    h = hashlib.sha256()
    for path in (checkpoint, adapter, dataset):
        h.update(path.name.encode())
        # Stream to keep memory use bounded even for a large checkpoint.
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
    return h.hexdigest()


def save_progress(
    head: dict,
    progress: Path,
    *,
    step: int,
    fingerprint: str,
    losses: list[float],
    total_steps: int,
) -> None:
    """Atomic, non-pickle checkpoints; optimizer is deliberately stateless."""
    from flax.traverse_util import flatten_dict

    arrays = {
        "/".join(key): np.asarray(value)
        for key, value in flatten_dict(head).items()
    }
    metadata = json.dumps(
        {"version": 1, "step": step, "fingerprint": fingerprint,
         "total_steps": total_steps, "recent_loss": losses[-10:]},
        sort_keys=True,
    )
    arrays["__meta__"] = np.asarray(metadata)
    staged = progress.with_suffix(".next.npz")
    with staged.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, progress)


def load_progress(progress: Path, fingerprint: str) -> tuple[dict, int, int]:
    """Reload head params only if data and source weights are identical."""
    from flax.traverse_util import unflatten_dict

    with np.load(progress, allow_pickle=False) as bundle:
        info = json.loads(bundle["__meta__"].item())
        if info.get("version") != 1 or info.get("fingerprint") != fingerprint:
            raise ValueError("Calibration inputs changed: reset head checkpoint manually")
        arrays = {
            tuple(name.split("/")): np.array(bundle[name])
            for name in bundle.files if name != "__meta__"
        }
        if not arrays:
            raise ValueError("Empty confidence-head checkpoint")
        return (
            unflatten_dict(arrays),
            int(info["step"]),
            int(info["total_steps"]),
        )


def prepare_jax_backbone(base: dict) -> dict:
    """Convert *all* Needle checkpoint NumPy tensors to JAX arrays.

    Flax engram embedding tables use traced gather indices. NumPy array
    indexing with tracers is not supported, even when the LoRA targets
    themselves have already been converted to JAX.
    """
    import jax
    import jax.numpy as jnp

    return jax.tree.map(jnp.asarray, base)


def make_confidence_grad_fn(model):
    """Return the actual calibration objective with dynamic frozen weights.

    The large 20-layer backbone must be a JIT argument, not a Python
    closure constant: otherwise XLA can constant-fold hundreds of MiB
    of weights into the compiled executable.
    """
    import jax
    import jax.numpy as jnp
    import optax

    def loss_fn(head_params, backbone_params, tokens, label):
        current_params = {**backbone_params, "confidence_head": head_params}
        logits = model.apply(
            {"params": current_params}, tokens,
            method=type(model).forward_confidence,
        )
        return optax.sigmoid_binary_cross_entropy(
            logits.astype(jnp.float32), label
        ).mean()

    return jax.jit(jax.value_and_grad(loss_fn, argnums=0))


def load_local_model(checkpoint: Path, adapter: Path):
    """Reuse exactly upstream Needle's local LoRA merge (no downloads)."""
    from needle.model.checkpoints import read_adapter
    from needle.model.finetune import merge_lora
    from needle.model.run import load_checkpoint

    base, config = load_checkpoint(str(checkpoint))
    tuned = read_adapter(str(adapter))
    if not tuned or not tuned.get("lora"):
        raise ValueError("Missing or malformed Needle LoRA adapter")
    import jax
    import jax.numpy as jnp

    # Upstream read_checkpoint() loads every weight as a NumPy ndarray.
    # merge_lora() only touches the five LoRA target groups, leaving
    # other NumPy leaves (notably engrams[].embedding) unchanged. Flax
    # indexes those embeddings with JAX traced indices in hidden_cells,
    # causing TracerArrayConversionError during confidence backprop.
    # Convert the *entire* backbone before tracing, not just LoRA targets.
    base = prepare_jax_backbone(base)

    lora = {
        tuple(path.split("/")): {
            "A": jnp.asarray(arrays["A"]),
            "B": jnp.asarray(arrays["B"]),
        }
        for path, arrays in tuned["lora"].items()
    }
    merged = merge_lora(base, lora, float(tuned["scale"]))
    if "confidence_head" not in merged:
        raise ValueError("Base checkpoint has no trainable confidence head")
    return merged, config


def _encoded(model_tokenizer, row: dict, max_len: int) -> np.ndarray:
    from needle.model.finetune import render_example
    from needle.model.tokenizer import BOS_ID, PAD_ID

    prompt, target = render_example(row)
    ids = [BOS_ID] + model_tokenizer.encode(prompt + target)
    if len(ids) > max_len:
        raise ValueError(
            f"Training example has {len(ids)} tokens; max_len={max_len}; "
            "do not silently truncate a safety-critical call"
        )
    return np.asarray(ids + [PAD_ID] * (max_len - len(ids)), dtype=np.int32)


def calibration_end_step(
    current_step: int, total_steps: int, steps_per_run: int,
    *, run_to_completion: bool = False,
) -> int:
    """Plan remaining work without ever changing the resume checkpoint.

    The automatic mode uses exactly the same training examples and stored
    weights as bounded calibration. Only the end index is different.
    """
    if not isinstance(run_to_completion, bool):
        raise ValueError("run_to_completion must be boolean")
    if not 1 <= steps_per_run <= 32:
        raise ValueError("steps_per_run must be 1..32")
    if type(current_step) is not int or type(total_steps) is not int:
        raise ValueError("Calibration checkpoint steps must be integers")
    if total_steps < 1 or not 0 <= current_step <= total_steps:
        raise ValueError(
            f"Invalid confidence checkpoint progress {current_step}/{total_steps}"
        )
    return (
        total_steps if run_to_completion
        else min(current_step + steps_per_run, total_steps)
    )


def run_calibration(
    work: Path, *,
    steps_per_run: int = 8,
    max_epochs: int = 2,
    run_to_completion: bool = False,
    max_len: int = 384,
    learning_rate: float = 0.0001,
) -> dict:
    """Execute one bounded slice or all remaining steps, checkpointing each.

    Frozen LoRA-merged backbone; only confidence_head gradients are computed.
    No upload or automatic promotion. Interrupted runs resume from the last
    fully saved step on a manual restart; momentum-free SGD needs no
    optimizer-state deserialization. The automatic mode runs in *one*
    subprocess invocation, never in a background scheduler.
    """
    if not 1 <= steps_per_run <= 32:
        raise ValueError("steps_per_run must be 1..32")
    if not isinstance(run_to_completion, bool):
        raise ValueError("run_to_completion must be boolean")
    if not 1 <= max_epochs <= 5 or not 128 <= max_len <= 768:
        raise ValueError("Invalid epochs or maximum sequence length")
    import jax
    import jax.numpy as jnp
    import optax
    from needle.model.architecture import SimpleAttentionNetwork
    from needle.model.finetune import read_examples, render_example
    from needle.model.tokenizer import get_tokenizer
    from needle.model.quantize import configure_deploy

    checkpoint = work / "needle3.safetensors"
    adapter = work / "needle_lora.safetensors"
    dataset = work / "train.jsonl"
    for file in (checkpoint, adapter, dataset):
        if not file.is_file():
            raise FileNotFoundError(str(file))

    fingerprint = data_fingerprint(checkpoint, adapter, dataset)
    params, config = load_local_model(checkpoint, adapter)
    config.dtype = "float32"
    configure_deploy(
        act_bits=getattr(config, "act_bits", 8),
        kv_bits=getattr(config, "kv_bits", 8),
    )
    tokenizer = get_tokenizer(config.vocab_size)
    rows = list(read_examples(str(dataset)))
    if not rows:
        raise ValueError("Empty training data")
    examples = candidate_examples(rows)
    # Reduce JAX memory and CPU use: compile only the smallest sequence
    # bucket that fits every *complete* prompt+call. Never truncate.
    longest = max(
        len(tokenizer.encode("".join(render_example(example)))) + 1
        for example, _ in examples
    )
    if longest > max_len:
        raise ValueError(
            f"Longest completed training call is {longest} tokens "
            f"(limit {max_len}); refusing truncation"
        )
    bucket = 128
    while bucket < longest:
        bucket *= 2
    bucket = min(bucket, max_len)
    print(
        f"Confidence calibration: {len(examples)} labeled completions, "
        f"max {longest} tokens, padded to {bucket}", flush=True,
    )
    sequences = [
        (_encoded(tokenizer, example, bucket), label)
        for example, label in examples
    ]
    progress = work / "confidence_head.npz"
    if progress.exists():
        stored_head, step, total_steps = load_progress(progress, fingerprint)
        if total_steps != max_epochs * len(sequences):
            raise ValueError(
                "Calibration epochs changed; use same epoch count or "
                "move the old checkpoint explicitly"
            )
        head = jax.tree.map(jnp.asarray, stored_head)
    else:
        head = params["confidence_head"]
        step = 0

    maximum = max_epochs * len(sequences)
    end = calibration_end_step(
        step, maximum, steps_per_run, run_to_completion=run_to_completion,
    )
    print(
        f"Confidence calibration: resuming from step {step}/{maximum}; "
        f"running {end - step} step(s) in this one-shot job "
        f"({'all remaining' if run_to_completion else 'bounded slice'}).",
        flush=True,
    )
    if step == maximum:
        print(
            "Confidence calibration already complete; existing checkpoint "
            "preserved. Export manually only after held-out evaluation.",
            flush=True,
        )
        return {
            "steps_complete": step,
            "steps_total": maximum,
            "finished": True,
            "mean_slice_loss": None,
            "head_checkpoint": str(progress),
        }

    model = SimpleAttentionNetwork(config)
    # The upstream head method uses stop_gradient on hidden cells, keeping
    # the backbone frozen. Trainable pytree consists exclusively of head.
    frozen = {key: value for key, value in params.items()
              if key != "confidence_head"}
    optimizer = optax.chain(
        optax.clip_by_global_norm(1.0),
        optax.sgd(learning_rate=learning_rate),
    )
    state = optimizer.init(head)

    # One compilation per invocation. The backbone is a dynamic JIT
    # argument and is frozen: only head_params receive gradients.
    grad_fn = make_confidence_grad_fn(model)
    losses: list[float] = []
    while step < end:
        # Rotate scenario order in a deterministic, reproducible way.
        index = (step * 73) % len(sequences)
        tokens, label = sequences[index]
        token_batch = jnp.asarray(tokens[None, :])
        targets = jnp.asarray([label], dtype=jnp.float32)
        loss, grads = grad_fn(head, frozen, token_batch, targets)
        loss_value = float(loss)
        if not np.isfinite(loss_value):
            raise RuntimeError("Nonfinite head calibration loss; stopping")
        updates, state = optimizer.update(grads, state, head)
        head = optax.apply_updates(head, updates)
        if not all(bool(jnp.all(jnp.isfinite(x)))
                   for x in jax.tree.leaves(head)):
            raise RuntimeError("Nonfinite head weights; refusing checkpoint")
        step += 1
        losses.append(round(loss_value, 6))
        save_progress(
            head, progress,
            step=step, fingerprint=fingerprint, losses=losses,
            total_steps=maximum,
        )
        print(
            f"Local confidence step {step}/{maximum}: "
            f"binary loss {loss_value:.4f}", flush=True,
        )
    return {
        "steps_complete": step,
        "steps_total": maximum,
        "finished": step >= maximum,
        "mean_slice_loss": round(float(np.mean(losses)), 6) if losses else None,
        "head_checkpoint": str(progress),
    }


def export_calibrated_candidate(work: Path) -> Path:
    """Export merged LoRA + the locally *trained* confidence head, offline.

    Does NOT create approved.cact or approved.json. Strict held-out model
    evaluation is still required before the inference add-on may use it.
    """
    import jax.numpy as jnp
    from needle.model.architecture import effective_kv_window
    from needle.model.export import (
        read_tokenizer_blob,
        write_export,
    )
    from needle.model.quantize import WEIGHT_BITS

    checkpoint = work / "needle3.safetensors"
    adapter = work / "needle_lora.safetensors"
    dataset = work / "train.jsonl"
    progress = work / "confidence_head.npz"
    base_cact = work / "needle3.cact"
    for file in (checkpoint, adapter, dataset, progress, base_cact):
        if not file.is_file():
            raise FileNotFoundError(
                f"Missing {file}; download both base files and finish head training"
            )
    fingerprint = data_fingerprint(checkpoint, adapter, dataset)
    head, step, total_steps = load_progress(progress, fingerprint)
    # Do not export partial experiments as candidates.
    # Step completion is checked by caller using the same parameters.
    if step < total_steps:
        raise ValueError(
            f"Calibration incomplete ({step}/{total_steps}): "
            "finish the remaining slices before export"
        )
    params, config = load_local_model(checkpoint, adapter)
    # Keep nested param structure intact for Flax export.
    import jax
    params["confidence_head"] = jax.tree.map(jnp.asarray, head)
    output = work / "candidate-local-confidence.cact"
    staged = work / "candidate-local-confidence.pending.cact"
    info = write_export(
        params, config, str(staged), bits=WEIGHT_BITS,
        tokenizer=read_tokenizer_blob(str(base_cact)),
        kv_window=effective_kv_window(config),
    )
    if not staged.is_file() or staged.stat().st_size < 1024:
        raise RuntimeError(f"Needle export did not create valid file: {info}")
    os.replace(staged, output)
    print(
        f"Exported local confidence candidate: {output} "
        "(NOT approved; benchmark required)", flush=True,
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resumable fully-local Needle 3 post-hoc confidence training"
    )
    parser.add_argument("command", choices=("calibrate", "export"))
    parser.add_argument("work", type=Path)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument(
        "--all", action="store_true",
        help="Calibrate all remaining steps in this one-shot invocation; "
             "continue from the atomic confidence_head.npz checkpoint",
    )
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--max-len", type=int, default=384)
    args = parser.parse_args(argv)
    if args.command == "calibrate":
        summary = run_calibration(
            args.work, steps_per_run=args.steps,
            max_epochs=args.epochs, max_len=args.max_len,
            run_to_completion=args.all,
        )
        print(json.dumps(summary, sort_keys=True), flush=True)
    else:
        if args.all:
            parser.error("--all is only supported with calibrate")
        export_calibrated_candidate(args.work)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
