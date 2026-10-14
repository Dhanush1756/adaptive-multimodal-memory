# Adaptive Evidence-Grounded Memory for Long-Term NLP Agents

An adaptive multimodal memory that links **text** and **image** evidence to evolving entity
states, keeps history instead of overwriting it, and answers current and historical questions
with the evidence behind each answer.

> **Status: Phase 8 release stabilization complete.** See
> [`docs/phase8_release_readiness.md`](docs/phase8_release_readiness.md) for the final UI fixes,
> integration-test results, release checks, and remaining manual/model validation limits.

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
- Answers come from deterministic templates over retrieved states. An optional LLM only
  rephrases a prompt that contains the retrieved evidence.

## Install and run

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
agent.store.close()
```

Relative configured storage paths resolve from the repository root. Missing database parents
are created automatically. Use `MemoryAgent(db_path=":memory:", light=True)` for an isolated,
ephemeral agent; tests and benchmark factories explicitly use temporary or in-memory storage.

The Streamlit app keeps one agent per browser session. With the default configuration its
database is `data/processed/memory_sessions/<random-session-id>/memory.db`; images are under
`<paths.image_dir>/sessions/<random-session-id>/`. Reruns and Light-mode changes preserve that
session's memory. Reset affects only its database. A fresh browser session gets a new namespace;
automatic restoration after a browser/server restart is not implemented. Existing files remain
available for explicit reopening through `MemoryAgent(db_path=...)`. Reset does not delete images.

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
python -m src.training.train_color_head --real-dir data/raw/colors
```

Full step-by-step instructions, evaluation rules and what each trained component does are in
[`docs/training.md`](docs/training.md).

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

## Limitations

- Only one attribute (`color`) is tracked; other attributes need extractor and CV support.
- One claim is extracted per input; several entities in one message are not handled.
- Explicit ordinal identities such as "first car" and "second car" are distinguished. General
  identity resolution and visual re-identification are not implemented.
- The synthetic images are an easy domain. Real-photo accuracy must be measured separately.
- Weights and thresholds in `config.yaml` are initial values, not tuned ones.

## License

MIT License. See [`LICENSE`](LICENSE). Copyright (c) 2026 Dhanush S, E Sasi Vaishnav, Dhruthi Kulkarni.
