# RAMBLA Cloud Web Runtime V1

Status: first deployable test runtime for colleagues. Resolve remains untouched.

## Goal

Run RAMBLA on a normal CPU cloud VM/container so the editor's own workstation is
only a web browser. No CUDA, local Qwen weights, Faster-Whisper model, ComfyUI or
Resolve installation is required by the colleague using the product.

The cloud machine still performs ordinary server work: HTTP requests, browser
automation when available, FFmpeg normalization/cutting, thumbnail/GIF generation,
downloads, caching and project storage. "GPU-free" means no local inference model is
loaded by the RAMBLA cloud runtime.

## Input modes

The Source panel accepts three primary inputs:

1. **VIDEO** — uploaded to the RAMBLA server. FFmpeg extracts/normalizes audio and
   Groq Whisper transcribes the audio in the cloud. The source video itself is not
   sent to the editorial Director.
2. **AUDIO** — uploaded directly. RAMBLA creates a silent synthetic timeline video
   on the server so the existing timing/retrieval contracts remain compatible, then
   sends only normalized audio to cloud ASR.
3. **TEXT** — paste the complete spoken transcript. ASR is skipped entirely. RAMBLA
   creates deterministic synthetic word timings at 2.5 words/sec for editorial
   planning. These timings are approximate because plain text contains no real
   timestamps.

For video/audio, the default cloud ASR is Groq
`whisper-large-v3-turbo`. The resulting RAMBLA transcript retains segment/word
timestamps when the provider returns them.

## AI/runtime split

- Editorial Director: Gemini/Groq API, transcript only.
- Audio/video transcription: Groq ASR API.
- B-roll/image search: provider/API/browser discovery on the server.
- Retrieval ranking in cloud mode: deterministic metadata/provider ranking
  (`RAMBLA_RETRIEVAL_RANKING=provider`), therefore no Qwen/GPU.
- TikTok/Instagram/Shorts: cloud mode forces `visual_verify=false`; no local Qwen.
- Envato: official Envato MCP discovery.
- Media prep: server CPU + FFmpeg/yt-dlp.
- Storage/cache: persistent server volume.
- Resolve calls: 0.

This first cloud build deliberately does **not** pretend that metadata-only ranking is
equivalent to the previous local Qwen visual verification. A later cloud-vision
ranker can restore visual frame judging by API without reintroducing a local GPU.

## Run with Docker

Copy the environment template without committing secrets:

```bash
cp cloud.env.example cloud.env
```

At minimum, fill `GROQ_API_KEY` for audio/video transcription. Configure
`GEMINI_API_KEY` and/or `GROQ_API_KEY` for the Director, plus stock/image provider
keys as needed.

Then:

```bash
docker compose -f docker-compose.cloud.yml up --build
```

Open:

```text
http://SERVER:8080/curation
```

The compose stack stores projects and retrieved media in the persistent
`rambla-data` volume. Deleting/recreating the application container does not delete
that volume.

## Deploying for colleagues

For a temporary internal test, place the container behind the hosting platform's
authentication/access-control layer (SSO, password protection, VPN or private
workspace). The application currently represents one shared RAMBLA workspace:
project-library entries are not separated into individual user accounts.

Do not expose an unprotected instance containing client media to the public internet.
API keys belong only in server environment variables/secrets.

## Social limitation

Authenticated TikTok/Instagram is the least cloud-portable part of the current
desktop workflow because manual login/CAPTCHA interaction previously depended on a
visible RAMBLA-owned browser window.

In cloud mode, FIND SOCIAL skips local-login-window verification and attempts the
server-side/public discovery path. It remains best-effort and may be blocked by
provider challenges. The cloud runtime does not bypass CAPTCHA or copy a colleague's
personal browser cookies. A dedicated remote-browser/session UX is a separate
follow-up before authenticated social can be called production-ready.

## Operational requirements

The container image installs:

- Python 3.12
- FFmpeg/ffprobe
- Chromium
- yt-dlp
- Pillow
- the RAMBLA Python package

No CUDA/NVIDIA runtime is required.

## Environment

Required/typical secrets:

- `GROQ_API_KEY`
- `GEMINI_API_KEY`
- `PEXELS_API_KEY`
- `GOOGLE_API_KEY` + `GOOGLE_CSE_ID`

Cloud defaults:

- `RAMBLA_RUNTIME_MODE=cloud`
- `RAMBLA_RETRIEVAL_RANKING=provider`
- `RAMBLA_PROJECT_ROOT=/data/projects`
- `RAMBLA_BROWSER_PROFILE_ROOT=/data/browser-profiles`

Optional:

- `RAMBLA_CLOUD_ASR_MODEL=whisper-large-v3-turbo`
- `RAMBLA_ASR_LANGUAGE=it`

## Acceptance boundary

Before calling this cloud runtime accepted, verify on a real deployed container:

- video -> cloud transcript -> Director -> image/video retrieval;
- audio-only -> cloud transcript -> Director;
- text-only -> no ASR -> Director;
- no Qwen/local-model load and no GPU requirement;
- project persistence after container restart;
- two browser clients can use distinct project IDs without artifact crossover;
- secrets are absent from project artifacts/logs;
- Resolve calls remain zero.

Authenticated TikTok/Instagram success is tracked separately from the GPU-free cloud
runtime acceptance.
