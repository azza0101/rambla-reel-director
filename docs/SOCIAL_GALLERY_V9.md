# Social gallery V9 — local acceptance

Approved changes implemented in the existing curation workflow:

- Provider-scoped progress bars use live run events, with indeterminate progress
  while completion fraction is unknown. Failed/cancelled runs clear the busy state.
- Click a social thumbnail to prepare/open its timeline GIF. Backdrop click or Esc
  closes it; late responses cannot reopen a dismissed modal.
- Six compact cards per page; right arrow first pages stored alternatives, then
  requests another provider-scoped append run with a changed query round.
- Three additional variation rounds, up to 24 retained/displayed social alternatives.
  Fewer are allowed when quality or dedupe eliminates results. Existing cards keep
  stable ordering within the viewing session; failed runs do not consume rounds.
- Expand Keyword per shot to edit short search queries for individual shots.
  Overrides and variation round are validated by the API and passed to the worker.
  The imported editorial plan is untouched. No invented geography; POV automatic
  variation is limited to compatible viewpoints. Query options participate in cache keys.
- Source links are styled as buttons; metadata/debug fields are collapsed; card
  spacing and three-column workspace proportions leave room for six portrait cards.

Validation: 576 tests passed; Python compile and rendered JavaScript syntax pass.
Browser inspection on current real project fea7fff128ef/beat_002 verified six cards,
pagination from 1–6 to 7–11, three editable shot keyword fields, a real GIF in the
modal, and outside-click dismissal. Temporary server 8899 and inspection tab closed.
No provider search, ASR, media cleanup, plan import or installation was performed.
Live relevance of newly varied provider searches is not claimed as tested.

Changes remain local and require backend restart via RESTART_RAMBLA_V5.ps1.
