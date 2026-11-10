# KURA Paper Text effect: experimental build

This effect accepts the rendered output of an existing Text+ as its input. Text,
font, color, size, spacing, alignment and position stay on the original Text+;
all 19 KURA paper, texture, motion and shadow input controls remain exposed by
the effect. The original KURA title is not overwritten.

An AutoDomain node is inserted immediately after the Text+ input; it narrows the
domain of definition without lowering the physical frame resolution. On Resolve
Studio 21.1 the input-domain optimization produced byte-identical RGB stills on a
gray background for `wow!` at three frames and for a long title and a two-line
title at two frames each. The actual generated macro loads in Fusion and its
texture, motion and shadow controls modify their target nodes. The installer was
tested in an isolated Windows profile; macOS and installing/dragging the effect
in the Resolve Edit library remain untested.

Gallery still-capture timings varied widely between runs and are not playback
FPS. They do not establish a reliable speedup or real-time playback. More tests
are needed with other fonts, shadows, colors, nonstandard frame sizes, user
settings and complete animations. The effect is experimental, not a substitute
for the full-fidelity KURA title until those checks pass.
