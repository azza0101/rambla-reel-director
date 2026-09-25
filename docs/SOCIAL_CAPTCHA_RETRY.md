# CAPTCHA focus and manual retry — 2026-09-23

Local patch; no remote publication.
- Cause confirmed by regression: OPEN uses run_in_profile's per-provider search lock, so focusing can wait behind a running search. Existing tab focus also does not explicitly restore a minimized window. Errors were only shown in the distant global login status.
- Live session focus now bypasses the navigation/search lock, targets the existing managed page, restores a minimized Chromium window and brings the page forward. No navigation, new tab, reload or CAPTCHA bypass.
- CAPTCHA alert calls the existing login/focus route directly; reports success/failure inline instead of swallowing errors into global UI.
- Rilancia ricerca is disabled while a run is active; afterwards it explicitly retries only the displayed beat/provider in append mode, preserving variation/query/Qwen options when available. No VERIFY or automatic retry. Global-run alerts retry the currently displayed beat only.
- Validation: 599 tests passed; backend compile and generated JS syntax passed. Regression tests cover search-lock focus, minimized window commands, retry scope/options/busy guard, inline error feedback. Real Windows foreground behavior/CAPTCHA interaction not exercised by agent.
- Restart RAMBLA to load patch; user resolves CAPTCHA manually.
