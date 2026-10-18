# Adaptive Evidence-Grounded Memory for Long-Term NLP Agents

An adaptive multimodal memory that links **text** and **image** evidence to evolving entity
states, keeps history instead of overwriting it, and answers current and historical questions
with the evidence behind each answer.

> **Status: integrated NLP + CV research prototype.** The implementation follows the submitted
> report's adaptive evidence-grounded architecture. See
> [`docs/report_implementation_traceability.md`](docs/report_implementation_traceability.md) for
> claim-by-claim alignment and [`docs/integrated_nlp_cv_architecture.md`](docs/integrated_nlp_cv_architecture.md)
> for the final data flow.

## How it works

```
text  -> NLP (entities, colour claim, time expressions) ─┐
                                                          ├─ evidence fusion (agreement, confidence)
image -> CV  (detect, crop, HSV/CLIP colour, embedding) ──┘            │
                                                                       v
                    rule-based memory engine: ADD / UPDATE / MERGE / HISTORICAL /
                    CONTRADICTORY / IGNORE  ->  SQLite states chained by time
                                                                       │
 question -> intent + entity -> temporal retrieval -> grounded answer + evidence + confidence
```

- The memory engine is independent of any LLM (`src/memory/update.py`).
- Old states are never deleted; they become `HISTORICAL` and stay linked.
- Text and image that confidently disagree are stored as `CONTRADICTORY` and not applied.
- Unresolved disagreements can be queried directly and require one explicit human verification.
- Evidence keeps event time separate from ingestion time and records the active NLP/CV method.
- Answers come from deterministic templates over retrieved states. An optional LLM only
  rephrases a prompt that contains the retrieved evidence.

## Install and run

The persistent-account research interface is available separately:

```bash
python -m streamlit run app/account_app.py --server.address 127.0.0.1
```

It keeps account authentication, transcripts and adaptive memory distinct.
See [Phases 13-14 implementation and training blockers](docs/phase13_14_implementation.md).
Real-photo model training remains blocked on a reviewed labeled dataset; the
Light-mode results do not imply pretrained CV or real-photo performance.

```bash
pip install -r requirements.txt
pytest -q                                   # unit + end-to-end tests (no model downloads)
python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1  # Light mode defaults on
```

Quick use from Python:

```python
from src.agent.reasoning import MemoryAgent
agent = MemoryAgent(light=True)             # uses the configured persistent database
agent.remember("I bought a red car.", "red_car.jpg", "2026-10-01")
agent.remember("I repainted my car blue.", "blue_car.jpg", "2026-10-10")
print(agent.ask("What color is my car now?").text)
print(agent.ask("What color was my car originally?").text)
print(agent.ask("Do the text and image disagree about my car?").text)
agent.store.close()
```

Relative configured storage paths resolve from the repository root. Missing database parents
are created automatically. Use `MemoryAgent(db_path=":memory:", light=True)` for an isolated,
ephemeral agent; tests and benchmark factories explicitly use temporary or in-memory storage.

The Streamlit app keeps one agent per browser session. With the default configuration its
database is `data/processed/memory_sessions/<random-session-id>/memory.db`; images are under
`<paths.image_dir>/sessions/<random-session-id>/`. Reruns and Light-mode changes preserve that
session's memory. Reset affects only its database. The sidebar displays a random 128-bit recovery
code; saving and re-entering that exact code reopens the existing isolated database after a
browser or server restart. Codes are never listed, and invalid or missing codes do not create or
open storage. The code is a local bearer secret, so hosted multi-user deployment still requires
authentication and access controls. Reset does not delete images.

Late compatible evidence uses its event time: a blue observation dated October 10 can extend
a blue state previously known from October 20. An October 15 query then returns blue because
of that earlier observation. Evidence merely confirming an October 20 event does not backdate
it. Every text/image item retains its own source date and session association.

## Evaluate and train

```bash
python -m src.data.make_dataset --n 300 --seed 0 --out data/synthetic --save-images
python -m src.evaluation.ablations --split test --out reports/results
python -m src.evaluation.component_eval --split test
python -m src.training.train_intent_classifier
python -m src.training.real_color_experiment --manifest data/raw/colors/manifest.csv --features hist --out models/colour-study-v1
```

