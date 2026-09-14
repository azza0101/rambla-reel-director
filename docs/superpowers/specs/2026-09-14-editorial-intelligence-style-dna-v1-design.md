# RAMBLA Editorial Intelligence + StyleDNA V1 — Design

Status: **APPROVED IN CHAT on 2026-09-14; written-spec review pending**

Date: 2026-09-14

## 1. Why this design exists

The current RAMBLA sourcing path has proven the mechanics: semantic transcript understanding, YouTube/Shorts discovery, lightweight whole-source inspection, bounded acquisition, exact local trims, Qwen verification on final frames, A/B proposals, provenance, and review artifacts.

The remaining quality problem is editorial, not mechanical. A candidate can be semantically relevant and still be a weak B-roll choice: generic tutorial footage, low-value screen recordings, visually dull clips, duplicated visual ideas, weak source authority, intrusive overlays, or footage that merely mentions the concept instead of showing the exact evidence/person/event/product/article being discussed.

The user supplied two reference reels as external exemplars: one Factanza reel and one Olimpia Peroni reel. They are intentionally different, but they share one important principle:

> **Exact evidence / exact subject beats generic semantic similarity.**

This design turns that observation into an explicit editorial intelligence layer. It extends the approved Evidence Sourcing V2 and Taste Engine designs. It does not replace CoveragePlanner, VisualRoute, Qwen, SceneLocator, bounded acquisition, provenance, review, or Resolve Apply.

## 2. Product goal

RAMBLA should stop behaving like a semantic stock finder and start behaving like an experienced social-news editor.

For every visual opportunity, it should answer these questions in order:

1. **What is the narration actually asserting?**
2. **What visual would prove, identify, or concretize that assertion?**
3. **What source class is most appropriate?**
4. **Is the candidate editorially strong enough to deserve screen time?**
5. **Does it fit the active client/style fingerprint?**
6. **Can it be presented cleanly in a 9:16 composition without destroying the evidence?**
7. **If nothing strong passes the quality floor, should we simply stay on the speaker?**

A wrong or mediocre B-roll is worse than `NO_BROLL`.

## 3. Reference-derived style families

The two supplied exemplars must remain separate reference fingerprints, not be collapsed into one average style.

### 3.1 Factanza-like evidence/editorial mode

Observed editorial traits:

- the speaker remains the narrative anchor;
- inserts often function as **receipts/evidence**: article pages, headlines, archive, charts, event footage, named people, exact products/places, historical imagery;
- source-native imperfections are acceptable when they increase authenticity;
- many visuals are composited with the speaker rather than replacing the full frame;
- landscape, square, screenshots and documents remain useful if laid out intelligently;
- generic stock is rare and should be a late fallback;
- visual holds are generally calmer than the Olimpia-like mode;
- bold readable captions and highlighted keywords support the editorial hierarchy.

Default StyleDNA direction for this family:

- evidence specificity: very high;
- speaker persistence: high;
- insert density: medium/high;
- typical useful hold: roughly 2.5–5.0 s, content-dependent;
- still/document acceptance: high;
- generic-stock tolerance: low;
- split/composite layout tolerance: high;
- source-native social/news aesthetic tolerance: high.

### 3.2 Olimpia-like social/kinetic mode

Observed editorial traits:

- much faster alternation between speaker and external visuals;
- short, punchy inserts and frequent returns to the face;
- source-native social clips, interviews, original event footage, profiles/posts and recognizable cultural references are valuable;
- footage can be visually rough if it is specific, authentic and emotionally legible;
- the system should prefer an exact social/native moment over a cleaner but generic stock clip;
- visual rhythm is an editorial feature, not just a duration parameter.

Default StyleDNA direction for this family:

- evidence specificity: high;
- speaker persistence: medium/high but with frequent returns;
- insert density: high/very high;
- typical useful hold: roughly 0.8–2.8 s, with longer holds when evidence must be read;
- cultural/social-native tolerance: high;
- generic-stock tolerance: very low;
- fast alternation and short source windows: preferred.

