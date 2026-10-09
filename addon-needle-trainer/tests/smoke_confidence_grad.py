"""Real JAX gradient regression for locally trained Needle confidence head.

Runs with the version-pinned upstream cactus-needle image but uses a
*tiny* random Needle model. Tests the engram gather + end-to-end Flax
backprop that previously failed with TracerArrayConversionError, without
downloading the user's checkpoint or running heavyweight full fine-tuning.
"""

from __future__ import annotations

import math

import jax
import jax.numpy as jnp
import numpy as np

from local_confidence import make_confidence_grad_fn, prepare_jax_backbone
from needle.model.architecture import SimpleAttentionNetwork, TransformerConfig


def main() -> None:
    cfg = TransformerConfig(
        vocab_size=128,
        d_model=32,
        num_heads=4,
        num_kv_heads=2,
        num_layers=2,
        qk_head_dim=8,
        v_head_dim=8,
        max_seq_len=32,
        embedding_dim=8,
        embedding_probes=2,
        embedding_queries=2,
        confidence_probes=2,
        confidence_queries=2,
        router_probes=2,
        router_queries=2,
        dtype="float32",
        flash=False,
        engram_orders=(2, 3),
        engram_heads=1,
        engram_slots=32,
        engram_layers=(1,),
        global_layers=(),
        sliding_window=0,
        qkv_conv_taps=0,
        mhc_lanes=2,
        remat=False,
        scan_unroll=1,
    )
    model = SimpleAttentionNetwork(cfg)
    tokens = jnp.asarray([[2, 4, 21, 22, 13, 0, 0, 0]], dtype=jnp.int32)
    params = model.init(
        jax.random.PRNGKey(7),
        tokens,
        method=SimpleAttentionNetwork.forward_confidence,
    )["params"]

    # Simulate the real Needle safetensors loader: *all* checkpoint
    # tensors arrive as NumPy ndarrays. Merge only the LoRA targets
    # would leave Engram tables as NumPy and trigger the original bug.
    checkpoint_params = jax.tree.map(np.asarray, params)
    assert any(isinstance(x, np.ndarray)
               for x in jax.tree.leaves(checkpoint_params))
    converted = prepare_jax_backbone(checkpoint_params)
    assert all(isinstance(x, jax.Array)
               for x in jax.tree.leaves(converted))

    head = converted["confidence_head"]
    frozen = {k: v for k, v in converted.items() if k != "confidence_head"}
    grad_fn = make_confidence_grad_fn(model)

    loss, grads = grad_fn(
        head, frozen, tokens, jnp.asarray([1.0], dtype=jnp.float32)
    )
    assert math.isfinite(float(loss)), f"invalid loss: {loss}"
    leaves = jax.tree.leaves(grads)
    assert leaves and all(bool(jnp.all(jnp.isfinite(x))) for x in leaves)
    # The head must receive actual (nonzero) gradients.
    assert any(bool(jnp.any(jnp.abs(x) > 0)) for x in leaves)
    assert jax.tree.structure(grads) == jax.tree.structure(head)
    print(
        f"Needle JAX engram + confidence backward OK, "
        f"loss={float(loss):.4f}; {len(leaves)} head leaves",
        flush=True,
    )


if __name__ == "__main__":
    main()
