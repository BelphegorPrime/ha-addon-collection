"""Fully local, resumable Needle 3 confidence-head calibration and model export.

Only a standalone Home Assistant *trainer* add-on may run this module. Never
approve an action or replace a production model here. Upstream local LoRA
discards the confidence head; this trains it against matching/mismatching
tool-call completions and exports it with the merged adapter instead.
"""

from __future__ import annotations

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
) -> None:
    """Atomic, non-pickle checkpoints; optimizer is deliberately stateless."""
    from flax.traverse_util import flatten_dict

    arrays = {
        "/".join(key): np.asarray(value)
        for key, value in flatten_dict(head).items()
    }
    metadata = json.dumps(
        {"version": 1, "step": step, "fingerprint": fingerprint,
         "recent_loss": losses[-10:]},
        sort_keys=True,
    )
    arrays["__meta__"] = np.asarray(metadata)
    staged = progress.with_suffix(".next.npz")
    with staged.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staged, progress)


def load_progress(progress: Path, fingerprint: str) -> tuple[dict, int]:
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
        return unflatten_dict(arrays), int(info["step"])


def load_local_model(checkpoint: Path, adapter: Path):
    """Reuse exactly upstream Needle's local LoRA merge (no downloads)."""
    from needle.model.checkpoints import read_adapter
    from needle.model.finetune import merge_lora
    from needle.model.run import load_checkpoint

    base, config = load_checkpoint(str(checkpoint))
    tuned = read_adapter(str(adapter))
    if not tuned or not tuned.get("lora"):
        raise ValueError("Missing or malformed Needle LoRA adapter")
    import jax.numpy as jnp

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


def run_calibration(
    work: Path, *,
    steps_per_run: int = 8,
    max_epochs: int = 2,
    max_len: int = 384,
    learning_rate: float = 0.0001,
) -> dict:
    """Execute a small bounded slice, saving trainable head after every step.

    Frozen LoRA-merged backbone; only confidence_head gradients are computed.
    No upload or automatic promotion. Repeated starts continue with the next
    slice; momentum-free SGD needs no unsafe optimizer-state deserialization.
    """
    if not 1 <= steps_per_run <= 32:
        raise ValueError("steps_per_run must be 1..32")
    if not 1 <= max_epochs <= 5 or not 128 <= max_len <= 768:
        raise ValueError("Invalid epochs or maximum sequence length")
    import jax
    import jax.numpy as jnp
    import optax
    from needle.model.architecture import SimpleAttentionNetwork
    from needle.model.finetune import read_examples
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
    sequences = [(_encoded(tokenizer, row, max_len), label)
                 for row, label in examples]
    progress = work / "confidence_head.npz"
    if progress.exists():
        stored_head, step = load_progress(progress, fingerprint)
        head = jax.tree.map(jnp.asarray, stored_head)
    else:
        head = params["confidence_head"]
        step = 0

    model = SimpleAttentionNetwork(config)
    # The upstream head method uses stop_gradient on hidden cells, keeping
    # the backbone frozen. Trainable pytree consists exclusively of head.
    frozen = {**params, "confidence_head": None}
    optimizer = optax.chain(
        optax.clip_by_global_norm(1.0),
        optax.sgd(learning_rate=learning_rate),
    )
    state = optimizer.init(head)

    def loss_fn(head_params, tokens, label):
        current_params = {**frozen, "confidence_head": head_params}
        logits = model.apply(
            {"params": current_params}, tokens,
            method=SimpleAttentionNetwork.forward_confidence,
        )
        return optax.sigmoid_binary_cross_entropy(
            logits.astype(jnp.float32), label
        ).mean()

    # One compilation per invocation. Only one logical CPU is allocated by
    # the parent add-on; JAX threads are limited in the subprocess env.
    grad_fn = jax.jit(jax.value_and_grad(loss_fn))
    losses: list[float] = []
    maximum = max_epochs * len(sequences)
    end = min(step + steps_per_run, maximum)
    while step < end:
        # Rotate scenario order in a deterministic, reproducible way.
        index = (step * 73) % len(sequences)
        tokens, label = sequences[index]
        token_batch = jnp.asarray(tokens[None, :])
        targets = jnp.asarray([label], dtype=jnp.float32)
        loss, grads = grad_fn(head, token_batch, targets)
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
    head, step = load_progress(progress, fingerprint)
    # Do not export partial experiments as candidates.
    # Step completion is checked by caller using the same parameters.
    if step < 1:
        raise ValueError("No calibrated confidence steps")
    params, config = load_local_model(checkpoint, adapter)
    params["confidence_head"] = jnp.asarray(head) if isinstance(head, np.ndarray) else {
        name: jnp.asarray(value) if isinstance(value, np.ndarray) else value
        for name, value in head.items()
    }
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