### 3.3 Hybrid mode

RAMBLA should support interpolation between the two fingerprints instead of hard-coding only two presets.

A `style_mix` can express, for example:

```text
Factanza evidence/editorial: 0.70
Olimpia social/kinetic:      0.30
```

The active mix affects pacing, source-class preferences, layout behavior, quality thresholds and diversity, but never permits a semantically/factually wrong candidate to win.

## 4. New architectural layer: Editorial Intelligence

Introduce an editorial-quality layer between discovery/semantic verification and final candidate selection.

The new logical flow becomes:

```text
Timed semantic chunk
-> CoveragePlanner
-> VisualRoutePlanner
-> EvidenceIntentPlanner
-> SourceStrategyPlanner
-> discovery across source classes
-> coarse semantic verification
-> scene/window localization
-> bounded acquisition / screenshot capture
-> final Qwen semantic verification
-> EditorialQualityScorer
-> SourceAuthorityScorer
-> AestheticFitScorer / StyleDNA scorer
-> CompositionUsabilityScorer
-> Diversity/novelty pass
-> hard quality floor
-> proposal A/B or NO_BROLL
```

Semantic relevance remains necessary but is no longer sufficient.

## 5. EvidenceIntentPlanner

Before searching, each coverage slot must receive an explicit `EvidenceIntent` that describes what a strong visual would actually be.

Examples:

- narration names a person -> exact person in the relevant context, not a random portrait;
- narration references a statement/post -> screenshot or original post/article receipt;
- narration cites a statistic -> chart, report, dashboard, paper or publication source;
- narration discusses a product/app -> exact interface/demo/product shot;
- narration describes a historical event -> archival/repertory material from that event;
- narration references a viral clip -> original or directly related social artifact;
- narration explains an abstract mechanism -> explanatory graphic/demo, then concept footage only if needed;
- narration is purely connective or emotional -> speaker may be stronger than forced B-roll.

Persist:

- `evidence_intent_type`;
- `target_entities`;
- `target_event_or_claim`;
- `acceptable_visual_forms`;
- `unacceptable_substitutions`;
- `specificity_required`;
- `can_use_still`;
- `can_use_composite_with_speaker`;
- `fallback_route_order`.

## 6. SourceStrategyPlanner: search by editorial value, not provider convenience

The system must search source classes in an explicit priority order.

Default hierarchy:

1. `EXACT_RECEIPT` — original article/post/document/chart/page/search result/official statement.
2. `EXACT_ENTITY_EVENT` — footage or imagery of the exact person/event/place/product being discussed.
3. `SOURCE_NATIVE_SOCIAL` — original/near-original social clip, creator/interview/event footage.
4. `ARCHIVAL_REPERTORY` — relevant news/archive/history footage.
5. `PRODUCT_UI_DEMO` — exact interface/product workflow.
6. `CULTURAL_REFERENCE` — recognizable meme/film/reaction/reference when stylistically appropriate.
7. `CLOSE_SEMANTIC_EDITORIAL` — directly related contextual footage.
8. `GENERIC_STOCK` — last-resort fallback only.

The order can change per route/style profile, but generic stock should never outrank exact evidence merely because it has higher image quality.

### Provider implications

YouTube and YouTube Shorts remain useful but are not treated as the whole internet.

The architecture should support independent adapters for:

- YouTube / Shorts;
- web/article/image search and page capture;
- Instagram/Reels when available and authorized;
- TikTok when available and authorized;
- official sites / product pages / reports;
- stock providers as fallback.

The provider layer remains pluggable. A source class is not equivalent to one provider.

## 7. Multi-axis candidate scoring

Replace the practical dependence on a single semantic similarity score with inspectable score components.

Every final candidate should expose at minimum:

### 7.1 `semantic_relevance`

Does the actual selected segment visually/textually match the narration and EvidenceIntent?

Measured using the proven final-segment Qwen pass, not only thumbnails/titles.

### 7.2 `evidence_specificity`

