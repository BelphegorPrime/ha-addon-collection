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
**prepare → download → download_base → train → calibrate_all → export_local → evaluate_local**. All steps run in the isolated trainer
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

## v0.2.5: real held-out offline evaluation

After `export_local`, select `mode: evaluate_local` for a read-only test
that requires all 36 untouched six-language scenarios. This mode evaluates
both `needle3.cact` (baseline) and the exported
`candidate-local-confidence.cact` through the **native Needle 3 engine**
bundled at image build time. It uses `Needle.complete()` with inert JSON
tool descriptions and NEVER `Needle.run()` or any Home Assistant API.
Tool calls in the outputs are **inspected only**, never executed.

In a separate JAX pass it compares the trained confidence-head's scores on
each held-out correct completion versus one deliberately wrong completion,
reporting ranking accuracy, Brier score, and locale breakdown. Those head
probabilities are *float32 pre-export diagnostics*, **not native combined
confidence**, which is measured independently from the `.cact` engine.

The full report is saved atomically to
`/share/needle-training/evaluation/test-report.json`. A `NO_GO` verdict
is expected if there is no increase in accepted correct actions versus the
base, unsafe tool approval, regression in correct no-action rejections,
missing native confidence, or insufficient measurement. The process exits
with a nonzero status for `NO_GO` **after saving the report**; check
the report even if the HA add-on job shows an error.

Nothing is auto-approved. Even `CANDIDATE_FOR_MANUAL_REVIEW` is not
permission to deploy to Home Assistant. See [DOCS.md](DOCS.md) for the
interpretation and safety limitations.

## v0.2.6: diagnose before retraining

Run `mode: diagnose_local` (plus `confirm_resource_use: true`) to
re-analyze the saved native baseline/candidate test report in seconds,
without rerunning JAX or inference. Inspect
`/share/needle-training/evaluation/diagnosis.json` for failures by scenario,
language and family, and a **diagnostic-only** confidence threshold sweep.

Run `mode: prepare_experiment` to stage a separate train-only augmentation
of 96 multilingual safety and positive-command examples, without replacing
the existing checkpoint, LoRA, candidate, or held-out test data.
This creates `/share/needle-training/experiments/v026/` (312 training
examples, unchanged 36 validation and 36 test). **No training occurs.**
The original root dataset and `train` mode remain unchanged; see [DOCS.md](DOCS.md).

No new mode approves the candidate, executes Home Assistant actions, or
lowers the production confidence threshold.

## v0.2.7: separate experiment workflow (no root model writes)

With `prepare_experiment` already completed, follow five manually selected
modes: `experiment_train` → `experiment_calibrate_all` →
`experiment_export` → `experiment_validate` → `experiment_test`.
All outputs are placed only under `experiments/v026/`; the old model,
LoRA, calibration checkpoint, evaluation and native test dataset remain
untouched. The new 312-example training set produces 1,248 confidence
steps at two calibration epochs.

`experiment_test` refuses to access the unchanged held-out test dataset
unless a valid, successful independent 36-case validation report for
the exact same candidate has already been saved. A validation `NO_GO`
produces a JSON report and a deliberate nonzero exit; do not bypass this
gate. **No automatic approval or Home Assistant action occurs.**
See [DOCS.md](DOCS.md) for exact modes, output paths, and resource settings.

## v0.2.8: memory ceilings are not upfront RAM allocations

`memory_limit_mib` remains the **maximum allowed resident worker memory**.
It no longer requires that entire amount to be available at startup.
Jobs start when the host has at least
`reserve_memory_mib + 512 MiB` available, while the existing watchdog
checks both actual process-group RSS and the Home Assistant free-RAM
reserve throughout execution. A genuine 6 GiB allocation still needs
enough physical host headroom, or the worker will be stopped to protect
Home Assistant. The watchdog is best effort; it is not a cgroup quota.
See [DOCS.md](DOCS.md) for details.
