# Needle Trainer (Experimental) — Home Assistant add-on

Run the multilingual LoRA training experiments from
[ha-needle-llm](https://github.com/BelphegorPrime/ha-needle-llm)
**on the same Home Assistant host** as the
[Needle inference add-on](../addon-needle), without installing JAX in
the inference container or changing the live assistant.

This is a separate, optional add-on in the **same repository** to keep
training isolated and manually controlled. No automated retraining,
model replacement or HA service execution occurs.

Read [DOCS.md](DOCS.md) before use. Start with **prepare**, then
**download**, then **train** (each requires a manual start and confirmation).
Training is best-effort on weak hosts and might fail due to lack of RAM.

**A local Needle 3 LoRA export lacks calibrated confidence** and cannot be
deployed for automatic HA actions under Needle LLM's 0.8 confidence gate.