How exact is the candidate?

Suggested interpretation:

- 1.00: exact post/article/event/person/action/product/claim;
- 0.75: same entity/event and clearly relevant context;
- 0.50: related subject but not the exact evidence;
- 0.25: generic concept footage;
- 0.00: merely keyword-adjacent.

This score should carry major weight in evidence-heavy styles.

### 7.3 `editorial_quality`

Measures whether the clip is actually worth showing.

Signals can include:

- visually legible action/subject;
- shot clarity and useful composition;
- motion/visual interest appropriate to the slot;
- absence of accidental UI clutter;
- absence of tiny unreadable content when it is not intentional evidence;
- no freeze/black/broken frames;
- no obvious low-value filler;
- no awkward intro/outro/card unless that is the evidence;
- no visually dead 3.5 s segment when a better moment exists nearby.

### 7.4 `source_authority_authenticity`

Measures whether the source is original, authoritative or close to original.

Prefer:

- official/primary source;
- original creator/account;
- authoritative news/archive/source;
- direct interview/event capture;

over:

- compilation;
- reaction repost;
- scraped mirror;
- generic tutorial mentioning the topic.

Authority is route-dependent: an original TikTok may be more authoritative for a viral social artifact than a polished news recap.

### 7.5 `style_fit`

How well does the candidate fit the active StyleDNA fingerprint?

Examples:

- evidence/documents score strongly in Factanza-like mode;
- source-native social clips and fast punchy moments score strongly in Olimpia-like mode;
- generic stock receives a penalty in both supplied exemplar families;
- long static software tutorials are penalized unless the exact UI/workflow is itself the evidence.

### 7.6 `composition_usability`

Replaces the simplistic idea that everything must become full-screen portrait.

The candidate can be usable as:

- full-screen 9:16;
- crop/reframe;
- speaker + evidence split layout;
- picture-in-picture;
- framed screenshot/document;
- blurred-background fill;
- subtle still zoom;
- top-card/bottom-speaker evidence composition.

The score should consider the best viable composition, not only a center crop.

### 7.7 `technical_quality`

Resolution, compression, frame integrity, readability, stable acquisition, etc.

Technical cleanliness should not overpower evidence specificity. A lower-resolution authentic archive clip can beat pristine generic stock.

### 7.8 `diversity_novelty`

Penalize repeated use of:

- the same source/video;
- nearly identical shots;
- the same visual motif across consecutive slots;
- too many node graphs/tutorial screens simply because the topic is AI.

## 8. Ranking and hard gates

Use a two-stage system: **eligibility gates first, weighted ranking second**.

### 8.1 Hard eligibility gates

Reject or force review when:

- final-segment semantic relevance is below threshold;
- evidence specificity is insufficient for a route that requires exact evidence;
- final segment is broken/blank/unreadable;
- provenance/rights state is unacceptable for the configured workflow;
- the subject cannot survive any allowed composition;
- candidate is a near-duplicate of proposal A and does not provide a meaningful B alternative;
- quality is below the active editorial floor.

If fewer than two candidates pass for a normal B-roll slot, RAMBLA should search additional source classes before settling.

If no strong candidate passes, use explicit `NO_BROLL_QUALITY_FLOOR` rather than presenting weak filler.

### 8.2 Weighted ranking

Suggested initial evidence/editorial weighting after gates:

```text
semantic_relevance            0.25
evidence_specificity          0.25
editorial_quality             0.15
source_authority_authenticity 0.10
style_fit                     0.10
composition_usability         0.08
technical_quality             0.04
diversity_novelty             0.03
```

These are starting calibration values, not permanent constants.

For a more Olimpia-like style, shift weight from longer-form evidence/readability toward style fit, source-native social value, kinetic quality and diversity. For a Factanza-like style, raise evidence specificity and receipt/source authority.

No taste weight may rescue a semantically wrong candidate.

## 9. EditorialQualityScorer design

Editorial quality should combine deterministic metrics and a multimodal judge, rather than rely only on embeddings.

