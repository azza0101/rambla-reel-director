# Optional GPU video reader: implementation and evidence

The worker can use NVIDIA PyNvVideoCodec 2.2.3 to keep at most three source decoders alive and read sparse frames in batches. Source PTS are checked for every retained frame; Sony preroll is calibrated per file. Unsupported media and failures fall back to the existing reader. Active-speaker windows retain 25 fps; other source rates keep the original FFmpeg resampler. Existing analysis caches remain valid.

Benchmark on three 4K25 sources totalling 981.12 seconds, same original audio and same models, fresh analysis caches:

| Path | Preparation + shot/active-speaker analysis |
| --- | ---: |
| Original reader | 224.53 s |
| Full GPU H.264 proxy, including creation | 181.27 s |
| Persistent batched NVDEC on original sources | 130.86 s |

Shot labels: 490/490 comparisons identical. Active-speaker status: 23/24 identical, one baseline unknown became absent. Timestamp checks: 1693 passed. This does not establish equivalence on all media or measure transcription, LLM planning or Resolve application. Already cached active-speaker requests took approximately 0.2 seconds for the same 24 requests with either path.

The isolated distributable Python runtime was tested with the real decoder on three source frame indices; all three source timestamp checks passed. No global Python environment, ComfyUI environment or driver was modified.

Distribution: pinned Windows cp313 wheel hash in runtime/requirements.lock. Keep the complete MIT and FFmpeg LGPL notices. Provide the verified official PyNvVideoCodec_2.2.3.zip source asset with the release (SHA-256 29f7c0694d683266c563aca9a4f8e979ba0c5dce8f0ccc1efe500073e0948be0). Its FFmpeg 9.0.1 source and accompanying binaries were inspected; the two x64 FFmpeg DLL hashes match the wheel exactly. Runtime libraries remain dynamically replaceable.

Primary references:
- https://developer.nvidia.com/pynvvideocodec
- https://docs.nvidia.com/video-technologies/pynvvideocodec/pynvc-api-reference/decoder.html
- https://catalog.ngc.nvidia.com/orgs/nvidia/resources/pynvvideocodec

Editorial planning changes on this branch have a separate verification status. Passing decoder tests must not be presented as proof of editorial quality.
