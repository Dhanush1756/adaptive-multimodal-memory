# Phase 5 - Generalization and evidence reliability

Evaluated on October 13, 2026. This phase fixes the concrete Phase 4 failure
classes. It keeps SQLite, the existing rule-based lifecycle, the Streamlit UI,
and the current NLP/CV component interfaces. No package or model was installed
or downloaded, and every evaluation agent used in-memory SQLite.

## Confirmed root causes

1. Detector-free light mode produced a full-image colour observation marked
   `contextual`. Fusion and conflict handling nevertheless treated
   `contextual` and `verified` alike. An unrelated red laptop uploaded with a
   blue-car statement could therefore create a car conflict.
2. The query parser did not cover general original-state wording such as
   "start with" or "earliest recorded". Its past-tense fallback classified the
   question as `PREVIOUS`.
3. Past-state extraction rejected "On this date the car was blue" because the
   phrase had no independently parsed calendar date. It did not recognize the
   phrase as a reference to the supplied observation timestamp.
4. Entity resolution keyed every object only by its category. Both "first car"
   and "second car" therefore resolved to `car_001`.
5. Evidence questions without a recognized temporal cue defaulted to `ALL`, so
   an unfamiliar current-evidence question returned a list even when it asked
   for the established scalar state.

## Implemented behavior

Visual evidence now carries `supports_state`. Only an association marked
`verified` by an actual detector match can fill a missing text value, affect
fusion confidence, establish an image-only state, or create a cross-modal
conflict. Detector-free full-image analysis remains stored as contextual
provenance with its source timestamp, session, image ID, and association reason,
but it is excluded from supporting citations and state decisions. Unmatched or
ambiguous detector results remain excluded. Text ingestion continues if image
analysis fails or cannot verify an entity.

Original-state rules now cover `start with`, `started out with`, `earliest
recorded`, `first appearance`, and `initial condition`. `PREVIOUS` remains the
immediately preceding state and `CURRENT` remains the newest valid state.
Evidence requests default to the current state unless they explicitly select an
original, previous, or named value. Deictic dated phrases (`on this date`, `on
that date`, `that day`, `at that time`) use the caller-supplied observation time;
generic ungrounded statements such as "the car was red" remain rejected.

The schema now stores `entity_ref` separately from the category. Explicit
ordinal references such as `first car` and `second car` receive independent IDs
and histories. Pronoun context carries the most recent explicit identity.
Queries with a supported reference resolve that instance; a category-only query
abstains when multiple instances exist. The implementation deliberately does
not infer identity from colour, image upload order, or a contextual image.

Answers retain the existing fields and add a validated `status` (`answered`,
`uncertain`, or `abstained`), supporting state IDs, and supporting evidence IDs.
Evidence records include source timestamps and whether they support the state.
An optional LLM rephrase is accepted only if it retains every selected value
and introduces no other known colour; otherwise the grounded deterministic
template is used. This is a conservative structural/value check, not a proof
that arbitrary natural-language output is factually correct.

Existing databases migrate in place by adding an empty `entity_ref` column.
Existing JSON visual evidence remains readable; legacy items are supporting
only when their stored association status was `verified`.

## Evaluation sets and leakage controls

`data/annotations/phase5_dev.jsonl` contains 3 scenarios. It covers alternate
initial/previous wording, two explicit car identities, and one unrelated-image
case. `data/annotations/phase5_test.jsonl` was then constructed separately with
6 scenarios, 13 observations, and 14 questions. It covers three state changes,
late event-time evidence, supported and unresolved entity identity, two
unrelated images, current evidence shape, initial state, and pre-history
abstention.

The construction seed is **20261013** for naming and deterministic rendered
image seeds; scenario content and labels were manually specified. Splits are at
scenario level. A regression rejects duplicate scenario IDs, exact normalized
observation-text overlap between Phase 5 development and test, and overlap
between Phase 5 test and Phase 4 test. The Phase 4 annotations were not edited.
The Phase 5 test set was evaluated only after the implementation and development
regressions passed. Self-created rendered images exercise decoding and fallback
analysis; they are not real-photo validation.

## Measured results

The complete Phase 5 light-mode matrix is in
`reports/phase5/ablation_results.json` and `ablation_table.md`.