### Deterministic checks

- actual frame resolution;
- black/frozen frame detection;
- excessive static hold when not intentional;
- severe letterboxing/cropping damage;
- duplicate-frame ratio;
- visible content occupancy / tiny central content;
- abrupt unwanted title-card boundaries inside the final clip;
- text/evidence readability proxies;
- watermark/UI occupancy where detectable;
- motion/shot-change profile.

### Multimodal judge

A local Qwen visual judge can score representative frames/window context using structured prompts such as:

- Is the important subject immediately understandable?
- Is this visually useful as a social-video insert?
- Is it generic filler or specific evidence?
- Does the shot contain distracting tutorial/player/UI elements?
- Is the relevant content large enough to read/recognize?
- Does this look like original/source-native footage or a low-value repost/compilation?

The judge should return structured components/reasons, not prose-only hidden decisions.

## 10. StyleDNA V1 schema additions

Extend `TasteProfile` with a `style_dna` object.

Suggested fields:

- `reference_profiles[]` with independent exemplar fingerprints;
- `active_style_mix`;
- `speaker_persistence_target`;
- `coverage_density_target`;
- `return_to_speaker_interval_distribution`;
- `insert_duration_distribution`;
- `hook_density_multiplier`;
- `route_preference_weights`;
- `source_class_preference_weights`;
- `generic_stock_penalty`;
- `exact_evidence_bonus`;
- `source_native_bonus`;
- `still_document_tolerance`;
- `cultural_reference_tolerance`;
- `split_layout_preference`;
- `full_screen_preference`;
- `subtitle_style_metadata`;
- `keyword_highlight_behavior`;
- `visual_grit_tolerance`;
- `minimum_editorial_quality`;
- `minimum_evidence_specificity_by_route`;
- `maximum_repetition_by_source_or_motif`.

The two user-provided reference reels seed two independent external exemplar profiles. Their source media itself must not be committed to Git.

## 11. Fingerprint analyzer upgrades

The existing TasteFingerprintAnalyzer design should be upgraded from simple cut/route statistics to a richer editorial fingerprint.

For each exemplar, extract:

- duration and major cut/visual-change timestamps;
- talking-head vs full-screen cutaway vs split/composite intervals;
- speaker return frequency;
- insert duration distribution;
- route/type classification;
- still vs video ratio;
- document/article/post screenshot usage;
- exact-person/event/archive usage;
- social-native/UGC usage;
- generic stock usage;
- visual density over time;
- hook/body/end pacing differences;
- composition types;
- source-native overlays/watermarks tolerance;
- caption placement/highlight behavior where measurable;
- representative frames and classification confidence.

The analyzer must keep exemplar-specific profiles so future reels can mix or compare them.

## 12. Speaker persistence and composition-aware coverage

CoveragePlanner should stop assuming each B-roll slot means replacing the whole picture.

Each coverage slot receives a `presentation_mode` proposal:

- `FULL_FRAME_CUTAWAY`;
- `SPEAKER_PLUS_EVIDENCE_TOP`;
- `SPEAKER_PLUS_EVIDENCE_SPLIT`;
- `PIP_EVIDENCE`;
- `DOCUMENT_CARD`;
- `SOCIAL_POST_CARD`;
- `ARCHIVE_FRAME`;
- `STILL_WITH_MOTION`.

This lets RAMBLA use strong landscape/article/document evidence without rejecting it only because it is not portrait-native.

In Factanza-like styles, the speaker may remain visible while evidence appears above/alongside. In Olimpia-like styles, short full-screen native clips can appear more often, followed by quick return to speaker.

Actual Resolve layout rendering remains a later Apply concern; the Edit Plan should persist the recommended presentation mode now.

## 13. Coverage density policy

The system should not use a fixed "one B-roll every N sentences" rule.

Coverage density is driven by:

- semantic importance;
- evidence opportunity;
- novelty/visual payoff;
- active StyleDNA;
- nearby recent coverage;
- speaker-return pacing;
- hook/body phase;
- candidate quality actually available.

