# Riferimenti e decisioni

- AutoCut source snapshot: https://github.com/azza0101/rambla-reel-director/tree/a1c73bee994a3c5825df2686238ca8b03b12b3c3/autocut-standalone
- `autocut-standalone/tools/autocut_integration/main.js`: native `WorkflowIntegration.node`, Electron, local worker, lifecycle e update.
- `autocut-standalone/tools/autocut_integration/source_adapter.js`: riferimento di recupero progetto/timeline/marks; **non** usare la restrizione single video.
- `autocut-standalone/backend/app/autocut_update.py`: allowlist, SHA256, rollback e GitHub releases.
- `autocut-standalone/tools/install_autocut_integration.py`: installazione cross-platform e SDK locale.
- `autocut-standalone/docs/AUTOCUT_INTEGRATION.md`: documentazione di installazione e limiti reali.

Non copiare token GitHub, credenziali, .env.local, log, cache e file utente nel plugin/distribuzione. La V3.1 sorgente è un artefatto della conversazione, non ancora parte di questo snapshot GitHub.
