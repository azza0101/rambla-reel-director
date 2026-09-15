# RAMBLA Debug Runner

Debug UI locale temporanea per osservare il motore prima del plugin Resolve.

## Avvio

```powershell
.\tools\start_rambla_debug_runner.ps1
```

Apre `http://127.0.0.1:8765/debug`.

Default video:

```text
Z:\APP REEL TEST\VIDEO BASE\KURA_Finto etico_draft 1.mp4
```

Default output:

```text
Z:\APP REEL TEST\qwen-embedding-smoke\kura-finto-etico-smoke\run
```

## Collegamento alla pipeline reale

Il debugger non duplica la pipeline: lancia l'esatto comando dello smoke corrente tramite un profilo locale non versionato:

```text
Z:\APP REEL TEST\qwen-embedding-smoke\debug-runner-command.json
```

Formato:

```json
{
  "command": [
    "python",
    "-m",
    "<modulo-smoke-esistente>",
    "--video",
    "{video}",
    "--output",
    "{output}"
  ]
}
```

Codex deve sostituire solo il comando con **quello già usato per lo smoke Editorial Intelligence**, senza creare una nuova pipeline. `{video}` e `{output}` vengono sostituiti come argomenti, senza shell.

## Progress live

La UI combina:

- stdout/stderr live del worker;
- artifact reali (`transcript-raw.json`, `semantic-beats.json`, `online-candidates.json`, `coverage-metrics.json`, `edit-plan.json`, `review.html`);
- eventi opzionali del worker nel formato:

```text
RAMBLA_EVENT {"stage":"qwen_final","progress":60,"message":"3/5 frame verificati","data":{"candidate":"A"}}
```

Stage supportati: `prepare`, `asr`, `semantic_chunking`, `coverage`, `evidence_intent`, `source_strategy`, `online_search`, `qwen_coarse`, `bounded_acquisition`, `qwen_final`, `edit_plan`, `review`.

Non vengono inventate percentuali: senza eventi granulari, una fase passa al 100% solo quando esiste un artifact concreto.

La pagina mostra barra totale, barra per fase, log live, eventi/dati, A/B certificate, NO_BROLL, byte scaricati, tempo totale e i path finali di `review.html` e `edit-plan.json`.

`resolve_calls=0`: il debugger resta separato dal futuro plugin Resolve.