A chunk may produce:

- zero slots when speaker is stronger;
- one slot for one clear receipt/evidence moment;
- multiple short slots when several named/evidentiary beats occur inside a longer semantic chunk.

The system must distinguish:

- `NO_BROLL_NOT_NEEDED`;
- `NO_BROLL_NO_STRONG_EVIDENCE`;
- `NO_BROLL_QUALITY_FLOOR`;
- `NO_BROLL_RIGHTS_OR_PROVENANCE`.

This is important for review/debugging.

## 14. Search expansion when candidate quality is weak

A weak A/B pair must trigger additional search rather than immediate acceptance.

Suggested search ladder per slot:

1. exact entity/claim/event + source-native terms;
2. official/primary source search;
3. article/news/report/post search;
4. social/native platform search;
5. archive/repertory search;
6. related editorial context;
7. generic stock fallback.

Stop early when two sufficiently distinct candidates clear all hard gates.

Search cost is bounded by a configurable per-slot budget and wall-clock budget.

## 15. Candidate diversity contract

Proposal B is not simply score #2.

B must differ meaningfully from A in at least one editorial dimension:

- different source;
- different visual form;
- different presentation mode;
- different evidence angle;
- different moment/window;
- different composition strategy.

Example:

- A = original social clip of the person;
- B = article headline/receipt about the same claim.

This is more useful to an editor than two almost identical node-graph Shorts.

## 16. Review UI changes

The review artifact/panel should expose editorial reasoning, not only raw similarity scores.

For each slot show:

- semantic chunk and exact local narration;
- EvidenceIntent;
- VisualRoute;
- selected source strategy;
- proposed presentation mode;
- A/B previews;
- source URL/title/account/channel;
- source timestamp;
- semantic relevance;
- evidence specificity;
- editorial quality;
- source authority/authenticity;
- style fit;
- composition usability;
- technical quality;
- final score;
- provenance/rights;
- why A and B are meaningfully different;
- rejection reasons for top failed candidates when useful;
- explicit NO_BROLL reason where applicable.

Summary metrics should additionally include:

- candidate pass rate after quality gates;
- percentage exact-evidence vs generic fallback;
- generic-stock usage;
- average editorial-quality score;
- source-class distribution;
- repeated-source/motif count;
- speaker coverage percentage;
- full-frame vs composite presentation ratio;
- per-style fingerprint distance where measurable.

## 17. Performance constraints

Quality improvements must preserve RAMBLA's bounded-acquisition philosophy.

Use cheap stages first:

1. title/metadata/source identity;
2. lightweight storyboard/thumbnail/page screenshot;
3. coarse Qwen ranking;
4. only then bounded source acquisition;
5. final-frame semantic + editorial quality pass on actual candidate segment.

Batch candidate scoring by model/source where practical.

Do not download full long videos solely for editorial scoring.

Do not run an expensive multimodal judge on clearly irrelevant candidates.

## 18. Rights and provenance

Higher editorial quality does not relax rights policy.

Every candidate still preserves:

- canonical source URL;
- source account/creator/publisher;
- provider/platform;
- exact timestamp/range or page capture time;
- acquisition method;
- discovery query;
- rights/provenance state;
- whether the asset is primary, derivative, repost/unknown.

Private tests may use review-required sources for evaluation, but publication remains rights-gated.

## 19. Failure and safety behavior

- semantically relevant but low-quality -> reject and search further;
- strong exact evidence but poor portrait crop -> prefer composite/picture-in-picture layout before rejecting;
- polished but generic stock vs rough exact evidence -> exact evidence usually wins if technically usable;
- two near-identical top candidates -> diversify B;
- only weak candidates after search budget -> `NO_BROLL_QUALITY_FLOOR`;
- source extraction fails -> preserve discovery metadata and continue source ladder;
- Qwen disagreement/low confidence -> mark review-required and keep alternatives;
- no Resolve mutation during analysis/review;
- no autonomous main merge.

