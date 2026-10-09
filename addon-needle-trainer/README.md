# Needle Trainer (Experimental) — Home Assistant add-on

Run the multilingual LoRA training experiments from
[ha-needle-llm](https://github.com/BelphegorPrime/ha-needle-llm)
**on the same Home Assistant host** as the
[Needle inference add-on](../addon-needle), without installing JAX in
the inference container or changing the live assistant.

This is a separate, optional add-on in the **same repository** to keep
training isolated and manually controlled. No automated retraining,
model replacement or HA service execution occurs.

Read [DOCS.md](DOCS.md) before use. Full local workflow:
**prepare → download → download_base → train → calibrate_all → export_local**. All steps run in the isolated trainer
container and require manual confirmation; only the two downloads use
the internet. The default bounded `calibrate` slice trains eight confidence-head examples
per start. `calibrate_all` instead trains every remaining step in a single
manual run; both resume from the same atomic per-step checkpoint.
Weak hosts may still run out of RAM.

The resulting `candidate-local-confidence.cact` includes the locally
trained post-hoc head, but its calibration and safety are **not proven**.
No model is auto-promoted; a held-out, six-language benchmark and
independent review are required before setting up `approved.cact`.


**v0.2.1 offline tokenizer fix:** `download` now also fetches the official
Needle 3 `tokenizer.model` and `tokenizer.vocab` into
`/share/needle-training/tokenizer/`. If you already have the checkpoint but
training failed with `HF_HUB_OFFLINE=1`, select `download_tokenizer` once,
then return to `train`. No checkpoint redownload is required.


**v0.2.2 JAX compilation memory fix:** The old `memory_limit_mib`
was a virtual-address-space `RLIMIT_AS` which could crash XLA compilation
with `RESOURCE_EXHAUSTED: Failed to allocate buffer for Literal`.
The trainer now permits normal virtual address mappings while monitoring
actual resident RAM (including child workers) and the free-RAM reserve for
Home Assistant. It terminates the training subprocess group if either
budget is crossed. The monitor is best effort, **not a kernel-enforced
cgroup limit**; available memory and strict RSS guarantees depend on the
host OS and may still require a separate Linux container or host.


**v0.2.3 confidence calibration fix:** The local `calibrate` mode now
converts every NumPy-loaded Needle checkpoint tensor to JAX arrays before
differentiation, including Engram embedding tables. It also supplies the
frozen transformer as a dynamic JIT input, preventing huge XLA compiled
constants. CI now performs an actual tiny Needle Engram and confidence-head
forward/backward pass using the pinned JAX image.


**v0.2.4 resumable single-start calibration:** Select `mode: calibrate_all`
to continue from the existing `confidence_head.npz` (e.g., step 40 of 864)
and finish every remaining step in the same low-priority, offline run.
The 250 ms RAM watchdog, CPU affinity and reserve checks are unchanged.
Every successful step still writes an atomic checkpoint, permitting a later
manual restart after interruptions. The mode never runs automatically on
boot, never exports a model, and never promotes a model for HA actions.
`calibration_steps_per_run` remains relevant only to the bounded `calibrate`
mode. See [DOCS.md](DOCS.md#continuous-resumable-confidence-calibration-v024).
