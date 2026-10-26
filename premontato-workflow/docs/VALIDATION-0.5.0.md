# Premontato 0.5.0 — semantic alignment

Local quantized multilingual MiniLM-L12-v2, ONNX CPU and tokenizer bundled offline. Models obtained only during build from exact revision and SHA256 lock. No cloud inference or runtime download.

Scene-level chronological alignment with omission option; lexical evidence refines boundaries and rejects weak unrelated matches. Candidate windows keep original word times and avoid silence/repeated sentence boundaries. Meaning and exact word coverage are distinct metrics. Editorial alternation is subordinate to matching quality.

Actual test: 12 dialogue candidates from 12 script beats versus 10/12 in the lexical version. This is candidate retrieval, not proof every cut is complete or correct. Short utterances and source ASR errors still need review; no human audio review claimed. Initial embedding benchmark: 384 windows plus 12 queries in 4.81s warm CPU inference, excluding download/video decode. Integrated pipeline approx 9–15s on supplied transcript, machine dependent.

26 Python tests, 39 Node tests. UI host integration not interactively tested in this version. No identity detection or multicam.
