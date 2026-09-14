# RAMBLA Reference Style Calibration V1

Status: supporting analysis for the approved Editorial Intelligence + StyleDNA V1 plan. This document does not broaden implementation scope and does not authorize Resolve mutation.

## Purpose

Translate the two user-supplied editorial reference videos into measurable style targets and acceptance criteria that can be consumed by the StyleDNA fingerprint/analyzer and by the old-vs-new sourcing benchmark.

The references are intentionally kept as two separate style families rather than averaged into one generic taste profile.

## Reference family A — Factanza-like evidence/editorial

Observed editorial character:

- Approximate duration: 179 s.
- Approximate visually meaningful changes: ~40.
- Approximate mean interval between major visual changes: ~4.5 s.
- Approximate median insert interval: ~3.9 s.
- Speaker remains an anchor for much of the piece; evidence frequently appears as an overlay/composite rather than replacing the speaker full-screen.
- Strong preference for exact receipts and evidence: newspaper/article screenshots, historical stills, named people, TV/news archive, charts, documents, exact-event material.
- Generic stock is rare and should be treated as a fallback of last resort.
- Horizontal/static evidence remains editorially valuable when composition is good; it should not be rejected merely for not being native 9:16.
- Typical presentation modes: speaker + evidence above, document/card overlay, split layout, selective full-frame archival cutaway.
- Captions are bold/high-contrast and can emphasize key terms; caption styling is part of the visual identity but should remain separate from evidence relevance scoring.

Initial StyleDNA targets:

- `speaker_persistence`: 0.80–0.88
- `coverage_density`: 0.50–0.65
- `median_insert_seconds`: 3.4–4.3
- `split_layout_preference`: high
- `still_document_tolerance`: very high
- `generic_stock_penalty`: very high
- `exact_evidence_bonus`: very high
- `source_native_bonus`: medium
- route priority: `RECEIPT > ARCHIVAL > ENTITY > PRODUCT_UI > CLOSE_SEMANTIC_EDITORIAL > STOCK`

## Reference family B — Olimpia-like social/kinetic

Observed editorial character:

- Approximate duration: 81 s.
- Approximate visually meaningful changes: ~57.
- Approximate mean interval between changes: ~1.4 s.
- Approximate median interval: ~1.2 s.
- More than ~80% of the observed shots/inserts are <=2 s.
- Frequent return to face, but much more aggressive replacement/cutaway rhythm than the evidence/editorial family.
- Strong use of source-native social clips, interviews, named-person/event footage, profiles/posts, UGC and cultural references.
- Generic stock is still uncommon; specificity and social authenticity matter more than polish.
- Visual grit/compression/native captions can be acceptable or desirable when the source is authentic.
- Full-frame cutaways are common; non-vertical sources can still be used if the moment is stronger than a mediocre portrait alternative.

Initial StyleDNA targets:

- `speaker_persistence`: 0.55–0.70
- `coverage_density`: 0.75–0.90
- `median_insert_seconds`: 0.9–1.7
- `full_screen_preference`: high
- `visual_grit_tolerance`: high
- `cultural_reference_tolerance`: medium-high
- `generic_stock_penalty`: very high
- `source_native_bonus`: very high
- route priority: `SOURCE_NATIVE_SOCIAL > EXACT_ENTITY_EVENT > EXACT_RECEIPT > CULTURAL_REFERENCE > CLOSE_SEMANTIC_EDITORIAL > STOCK`

## Shared editorial law

Both references obey the same core hierarchy even though their pacing differs:

`exact evidence > source-native exact subject/event > culturally meaningful specific reference > semantically close editorial material > generic stock`

A visually clean but generic clip must not beat a rougher exact receipt solely because its embedding score or technical quality is higher.

## Candidate acceptance rubric

Every proposed visual should expose independent scores. A single semantic similarity number is insufficient.

Required dimensions:

