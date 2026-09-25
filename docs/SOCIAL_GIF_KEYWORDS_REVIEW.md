# Follow-up: retrieval fidelity, timeline GIFs, TikTok keyword discovery

The user's current beat_002 artifact uses clip-quality-15-social. Inspection found
all displayed TikTok entries unverified, repeated clip acquisition errors, and
`ranking_warning: Visual ranker unavailable: ValueError` on all three shots.

Root cause in the new thumbnail prefilter: missing client_id violated the existing
Qwen client-isolation guard. Fixed by passing the sourcing client_id explicitly.
A real local Qwen embedding smoke through that helper using a cached TikTok frame
completed in 39.45 s cold, visual_active=true, warning=null. No model installed,
no ASR/Director/provider search run. This is not proof of final beat relevance.

Instructional/how-to titles and vehicle-only ferry results are now rejected for
physical-action/passenger targets. Actual negative visual scores reject thumbnail
mismatches as well as overlays. TikTok accepts two supplied short keyword queries
per shot. Do not invent locations or force POV onto an exterior viewpoint.

Research: TikTok Help Center documents search matching, interaction/personalization
signals and filters. Creative Center Keyword Insights is advertising research,
not an organic clip-retrieval API. No documented no-overlay filter was established.
Sources:
- https://support.tiktok.com/en/using-tiktok/exploring-videos/how-tiktok-recommends-content
- https://ads.tiktok.com/resources/help/article/creative-center

Hover now renders an actual GIF, no video player. Six distributed timeline samples,
180x320, 64-color palette, 450 ms/frame. Prefer cached full download; otherwise use
YouTube storyboards or seek six remote frames, not full download. Real GIF generated
from user's cached TikTok full.mp4: 121521 bytes, 6 frames. First preparation can
still wait for provider metadata/frame retrieval; subsequent hover is cached.

Manual full download had access to live-session cookies, while sourcing tried
reading the locked Chrome profile DB. Sourcing now uses a token-protected loopback
cookie endpoint, writes only provider cookies transiently, removes them in finally,
and never opens another browser. Live authenticated acceptance remains pending.

Shorts provider login/CAPTCHA requests are surfaced explicitly; not bypassed and
not automatically retried. An already logged-in ordinary Chrome window does not
automatically authenticate the yt-dlp process.

572 tests pass; rendered UI JS syntax and backend compile pass. Local changes,
backend restart required. Current plan/transcript and existing selections untouched.
