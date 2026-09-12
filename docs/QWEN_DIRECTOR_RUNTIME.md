# Optional local Qwen Director runtime

The offline Director Engine works without these models. `director_benchmark` never downloads weights: it accepts a dedicated runtime `--model-root`, checks complete local weight shards and isolated packages, and records `UNAVAILABLE` rather than simulating inference. Keep model/cache/media artifacts outside Git; do not reuse ComfyUI's environment.

## Roles and verified upstream size

| Role | Model | Upstream repository size | Runtime adapter |
| --- | --- | ---: | --- |
| ASR | [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B/tree/main) | 4.7 GB | optional `qwen-asr` |
| Word alignment | [Qwen3-ForcedAligner-0.6B](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B/tree/main) | 1.84 GB | optional, paired with ASR |
| Director/query planner; optional judge | [Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B/tree/main) | 9.34 GB | optional Transformers local loader |
| Embedding | [Qwen3-VL-Embedding-2B](https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B/tree/main) | 4.27 GB | optional Sentence Transformers; text/image/video **keyframe** |
| Reranking | [Qwen3-VL-Reranker-2B](https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B/tree/main) | 4.27 GB | optional CrossEncoder metadata path; visual-capable runner remains replaceable |

The optional [Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B/tree/main) is 19.3 GB and is not the baseline. The five baseline repositories together are about **24.4 GB of weight files before activations, KV cache, CUDA context and memory allocator overhead**. This is a storage/weight-memory lower bound, not a measured peak VRAM requirement. For sequential operation, budget roughly 12–16 GB VRAM for the 4B Director and 6–9 GB for each 2B visual model as provisional engineering estimates; benchmark actual peaks before enabling simultaneous residency. CPU RAM and loader transient peaks also require measurement. Do not infer that all roles will coexist on a 32 GB card.

On this workstation the read-only `nvidia-smi` probe on 2026-09-12 reported **RTX 4090, 24,564 MiB total / 19,112 MiB free**, driver 616.56—not the assumed RTX 5090 32 GB. Neither the repo `.venv` nor isolated ASR venv contains `torch`, `transformers`, `sentence_transformers`, `qwen_asr` or `qwen_vl_utils`; the dedicated runtime model root has no Qwen weights. No Qwen inference or VRAM/RAM peak was measured. A separate global Hugging Face cache has Qwen3-VL-2B-Instruct variants, which are **not** the requested embedding/reranker/Director models and were not reused.

The [Qwen3-ASR model card](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) recommends an isolated Python 3.12 environment and `qwen-asr`; forced alignment supplies timestamps when the aligner is configured. The [embedding](https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B) and [reranker](https://huggingface.co/Qwen/Qwen3-VL-Reranker-2B) cards document Sentence Transformers usage and, for their Transformers examples, `transformers>=4.57.0`, `qwen-vl-utils>=0.0.14`, `torch==2.8.0`. The [Qwen3.5 card](https://huggingface.co/Qwen/Qwen3.5-4B) states that current Transformers support is required. These are upstream instructions, not packages installed by this task.

## Safety and current capability boundary

- Director JSON has exactly `action`, `query`, `reason`, `parameters`; one repair attempt, then deterministic fallback. Generation uses greedy decoding when a local model is present.
- Local asset candidate indexing checks `client_id` before embedding. Video candidates require an explicit local keyframe; filenames are never silently embedded as text. Embedding and reranker scores plus provider provenance are retained in the plan/report.
- The default optional visual judge flag is OFF. The included CrossEncoder runner scores metadata text; a truly visual rerank runner using candidate pixels is a separate capability and is **not** claimed as exercised.
- The Qwen benchmark runs on the same persisted transcript/beat outline/assets as the heuristic baseline and reports missing roles truthfully. There is no model auto-download path in the benchmark.

Before a real model smoke run, choose a specific isolated runtime and authorize at least one multi-GB weight download plus its runtime dependencies. Start with **one** role at a time; measure VRAM/RAM and output quality before considering 9B, simultaneous model residency or quantization.