- `semantic_relevance`: does it actually depict the spoken idea?
- `evidence_specificity`: is it the exact person/event/post/article/product rather than a category-level substitute?
- `editorial_quality`: would an editor willingly keep this shot in a published reel?
- `source_authority_authenticity`: original/official/source-native vs repost/compilation/generic.
- `style_fit`: fit to the active StyleDNA family/mix.
- `composition_usability`: can it be meaningfully composed in a vertical reel, including split/card layouts?
- `technical_quality`: resolution, legibility, corruption, severe watermark/UI problems.
- `diversity_novelty`: does it avoid repeating the same source, motif or visual idea?

Hard gates precede weighted ranking. Style can break a close tie but cannot rescue a semantically wrong candidate.

## Quality-floor behavior

A slot must not be filled just because the search returned something.

If fewer than two candidates pass the editorial/evidence floor:

1. expand/refine exact queries;
2. try the next source class in the route-specific strategy;
3. widen timestamp search within promising long-form sources;
4. consider still/document/composite presentation when appropriate;
5. only then descend toward generic semantic material;
6. if nothing strong passes, emit `NO_BROLL_QUALITY_FLOOR` with reason.

The system must never silently stretch or reuse one mediocre generic clip across multiple unrelated semantic chunks.

## A/B proposal requirement

For a normal B-roll slot, A and B should both be genuinely usable and meaningfully different. Diversity can be achieved by source class, shot type, source, visual motif, or presentation mode.

Examples of valid A/B diversity:

- exact article screenshot vs original interview clip;
- official product UI vs source-native creator demonstration;
- historical photo vs archival TV clip;
- original social post vs exact-event footage.

Two near-identical tutorial clips from the same creator are not strong A/B merely because the URLs differ.

## Presentation-aware selection

Do not reject strong evidence because it is horizontal or static. Candidate ranking should consider a presentation recommendation:

- `FULL_FRAME_CUTAWAY`
- `SPEAKER_PLUS_EVIDENCE_TOP`
- `SPLIT_VERTICAL`
- `DOCUMENT_CARD`
- `PICTURE_IN_PICTURE`
- `STILL_KEN_BURNS`
- `NO_BROLL`

The score should answer both “is this the right visual?” and “can this visual be made editorially useful in the active style?”.

## Benchmark acceptance criteria

The old-vs-new benchmark should measure more than retrieval similarity.

Primary human-facing metrics:

- `keep_rate`: percentage of proposal A/B candidates the user would actually keep.
- `exact_evidence_rate`: percentage of evidence-required slots served by exact/near-exact evidence rather than generic concept footage.
- `weak_filler_rate`: percentage of proposals that are technically relevant but editorially poor.
- `ab_useful_rate`: percentage of B-roll slots where both A and B are genuinely usable.
- `source_motif_repetition_rate`: repeated source/channel/motif across adjacent slots.
- `no_broll_precision`: whether `NO_BROLL_QUALITY_FLOOR` is chosen instead of weak filler at the right times.

Secondary metrics:

- Qwen coarse/final scores;
- source-class distribution;
- crop/composition usability;
- acquisition bytes and latency;
- rights/provenance completeness;
- percentage of selected proposals requiring bounded timestamp refinement.

## Initial pass/fail gate for Editorial Intelligence V1

Before calling the new selector better than the current semantic-only baseline, require all of the following on a representative multi-minute transcript:

- every B-roll slot has >=2 proposals or an explicit quality-floor failure state;
- no proposal with a hard semantic/evidence rejection is selected;
- exact evidence materially outranks generic stock for exact-claim/entity routes;
- generic stock is not selected while a stronger eligible exact/source-native candidate exists;
- A/B diversity rule is satisfied for normal successful slots;
- repeated same-source/same-motif usage is visible and penalized;
- review output exposes all component scores, source class, provenance, source timestamp/window and recommended presentation mode;
- `resolve_calls=0` throughout Analyze/Review benchmark execution.

## Practical default mix for current development

Until the user explicitly chooses otherwise, use the two fingerprints independently and support a mix. A sensible development default is:

- 70% `factanza_evidence_editorial`
- 30% `olimpia_social_kinetic`

This is a calibration default, not permanent learning. It must remain an inspectable, versioned parameter and may be changed only explicitly.