Full step-by-step instructions, evaluation rules and what each trained component does are in
[`docs/training.md`](docs/training.md).

The published Phase 6 Track A metrics are frozen. Put any reproduction in a new directory as
described in [`docs/multimodal_evaluation_protocol.md`](docs/multimodal_evaluation_protocol.md).
`requirements.txt` is the deterministic Light-mode profile tested on Windows 11 with
CPython 3.14.6, Streamlit 1.58.0, Starlette 1.3.1, Uvicorn 0.40.0, pytest 9.0.3 and
SQLite 3.53.2. A clean virtual-environment installation passed 193 tests and a live
headless-Chrome demonstration; see [`docs/phase12_demo_reproducibility.md`](docs/phase12_demo_reproducibility.md).
Python 3.10.8 with Streamlit 1.31.1 is not supported: core tests run, but that Streamlit AppTest
release cannot automate file upload and mishandles formatted selectbox values. Pretrained NLP/CV
packages and model assets are intentionally outside this Light-mode requirements file.

## Repository layout

| Path | Purpose |
|---|---|
| `src/nlp/` | preprocessing, entity lexicon, claim extraction, time expressions, text embeddings |
| `src/cv/` | image loading, YOLO detection, HSV/CLIP colour, image embeddings |
| `src/multimodal/` | cross-modal agreement, fusion into a candidate, visual pipeline |
| `src/memory/` | schema, SQLite store, update engine, state chains, conflict rules |
| `src/retrieval/` | temporal, hybrid, text and image retrieval |
| `src/agent/` | query parser, intent model, grounded answers, `MemoryAgent` |
| `src/data/` | synthetic benchmark generator |
| `src/evaluation/` | metrics, baselines, benchmark runner, ablations, component evaluation |
| `src/training/` | intent classifier and colour head training |
| `app/streamlit_app.py` | demo UI |
| `tests/` | memory, NLP, CV, retrieval and end-to-end tests |

Research documentation:

- [Local Ollama setup and manual demonstration](docs/local_models_setup.md)
- [Local-first implementation and actual evaluation status](docs/local_models_implementation.md)
- [Automatic account memory, architecture and demonstration](docs/automatic_memory_implementation.md)
- [Open Images car-colour training, results and opt-in launch](docs/openimages_colour_training.md)
- [`docs/report_implementation_traceability.md`](docs/report_implementation_traceability.md)
- [`docs/integrated_nlp_cv_architecture.md`](docs/integrated_nlp_cv_architecture.md)
- [`docs/multimodal_evaluation_protocol.md`](docs/multimodal_evaluation_protocol.md)
- [`docs/limitations_and_research_gaps.md`](docs/limitations_and_research_gaps.md)
- [`docs/integrated_report_outline.md`](docs/integrated_report_outline.md)
- [`docs/ieee_research_paper.tex`](docs/ieee_research_paper.tex)

## Limitations

- Only one attribute (`color`) is tracked; other attributes need extractor and CV support.
- One claim is extracted per input; several entities in one message are not handled.
- Explicit ordinal identities such as "first car" and "second car" are distinguished. General
  identity resolution and visual re-identification are not implemented.
- The synthetic images are an easy domain. Real-photo accuracy must be measured separately.
- Weights and thresholds in `config.yaml` are initial values, not tuned ones.

## License

MIT License. See [`LICENSE`](LICENSE). Copyright (c) 2026 Dhanush S, E Sasi Vaishnav, Dhruthi Kulkarni.
- [Groq provider assessment, costs and separate embeddings](docs/groq_assessment.md)
- [Groq secure PowerShell setup and manual demonstration](docs/groq_setup.md)
- [Groq implementation and actual test status](docs/groq_implementation.md)
- [Chat interface, attachments, memory controls and UI validation](docs/chat_layout.md)
- [Remember a Groq key securely and share the repository](docs/remembered_groq_key.md)
