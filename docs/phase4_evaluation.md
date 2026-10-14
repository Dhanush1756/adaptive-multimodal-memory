# Phase 4 - Independent evaluation, real-image status, and ablations

Evaluated on October 13, 2026. This phase changes evaluation infrastructure and
adds fixed annotations; it does not tune the application against the held-out
results. No dependency or model was downloaded, no external service was used,
and all adaptive agents used in-memory SQLite databases.

## Evaluation audit

The Phase 3 run generated 30 scenarios with `generate_dataset(30, seed=314159)`.
The generator chose entities, colours, observation types, conflicts, queries,
answers, evidence-session labels, and expected lifecycle actions in one code
path. Its 171 decisions were all generated sessions; its 26 conflicts were the
sessions randomly assigned a conflict kind. The rules used to label ADD,
UPDATE, MERGE, IGNORE, and CONTRADICTORY closely mirror the implemented memory
engine. Text and query templates repeat across generated scenarios and splits.

Consequently, the Phase 3 perfect lifecycle/conflict scores measure consistency
with the generator and are useful regression evidence, but they are not an
independent estimate of generalization. The deployed `MemoryAgent` was used,
including NLP extraction, light HSV vision, memory updates, temporal/image
retrieval, and answer generation. The data itself was not independent.

Metric denominators were executable, but the previous documentation called the
evidence denominator “evidence questions.” The implementation scores every
labelled question that has `evidence_sessions`. Phase 4 keeps that broader and
useful definition and documents it accurately. A separate evaluator bug also
treated a baseline runtime error as a lifecycle prediction; runtime errors are
now counted separately and excluded from lifecycle-action denominators.

## Fixed annotation set

The annotation format is JSON Lines. Each scenario has `scenario_id`, `entity`,
ordered `sessions`, and `queries`. A session records its source ID/time, text,
optional deterministic image specification or failure case, and gold lifecycle
action. A query records kind, intended intent, answer, gold source sessions, and
`answerable: false` where abstention is required.

Two files are fixed before the held-out run:

* `data/annotations/phase4_dev.jsonl`: 2 development scenarios.
* `data/annotations/phase4_test.jsonl`: 8 held-out scenarios, 18 ingest
  decisions, 16 questions, 13 questions with gold evidence sessions, and 3
  questions requiring abstention.

The split is manually fixed rather than randomly sampled. No random split seed
applies. Deterministic self-created image seeds are recorded in the test file
(`401`, `402`, and `501`). A regression verifies unique scenario IDs and no
exact normalized observation-text overlap between development and test. The
development set was not executed or used to alter rules in this phase. After
the held-out run, only reporting/evaluator defects were fixed; system behavior
and held-out annotations were not changed.

The test covers three successive changes, original/previous/current/as-of
questions, late arrival, repeated evidence, a text/image conflict, an unrelated
image, a missing timestamp, failed image decoding, irrelevant text, dates before
the first state, and two same-category objects. The latter is intentionally
unanswerable because the architecture has no instance-level entity identity.
There is no claim that these eight scenarios represent a population sample.

## Metrics

* Current and historical accuracy: correct answers or correct abstentions in
  each intent group divided by that group’s labelled questions.
* Evidence precision/recall: macro average over the 13 questions with gold
  source sessions. Precision compares gold sessions with all cited sessions;
  recall measures recovered gold sessions.
* Unsupported-answer rate: wrong returned values, including answers to
  unanswerable questions, divided by all answered questions.
* Lifecycle accuracy: correct exposed lifecycle decisions divided by the 18
  labelled ingest sessions. Baselines that expose no decisions report `n/a`.
* Conflict precision/recall/F1: `CONTRADICTORY` is the positive lifecycle class.
  There is one labelled conflict, so this estimate is especially unstable.
* Bootstrap intervals resample the eight scenarios 500 times. With only eight
  clusters, intervals are descriptive and coarse; groups with fewer than five
  contributing scenarios have no interval.

## Systems and ablations

| Name | Definition | Interpretation limit |
|---|---|---|
| `N_no_memory` | Discards observations and always abstains. | Control, not a useful assistant. |
| `L_latest_value` | Keeps only one latest value per entity. | Cannot answer historical questions. |
| `B_naive_multimodal` | Top-1 evidence retrieval without temporal/adaptive lifecycle. | Retrieval and memory behavior both differ. |
| `C_append_only_temporal` | Time-ordered observations with no merge/conflict lifecycle. | Removes several adaptive behaviors together. |
| `E_no_provenance` | Full system with citations removed after answering. | Directly measures citation metrics; QA is unchanged. |
| `E_no_visual_linking` | Existing unlinked text/image streams. | Changes more than one downstream decision. |
| `E_no_text_image_conflict` | Full system with text/image conflict thresholds disabled. | Image-only conflict handling still exists. |
| `E_proposed` | Complete implemented system. | Light components, one entity instance per category. |

