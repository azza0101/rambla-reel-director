# TikTok empty shelf diagnosis

The existing beat_006 artifact records six real TikTok attempts over three rounds, each with 12 raw hits; candidates and discovery_sources are both empty. Rejections include low visual relevance, text overlays, and unsupported hotel demotion. These are raw search results, not 12 displayable cards.

Fixed guesthouse/hotel alias consistency and accommodation context recognition: the actual imported shot no longer becomes its own negative target. Empty shelves now distinguish raw hits from discarded candidates and show rejection reasons. Quality thresholds remain unchanged; no rejected result is promoted automatically.

Validation: 578 tests passed; backend compilation passed; actual imported beat_006 specification checked without modifying the plan or running ASR. Fresh provider search and visual ranking after restart remain to be verified. Existing rejected artifacts have not been rewritten.