| Metric | Complete system result |
|---|---:|
| Current-state accuracy | 4/4 (1.000) |
| Historical-state accuracy | 3/3 (1.000) |
| Initial-state accuracy | 2/2 (1.000) |
| Entity-identity accuracy | 3/3 (1.000), including one correct abstention |
| Overall query accuracy | 14/14 (1.000) |
| Evidence precision / recall | 0.958 / 1.000 over 12 labelled questions |
| Unsupported-answer rate | 0/12 answered questions |
| Lifecycle accuracy | 13/13 (1.000) |
| Answer-schema validity | 14/14 (1.000) |
| Visual false-association rate | 0/2 rejected images |
| Visual association precision | n/a (0 verified predictions in detector-free mode) |
| Conflict F1 | n/a (0 positive conflict cases in this detector-free set) |

The full matrix includes no-memory, latest-value, naive multimodal,
append-only temporal, no-provenance, no-visual-linking, and no-conflict
comparisons on the same inputs. The complete system and the other adaptive
variants tie on QA in this small set; removing provenance reduces evidence
precision and recall to zero. These six scenarios are regression evidence, not
a population estimate, and no confidence interval is claimed for small groups.

The unchanged, already-inspected Phase 4 test set was rerun as a historical
benchmark under `reports/phase5/phase4_historical_rerun/`. The complete system
scored 12/16 overall, current 5/8, historical 6/6, evidence precision/recall
0.731/0.769, unsupported 3/13 answered, lifecycle 16/18, and conflict recall
0/1. Two frozen labels encode superseded assumptions: H04 expects a
detector-free contextual image to create a conflict, and H07 expects a second
explicit car to be ignored. The data remains unchanged, so those outcomes are
reported as benchmark disagreement rather than relabelled as errors. Compared
with the recorded Phase 4 complete-system run, historical accuracy changed from
4/6 to 6/6 and overall accuracy from 11/16 to 12/16. Evidence P/R remained
0.731/0.769. Current accuracy changed from 6/8 to 5/8 because of the two stale
assumptions above. This is a historical comparison after failure inspection,
not an untouched held-out improvement claim.

## Commands and actual outcomes

The targeted regression run passed 69 tests. The new Phase 5 reliability and
evaluation subset passed 9 tests after an initial split-overlap assertion found
two duplicated observation strings; those strings were replaced before the
test-set experiment. The first matrix attempt stopped before evaluating any
system because one fixture requested an unsupported synthetic `plant` renderer;
the unrelated object was changed to the supported `phone` renderer and the
matrix was rerun successfully. Both the Phase 5 matrix and unchanged Phase 4
historical matrix completed for all eight requested systems.

The final commands are:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m pytest --basetemp .pytest_cache\phase5-full -q
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.ablations --data data/annotations/phase5_test.jsonl --split all --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/phase5
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.ablations --data data/annotations/phase4_test.jsonl --split all --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/phase5/phase4_historical_rerun
```

The final full-suite run passed **165 tests in 13.12 seconds**, with no failures
or skips. It used `.pytest_cache/phase5-final2` for temporary files and did not
open or overwrite configured user data.

## Remaining limitations

- Ordinal references are a narrow, evidence-present identity mechanism. Names,
  ownership changes, aliases, and visual re-identification need a larger design.
- Detector-free mode cannot verify image/entity identity, so association
  precision and positive conflict F1 cannot be estimated from this run.
- Pretrained YOLO/CLIP and real photographs were not run because suitable local
  model assets were unavailable and downloads were not authorized.
- Only colour is tracked and one claim is processed per ingest.
- The optional LLM guard checks selected values and known colour words; the
  deterministic answer remains the strongest grounding guarantee.
- Existing unqualified category records cannot be retroactively assigned an
  ordinal identity without user evidence.

## Manual verification

Run:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

With Light mode enabled, record `My car is red.`, then `I repainted my car
blue.`, then `I painted my car black.` with increasing source timestamps. Ask:

1. `What color is my car now?` -> black.
2. `What color was my car immediately before this?` -> blue.
3. `What color did my car start with?` -> red.
4. `Show me the history of my car's color.` -> red, blue, black.
5. `Which evidence supports the established car colour?` -> black with the
   latest supporting text timestamp.

Upload an unrelated red laptop image with a blue-car statement. The ingestion
details should label the image association contextual, while the car state is
accepted from text as blue and the image is absent from supporting evidence
IDs. In a fresh reset, record `My first car is red.` and `My second car is
blue.`; explicit questions return each value, while `What color is my car?`
abstains and asks which identity is meant.