These are controlled comparisons on the same inputs. They are not causal proof:
several baselines and the visual-linking ablation alter multiple behaviors.

## Held-out results

All eight systems completed successfully. Full raw records and per-question
outcomes are in `reports/phase4/ablation_results.json`; the generated table is
in `reports/phase4/ablation_table.md`.

| System | Current | Historical | Evidence P/R | Unsupported | Lifecycle | Conflict P/R/F1 |
|---|---:|---:|---:|---:|---:|---:|
| No memory | 1/8 | 2/6 | 0.000 / 0.000 | n/a (0 answered) | n/a | n/a |
| Latest value | 5/8 | 2/6 | 0.385 / 0.333 | 3/8 | n/a | n/a |
| Naive multimodal | 4/8 | 0/6 | 0.308 / 0.256 | 11/15 | n/a | n/a |
| Append-only temporal | 5/8 | 4/6 | 0.615 / 0.641 | 6/13 | n/a | n/a |
| No provenance | 6/8 | 4/6 | 0.000 / 0.000 | 4/13 | 15/18 | 0.500 / 1.000 / 0.667 |
| No visual linking | 5/8 | 4/6 | 0.615 / 0.692 | 5/13 | 15/18 | 0 / 0 / 0 |
| No text/image conflict | 5/8 | 4/6 | 0.615 / 0.692 | 5/13 | 15/18 | 0 / 0 / 0 |
| Complete system | 6/8 | 4/6 | 0.731 / 0.769 | 4/13 | 15/18 | 0.500 / 1.000 / 0.667 |

For the complete system, current-state accuracy is 0.750 with scenario-bootstrap
CI `[0.375, 1.000]`; historical accuracy is 0.667 with no interval because too
few scenario clusters contribute. Overall accuracy is 11/16. The complete
system improves current QA and evidence attribution over the tested simple
baselines, ties append-only temporal memory on historical QA, and does not
reduce unsupported answers below the no-provenance ablation because removing
citations does not change answers.

## Error analysis

The complete system made five query errors:

1. “Which colour did the car start with?” was parsed as `PREVIOUS` instead of
   `ORIGINAL`, returning blue rather than red. This is a query-intent coverage
   limitation.
2. The late observation “On this date the car was blue.” produced no extracted
   claim, so it was ignored and the September 18 as-of answer remained red.
3. The unfamiliar evidence question selected all evidence and returned a
   one-item list rather than the annotated scalar value. This mixes query-parser
   coverage with answer-shape semantics.
4. A red laptop image submitted with blue-car text was contextually associated
   in detector-free light mode and created a false conflict. This is the main
   visual-association failure.
5. “First car” and “second car” collapsed to `car_001`; the system updated the
   first car and then answered the deliberately unanswerable second-car query.
   This is the known instance-identity limitation.

The three lifecycle errors correspond to the ignored late observation, the
irrelevant-image false conflict, and the second-car update. Conflict precision
is 1/2 and recall 1/1. Evidence precision below recall is partly caused by
transition answers citing both adjacent states while the annotation marks only
the minimally sufficient state.

## Computer-vision validation status

The installed environment contains `torch` and the `ultralytics` package, but
no local YOLO weight file was found. `transformers` is not installed and no
local CLIP model cache was found. Initializing configured YOLO would be able to
trigger a model download, which was prohibited. Therefore pretrained YOLO/CLIP
and real-photo inference were **not run**.

The held-out run did execute real decoding/analysis code on deterministic,
self-created rendered images using HSV and colour-histogram fallbacks. It also
exercised a corrupt-image failure and verified that the adaptive agent retained
usable text. This is light-mode integration validation, not real-image or
pretrained-model validation. Mocked Phase 2 detector tests remain unit tests and
are not counted as real-model results.

## Commands and run status

Focused validation:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -c "... pytest ... tests/test_phase4_evaluation.py tests/test_evaluation_metrics.py tests/test_reliability.py"
```

Held-out matrix:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.ablations --data data/annotations/phase4_test.jsonl --split all --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/phase4
```

The first matrix attempt executed all systems and wrote artifacts but failed
while printing a Unicode checkmark to the Windows console. The output path was
made encoding-safe and the final command completed successfully. Real-model
inference was skipped for the availability reasons above. No development-set
score was run. Focused Phase 4 validation passed 24 tests. The final complete
suite passed **155 tests in 13.40 seconds**, with no failures or skips.

## Recommended next steps

Expand the manually annotated set through independent annotation, including
real licensed photographs, before drawing research conclusions. Add explicit
entity-instance identifiers before claiming support for multiple cars. Improve
query-intent paraphrase coverage using development data only, then freeze and
evaluate once on a new test set. Acquire YOLO/CLIP weights and dependencies only
through a separately approved, documented model-validation run.
