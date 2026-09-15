# Current status: external editorial import

The primary workflow is now the model-neutral external-plan import described in [EXTERNAL_EDITORIAL_PLAN.md](EXTERNAL_EDITORIAL_PLAN.md). It passes the manual-fixture live provider acceptance without any generative model calls. The local Qwen producer remains experimental and optional.

## Historical local Qwen gate

The prior first-eight KURA narrative gate failed: missing chunks and invented metaphorical visuals. The real shot-batch stage was not accepted. Model load was 10.8875 seconds; two failed narrative calls took 93.0008 seconds (2,585 input / 760 output tokens). These are failed-gate measurements, not a semantic-quality or speedup claim.

The new import workflow does not rely on that producer. No new Qwen generation was run for external-import acceptance, and the real KURA external editorial plan is a separate next step. Historical raw outputs remain local and are not published.
