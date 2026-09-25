# Live TikTok diagnostics

Observed live run 079fd2fa96ef, project fea7fff128ef, beat_007: RUNNING; slot 2 completed with 24 raw hits, while slot 1 had not completed. Final online-candidates artifact did not yet contain either slot. The final gather delayed all published evidence. The old worker emits no thumbnail/ranking boundary events, so its current wait cannot be attributed conclusively.

Changes: provider attempts emitted before thumbnail ranking, live run evidence overlaid into curation diagnostics without publishing unfinished candidates, UI refresh every five seconds during beat research, explicit pending-provider text. Social thumbnails use a shared four-request semaphore and twelve-second timeout each; ranking phase is announced.

Validation: 580 tests passed; compileall passed. No ASR, plan changes, new provider calls, or cancellation of the user's running search. Restart is needed to use changed worker code. Live completion with the new worker remains unverified.
