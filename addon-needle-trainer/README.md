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
**prepare → download → download_base → train → calibrate (repeat in
small batches) → export_local**. All steps run in the isolated trainer
container and require manual confirmation; only the two downloads use
the internet. The default slice trains eight confidence-head examples
per start and resumes from an atomic checkpoint. Weak hosts may still
run out of RAM.

The resulting `candidate-local-confidence.cact` includes the locally
trained post-hoc head, but its calibration and safety are **not proven**.
No model is auto-promoted; a held-out, six-language benchmark and
independent review are required before setting up `approved.cact`.


**v0.2.1 offline tokenizer fix:** `download` now also fetches the official
Needle 3 `tokenizer.model` and `tokenizer.vocab` into
`/share/needle-training/tokenizer/`. If you already have the checkpoint but
training failed with `HF_HUB_OFFLINE=1`, select `download_tokenizer` once,
then return to `train`. No checkpoint redownload is required.
