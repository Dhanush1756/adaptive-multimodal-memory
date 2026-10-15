# Limitations and remaining research gaps

## Supported claims

- The prototype implements one shared NLP/CV temporal memory lifecycle.
- Accepted changes preserve previous and initial states.
- Event time controls state validity; ingestion time is retained separately.
- Text and visual evidence are traceable to IDs, sessions, timestamps and extraction methods.
- Unverified images cannot silently rewrite memory.
- Unresolved disagreements are retained, queryable and require an explicit human choice.
- Controlled Light-mode Track A results and current regression results are reproducible in the recorded environment.

## Partially supported

- **Language coverage:** rules cover a useful but finite set of entities, colors, event phrases and query paraphrases.
- **Identity:** explicit ordinal identity is supported; general coreference and visual re-identification are not.
- **Vision:** HSV and histogram behavior is evaluated on controlled images. Optional YOLO/CLIP adapters exist without release-level real-photo evidence.
- **Long-term interaction:** persistence and long sequences are tested, but natural conversations with hundreds of turns are not.
- **Confidence:** scores support gates and ranking but are not probability-calibrated.
- **Persistence:** SQLite reopens correctly. A full Streamlit server restart generates a new browser namespace unless an existing database is opened through the Python API.

## Unsupported claims

- LLaVA inference or general visual question answering.
- Superiority on LoCoMo, MTPChat, or another public benchmark.
- Real-world detector, CLIP or color accuracy.
- Production multi-user authentication or distributed concurrency.
- Open-domain attributes, multiple claims per input, or implicit same-object recognition across photographs.
- Human-rated answer quality, calibrated uncertainty, or independent replication.

## Research priorities

1. Freeze a licensed, identity-annotated real-photo Track B dataset and run approved pretrained CV adapters.
2. Expand NLP paraphrases and fix the known “immediately preceded” and sentence-initial “Initially” failures in a new evaluation version.
3. Evaluate instance association and clarification when multiple same-class objects appear.
4. Calibrate visual and fused confidence on development data.
5. Add external/public dialogue evaluation without changing the Track A protocol.
6. Pin a tested dependency profile and validate installation in a clean environment.

Frozen annotations and results must remain unchanged while these studies are developed.
