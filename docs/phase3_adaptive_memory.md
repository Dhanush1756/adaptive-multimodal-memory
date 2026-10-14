# Phase 3 - Adaptive memory lifecycle, conflict resolution, and evaluation

Reviewed and implemented on October 13, 2026. This phase retains the SQLite
state store, rule-based memory engine, NLP extraction, temporal retrieval, and
optional CV pipeline. No dependency was installed, pretrained model downloaded,
or existing user database opened for testing.

## Audit findings

### Confirmed behavior

Text extraction creates a structured entity, `color` attribute, value, event,
and resolved event time when a date expression is available. The supplied
timestamp is the observation/reference time otherwise. The state tracker orders
states by event time, rebuilds `previous_memory_id` links transactionally, and
keeps earlier states as `HISTORICAL`. A later state is `CURRENT`.

Visual evidence already retains source timestamp, session, detector provenance,
and Phase 2 association status. `verified` evidence comes from one matching
detector result; `contextual` evidence is explicitly unverified; `ambiguous`
and `unmatched` evidence does not support or contradict a state. Text/image
conflicts are stored as `CONTRADICTORY` records without changing the state
chain. Failed visual analysis leaves a usable text claim intact.

### Confirmed gaps fixed here

1. Replaying the exact same evidence source appended duplicate JSON evidence and
   increased state confidence on every retry. `MemoryStore.add_evidence` now
   appends only novel text or visual evidence, and `MemoryEngine` leaves
   confidence unchanged for an exact retry.
2. A missing timestamp was silently replaced by local ingestion time. This is
   still the practical fallback for a live UI observation, but the ingest result
   now carries an explicit uncertainty note.
3. Evaluation reported evidence recall only. It now also reports citation
   precision for labelled evidence questions and an operational
   unsupported-answer rate: incorrect returned values divided by answered
   labelled questions. This is not an open-ended LLM hallucination claim.

### Remaining known limitations

One entity instance is tracked per object category (`car_001`, `laptop_001`),
so two different cars cannot yet be safely distinguished. The project must not
merge them only because they share a category; this remains an explicit
prototype limitation rather than a solved identity problem. Equal-time updates
use insertion order. A contextual image can provide a colour observation but is
not detector-verified. The confidence formula and thresholds are engineering
rules, not calibrated probabilities or proof that a state is objectively true.

## Lifecycle rules

| Decision | Rule | Result |
|---|---|---|
| `ADD` | No state exists for the extracted entity and attribute. | Create the first current state. |
| `UPDATE` / supersede | A supported later value differs from the state in effect. | Create a new current state, mark the preceding state historical, and preserve its link in `superseded_memory_id`. |
| `MERGE` | A compatible value matches the state in effect or adjacent later state. | Attach only novel evidence; earlier compatible event time may extend that state's start. |
| `HISTORICAL` | A supported new value is older than the newest state. | Insert it in temporal order without overwriting current state. |
| `CONTRADICTORY` | Confident associated text and image disagree, or an image-only claim conflicts with state. | Preserve both source observations as a separate non-chain record. |
| `IGNORE` | No extractable supported claim, low confidence, or out-of-domain entity/attribute. | Do not create state. |

`UPDATE` is the project’s public decision name for a superseding transition.
The prior state is never deleted; its historical status and `previous_memory_id`
chain make the supersession inspectable. Exact retry identity is the full stored
text/visual evidence payload, including source/session/time. A separate source
that makes the same claim is retained as corroboration.

Temporal questions select the state effective at the requested time. Late
evidence is evaluated at its supplied event time, never at arrival order. If
there is no state at or before the requested time, the answerer reports that
insufficient information is stored. Contradictory records are surfaced for
current/evidence answers but are not applied as established state.

## Evaluation

The existing component evaluator measures extraction, synthetic visual colour,
and intent parsing in isolation. The ablation runner replays an integrated
agent, but its data generator uses a small fixed template family and generated
images. It is useful for deterministic lifecycle regression, not for a claim of
generalization. Scenario-level splitting avoids splitting sessions from one
scenario, but templates and colour vocabulary repeat across split boundaries.
No real-image, pretrained YOLO, or CLIP evaluation was run.

Metric denominators:

* Current/historical accuracy: labelled questions in that query group.
* Evidence recall: labelled questions with one or more gold source sessions.
* Evidence precision: the same evidence-question denominator; matching cited
  sessions divided by cited sessions, with zero when none were cited.
* Unsupported-answer rate: answered labelled questions; an unsupported answer
  is a returned value different from the labelled answer.
* Lifecycle decision accuracy and conflict F1: labelled ingest sessions.

Executed on October 13, 2026 with Anaconda Python 3.14.6, the existing
light-mode hashing/HSV components, 30 newly generated synthetic scenarios
(seed `314159`), 171 labelled ingest decisions, and 414 labelled questions:

| Metric | Result |
|---|---:|
| Lifecycle decision accuracy | 1.000 (171) |
| Conflict detection F1 | 1.000 (26 conflicts) |
| Current-state accuracy | 1.000 (60) |
| Historical-state accuracy | 0.971 (204; 95% scenario-bootstrap CI 0.951-0.990) |
| Evidence recall | 0.971 (204) |
| Evidence precision | 0.759 (204) |
| Unsupported-answer rate | 0.010 (412 answered) |

The evidence precision result shows the system often returns more supporting
sources than the generator marks as minimally required. The non-zero
unsupported-answer rate and non-perfect historical accuracy are retained as
observed results. These figures are not a benchmark against real photos,
unseen language, pretrained models, or humans.

## Files changed

| File | Rationale |
|---|---|
| `src/memory/store.py` | Idempotent evidence appends. |
| `src/memory/update.py` | Do not inflate confidence for an exact evidence retry. |
| `src/agent/reasoning.py` | Mark ingestion-time fallback when source time is missing. |
| `src/evaluation/metrics.py` | Add evidence precision and scoped unsupported-answer rate. |
| `tests/test_memory.py` | Retry/idempotence lifecycle regression. |
| `tests/test_multimodal_evidence.py` | Missing-timestamp uncertainty regression. |
| `tests/test_evaluation_metrics.py` | Deterministic metric denominator regression. |
| This document | Audit, lifecycle contract, test/evaluation record. |

## Verification and manual checks

Focused Phase 3 tests before the final full suite: **18 passed**. Final complete
suite: **151 passed in 11.40 seconds**, with no failures or skips. Tests used
temporary SQLite/image storage or in-memory stores; no user database was reset.

Launch the demo from the project root:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Keep Light mode enabled. In one browser session, store red on October 1, blue
on October 10, and black on October 20. Ask for current, original, previous,
and the colour on October 15; expected answers are black, red, blue, and blue.
Store the same blue statement again with the same source session/date only when
testing a retry: the timeline must not gain a state or duplicate evidence.
For a visual conflict, use a detector-verified red image with the text `My car
is blue.`; the UI should report a conflict and keep the preceding established
state. A missing/invalid image should show an uncertainty note while retaining
valid text memory.