## 20. Validation benchmark

Create a repeatable benchmark using the user-provided reference style direction plus the existing long talking-head smoke transcript.

For at least 8 semantic chunks:

1. run the current semantic-first baseline;
2. run Editorial Intelligence + StyleDNA ranking on the same slots/search budget;
3. compare candidate sets blindly in review;
4. record user/editor acceptance A/B/NO_BROLL;
5. measure whether the new system improves acceptance without reducing factual relevance.

Primary metrics:

- editor acceptance rate of proposal A;
- editor acceptance rate of either A or B;
- exact-evidence rate;
- generic/low-value rejection rate;
- number of additional searches required;
- final Qwen semantic floor violations (must remain zero);
- average acquisition bytes per accepted slot;
- runtime per slot.

The benchmark is a quality gate, not an optional demo.

## 21. Implementation decomposition

This design is architectural and should be implemented in slices after written-spec approval.

Recommended sequence:

### Slice E1 — scoring and quality floor

- add evidence/editorial/source/style/composition score fields;
- implement deterministic editorial quality checks;
- add candidate eligibility gates;
- require explicit NO_BROLL quality reasons;
- diversify A/B.

### Slice E2 — EvidenceIntent + source strategy

- add EvidenceIntentPlanner;
- source-class search ladder;
- expand web/article/receipt strategies behind existing provider interfaces;
- generic stock becomes true fallback.

### Slice E3 — StyleDNA reference fingerprints

- extend fingerprint analyzer for the two supplied exemplar families;
- persist independent reference profiles;
- add active style mix;
- thread StyleDNA into planning/ranking.

### Slice E4 — composition-aware coverage

- add presentation mode recommendations;
- score full-frame vs composite usability;
- show recommended layout in review;
- do not implement Resolve rendering yet unless separately approved.

### Slice E5 — benchmark and calibration

- baseline vs new-ranking benchmark;
- tune weights/thresholds from real editor acceptance;
- persist calibration evidence, not opaque guesses.

Resolve Apply remains frozen through E1–E5 unless separately authorized.

## 22. Acceptance criteria

Editorial Intelligence + StyleDNA V1 is demonstrated when RAMBLA can:

- analyze the supplied external reference reels as separate exemplar fingerprints;
- preserve a Factanza-like and Olimpia-like style family rather than averaging them away;
- classify each planned visual into an explicit EvidenceIntent and source strategy;
- search exact evidence/source-native material before generic stock;
- score candidates separately for semantic relevance, evidence specificity, editorial quality, source authority/authenticity, style fit, composition usability and technical quality;
- reject a semantically relevant but editorially weak candidate;
- return explicit `NO_BROLL_QUALITY_FLOOR` when no good candidate exists;
- present at least two meaningfully different A/B proposals for successful slots;
- use final-segment Qwen verification on actual selected clips;
- recommend composite/speaker+evidence presentation when that preserves a strong landscape/document source better than a destructive 9:16 crop;
- expose all score components and reasons in review;
- demonstrate improved human acceptance versus the existing semantic-first baseline on a real multi-chunk reel;
- preserve bounded acquisition, provenance, client isolation and zero Resolve mutation during analysis.

## 23. Explicit non-goals for V1

- no end-to-end autonomous publishing;
- no assumption that YouTube Shorts alone is an adequate source universe;
- no blind copying of the visual branding of Factanza or Olimpia;
- no model fine-tuning required;
- no cross-client global taste leakage;
- no automatic permanent learning from one click;
- no requirement that all media be portrait-native;
- no forced B-roll when candidate quality is weak;
- no Resolve timeline mutation from the Director/scoring pipeline.

## 24. Design decision

The recommended architecture is the hybrid evidence-first system described above:

**semantic correctness is the admission ticket; evidence specificity + editorial quality decide whether the clip deserves to be shown; StyleDNA decides how it should feel and be presented.**

This is the product direction intended to move RAMBLA from "technically finds relevant clips" to "makes editorial choices an experienced social-video editor would actually keep."