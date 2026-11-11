# KURA optimized effect — offline archive experiment

The experimental offline archive creates individual Text+ clips with Montserrat Black and the KURA_Paper_Text_Optimized Fusion effect, which remains separate in Resolve. The archive includes the effect package and installers. Montserrat must already be installed. Resolve 21.1 round-trip verified two 30 fps titles and rendered the first with the paper effect.

Limits: titles over 125 frames are rejected because effect timing has not been verified beyond the captured template. The current Resolve bridge copies Fusion compositions without separate Fusion effects and does not implement this behavior. No changes here make the bridge use the optimized effect. The offline DRA exporter supports verified H.264 sources and converts stereo source audio to mono in an archive-only copy; original media is not modified. Multichannel audio remains unsupported. Do not release this experiment as a complete bridge/offline implementation.

Bridge experiment: a DRT copy can replace the specifically identified generated carrier with a native Text+ plus the optimized Fusion effect. Resolve 21.1 imported the rewritten timeline and rendered it correctly in a QA project. The helper is not wired into APPLICA: DRT import creates a new timeline and cannot safely change an existing timeline in place through the public scripting API. Source media, markers, other tracks and active-timeline behavior still require end-to-end validation before release.

The KURA Natale project was exported and restored in Resolve with original video, stereo-to-mono audio, 104 subtitles, 30 titles and 15 selected generic clips. The H.264 video stream was checked byte-for-byte; additional phrase-specific B-roll was not selected in the saved project.
