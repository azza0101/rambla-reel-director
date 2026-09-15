# General-purpose curator: implementation and runtime blocker

## Implemented

- Domain-neutral `generate(prompt) -> JSON` Director boundary, strict shot schema, one repair attempt, no template/embedding planning fallback. Context includes whole transcript, previous/current/next chunks and timings. Generated plans are resumable; Director subprocess exits before embedding starts.
- KURA is a fixture alongside cybersecurity, cooking and personal finance. Mocked generator regressions verify the contract; they do not prove real model understanding.
- HD image filtering (long edge >=1024, short edge >=480, area >=500,000), decoded-preview measurements, dHash/exact dedupe, cross-chunk rejection and cache invalidation for provider/ranker/quality changes. Relevance floor 0.30 is provisional, pending real positive/negative calibration.
- Optional official Google Custom Search image adapter (`GOOGLE_API_KEY` and `GOOGLE_CSE_ID`), Pexels Photos when configured, Wikimedia 1280px previews. Only Wikimedia is configured in this environment. Google uses source image URLs where no HD thumbnail is available; deferred full-resolution acquisition still needs a provider-specific bounded-preview strategy there.
- Verified H.264 MP4/WebM playback contract. Pexels can materialize a bounded local clip and rank its frame; YouTube thumbnails remain explicitly labelled discovery. Every card exposes provider/source. Real MP4 probe rejects images and invalid durations. Inspect and Select stay separate.
- Fixed-height Console / Transcript + Visual Plan split; event JSON is expandable.
- Unique atomic JSON files with bounded sharing-violation retries. Cross-process stage lock. ASR DLL preflight and explicit CPU fallback, existing runtime only.

## Evidence

- 275 tests passed; backend compile passed, run with the existing Python 3.12 environment. `tools/run_workspace_tests.py` supplies ordinary workspace temp directories because pytest's mode-0700 directories become unreadable under this Windows sandbox; no ACL/system changes.
- Real ffmpeg preview: 3.52 seconds, H.264, `video/mp4`; JPEG remains discovery. JavaScript parse and card behavior checked with installed Node.
- Actual 1280x800 image decoded and duplicate rejected by perceptual/content identity.
- Existing faster-whisper runtime: CPU/int8, 19.75 seconds on a two-second KURA audio sample; explicit `CUDA ASR unavailable` event, no CUDA traceback. Full KURA ASR reused: 102.25-second source, 27 semantic chunks, analysis completion 100%.

## Existing-runtime inventory and blocker

Recursive inspection of `Z:\APP REEL TEST` found two preexisting project interpreters:

1. `qwen-embedding-smoke\venv\Scripts\python.exe`: Python 3.10.11, Transformers 4.57.6, Torch and Qwen3-VL Embedding implementation. No faster-whisper/CTranslate2. Transformers has `qwen3_vl`, but neither `qwen3_5` model registration nor `AutoModelForMultimodalLM`. Renaming the auto loader cannot add the missing Qwen3.5 architecture.
2. `qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe`: Python 3.12.12, faster-whisper 1.2.1, CTranslate2 4.8.2; no Transformers, Torch, llama_cpp or ollama package.

The only preexisting Qwen weights found were Qwen3-VL-Embedding-2B. No preexisting Qwen3.5-4B/9B or alternative generative weights/GGUF were found. Unreadable directories were test/ASR temporary paths, recorded in the local inventory.

Before the user's no-install correction arrived, Qwen3.5-4B weights and a separate `director-deps` directory had already been created under `qwen-embedding-smoke`. The attempted inference was stopped without accepted output. Those additions are outside Git, are **not preexisting-runtime evidence**, and are not automatically enabled. No further installation/download is authorized. No ComfyUI/global Python/PATH/CUDA changes occurred.

Production fails explicitly if no compatible Director is configured. `RAMBLA_DIRECTOR_PYTHON` and the opt-in `RAMBLA_DIRECTOR_DEPS` boundary allow a separately approved local runtime; neither installs nor downloads anything. Standard runtime never calls OpenAI/GPT/Codex.

**REAL_DIRECTOR_ACCEPTANCE_BLOCKED**: no accepted real Qwen3.5 generation on KURA or the three other domains. New-plan provider coverage, semantic precision, threshold calibration, actual Pexels playback and global KURA repetition statistics remain unproven. Do not label this milestone `GENERAL_PURPOSE_CURATOR_FIX_PUBLISHED` or `TESTABLE=YES` until those gates pass.

## Commands

From the plain workspace:

```powershell
& 'Z:\APP REEL TEST\qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe' tools/run_workspace_tests.py -q
& 'Z:\APP REEL TEST\qwen-embedding-smoke\editorial-intelligence-worktree\.venv\Scripts\python.exe' -m compileall -q backend
& 'Z:\APP REEL TEST\qwen-embedding-smoke\curation-ui-plain\tools\start_curation_acceptance.ps1'
```

The launcher loads the exact remote branch build. Analyze remains usable; sourcing requires the explicitly approved compatible Director runtime. Resolve remains frozen (`resolve_calls=0`).
