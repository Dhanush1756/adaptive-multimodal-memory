# Phase 6 - Research-grade benchmarking and comparative evaluation

## Preregistered research questions and hypotheses

The following questions, directional hypotheses, metrics, and interpretation
rules were fixed before executing the Phase 6 test benchmark.

| RQ | Question | Predeclared hypothesis | Primary measures |
|---|---|---|---|
| RQ1 | Does adaptive memory improve current and historical QA over simpler memory? | The complete system will exceed no-memory and latest-value memory on answer coverage and historical accuracy, and exceed naive retrieval on overall temporal QA. | Current, historical, initial, history, overall accuracy; coverage |
| RQ2 | Does evidence-aware retrieval improve supporting evidence? | The complete system will have higher evidence precision and recall than naive multimodal retrieval and the no-provenance ablation. | Macro evidence precision/recall with labelled-question denominators |
| RQ3 | Do temporal validity and conflict handling improve changing/conflicting decisions? | The complete system will exceed append-only temporal memory on lifecycle accuracy and verified-conflict F1 while retaining current-state accuracy. | Lifecycle accuracy; conflict precision/recall/F1; as-of accuracy |
| RQ4 | What do visual association, entity identity, and provenance contribute? | Verified visual links will be retained, rejected/ambiguous links will not affect state, explicit ordinal identities will remain isolated, and removing provenance will reduce citation metrics. | Visual association precision/FAR; identity accuracy; evidence P/R |
| RQ5 | When does the system fail or abstain? | It will correctly abstain before the first known state and for unresolved same-category references, but coverage and error analysis will expose unsupported language/identity limits. | Abstention rate/correctness, unsupported-answer rate, schema validity, individual errors |

An improvement is claimed only for an experiment actually run on identical
examples. A system that always abstains can score some unanswerable items, so
accuracy is always reported with answer coverage and abstention correctness.
No statistical-significance claim will be made unless the paired test and its
assumptions are reported. The complete system is `E_proposed`.

## Fixed methodology

Phase 6 uses two strictly separated tracks:

- **Track A:** deterministic rule-based NLP, hashing embeddings, rendered
  images, controlled detector outputs, corrupt bytes, and in-memory SQLite.
  Controlled detections test evidence association logic; they are not claims
  about YOLO accuracy.
- **Track B:** real photographs with locally available pretrained inference.
  It is run only if all required packages and weights are already local. No
  dependency, weight, image, or external service may be downloaded implicitly.

The Phase 6 files are new and do not replace Phase 4/5 annotations. Development
and test scenarios use separate wording banks and scenario IDs. The static
JSONL files are the experimental input; no annotation is regenerated during a
benchmark run. A fixed seed of `20261013` is used for bootstrap resampling and
recorded deterministic image seeds.

The controlled challenge set is independently specified from the existing
synthetic generator, but it is still synthetic. It is constructed from a
manually defined factor matrix and phrase banks, so scenarios within a family
are correlated and share structure. It must not be described as a fully
independent real-world dataset.

## Metric definitions

- Accuracy is correct labelled outputs divided by all labelled outputs in that
  group; correct abstention counts only on explicitly unanswerable questions.
- Coverage is answered questions divided by all questions.
- Abstention rate is abstained questions divided by all questions. Abstention
  correctness is correct abstentions divided by all abstentions.
- Unsupported-answer rate is wrong returned answers divided by answered
  questions. Its denominator excludes abstentions.
- Evidence precision/recall are macro averages across questions with labelled
  source sessions. Contextual non-supporting images are excluded from citations.
- Lifecycle accuracy is correct update actions divided by scored ingest
  decisions. Runtime errors and skips are reported separately, not converted
  into lifecycle predictions.
- Conflict P/R/F1 treats `CONTRADICTORY` as the positive lifecycle class.
- Visual precision treats detector-verified associations as positive
  predictions. False-association rate is false verified associations divided
  by labelled rejected images.
- Schema validity requires the Phase 5 answer contract fields and valid status.

Query accuracy uncertainty uses scenario-cluster bootstrap intervals when at
least five scenarios contribute. Pairwise comparisons use identical question
pairs, report discordant counts and an exact two-sided McNemar p-value, and use
a scenario-cluster bootstrap interval for the accuracy difference. Repeated
questions within a scenario are therefore not treated as independent in the
interval. Evidence macro means and sparse per-family results are descriptive.

## Systems

The fixed comparison includes no persistent memory, latest-value memory, naive
multimodal top-1 retrieval, append-only temporal memory, no-provenance,
no-visual-linking, no-conflict, and the complete system. They receive identical
session text, timestamps, rendered images, and controlled detections. Capability
differences are retained rather than hidden: simple baselines expose no adaptive
lifecycle decisions, naive retrieval does not implement temporal selection, and
the no-provenance view deliberately removes citations after answering.

## Dataset design

The static dataset contains **15 development scenarios** and **100 test
scenarios**. The test set has 210 ingest decisions and 265 questions. It was
expanded from a manually specified factor matrix; values, entities, dates, and
render seeds vary deterministically. It was not sampled from users or a natural
language corpus.

| Test family | Scenarios | Purpose |
|---|---:|---|
| temporal sequence | 15 | Three-state current/initial/previous/as-of/history QA |
| late arrival | 10 | Out-of-order event-time insertion |
| duplicate/corroboration | 10 | MERGE and evidence attribution |
| unrelated visual | 10 | Negative association with a different detected category |
| verified visual | 10 | Positive controlled association |
| verified conflict | 10 | Detector-linked text/image contradiction |
| entity identity | 10 | First/second instance and ambiguous-category abstention |
| abstention/irrelevance | 10 | Pre-history query, ignored text, and five equal-time text contradictions |
| corrupt image | 5 | Missing source time plus CV failure while preserving text |
| ambiguous visual | 5 | Two matching detections must not support state |
| long sequence | 5 | Five successive states and long history |

Each session stores ID, source timestamp, text, optional rendered-image spec,
optional controlled detections, and gold lifecycle/association labels. Each
query stores kind, intended intent, answerability, answer, and minimally
sufficient source sessions. Controlled detections include label, normalized
entity, bounding box, and confidence. Every system receives the same inputs.

Development and test IDs and phrase banks are disjoint. A regression checks
that there is no exact normalized utterance overlap and that the maximum
character-sequence similarity across development/test utterances is below
0.96. This guards obvious leakage but cannot make templated synthetic language
equivalent to independently collected language. Existing Phase 4/5 files were
not edited or used as Phase 6 test inputs.

Frozen hashes after annotation validation:

| File | SHA-256 |
|---|---|
| `phase6_dev.jsonl` | `a05c713fad1d8c06159c1b6a53502ea8748ac1e76ebb3ce39225aaa91c2e02bc` |
| `phase6_test.jsonl` | `831449bb23989915803bf715071a656bf663c6c335320890b8340edfa9fadaf7` |

The first attempted run exposed an unsupported `gray` rendered-image fixture.
No system completed. Only those three image specs were changed to the supported
rendering synonym `silver`; text and gold state values were retained. A later
run executed every system but failed while writing the new summary due to a
report-only variable-name error. A coverage audit then found that missing source
times and text-only contradictions were not explicit. Five existing corrupt
image cases were assigned missing source times, and five existing irrelevance
cases were converted to equal-time contradictory text observations. Scenario
and query counts did not change, system code was not modified, annotation tests
passed, and the hash above became the final freeze. The entire matrix was rerun
from the beginning. Only that final successful command supplies the results
below.

## Results

### Execution

Track A ran on October 13, 2026 with Python 3.14.6 on Windows 11. Components
were hashing-256 text embeddings, HSV colour extraction, colour-histogram image
embeddings, controlled detector outputs where annotated, and otherwise the
detector-free fallback. Every adaptive run used in-memory SQLite. There were no
query or session runtime errors for the complete system and no skipped cases.

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.ablations --data data/annotations/phase6_test.jsonl --split all --seed 20261013 --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/phase6
```

The run manifest records the exact command, full configuration and its hash,
dataset hash, platform, component status, dirty repository status, family
counts, and requested systems. This repository has no available Git commit, so
the manifest correctly records `git_commit: unavailable` rather than inventing
a version identifier.

### Complete-system metrics

| Metric | Result | Denominator / interval |
|---|---:|---|
| Overall accuracy | 240/265 = 0.906 | scenario-bootstrap CI [0.874, 0.940] |
| Current-state accuracy | 90/90 = 1.000 | CI [1.000, 1.000] |
| Historical-state accuracy | 40/55 = 0.727 | CI [0.656, 0.816] |
| Initial-state accuracy | 15/20 = 0.750 | CI [0.550, 0.900] |
| Full-history accuracy | 25/30 = 0.833 | CI [0.667, 0.933] |
| Entity-identity accuracy | 30/30 = 1.000 | CI [1.000, 1.000] |
| Evidence precision | 0.908 | 245 labelled questions; CI [0.882, 0.938] |
| Evidence recall | 0.914 | 245 labelled questions; CI [0.890, 0.942] |
| Answer coverage | 245/265 = 0.925 | CI [0.893, 0.952] |
| Abstention rate | 20/265 = 0.075 | CI [0.047, 0.107] |
| Abstention correctness | 20/20 = 1.000 | CI [1.000, 1.000] |
| Unsupported-answer rate | 25/245 = 0.102 | answered-question denominator; CI [0.066, 0.134] |
| Answer-schema validity | 265/265 = 1.000 | CI [1.000, 1.000] |
| Lifecycle accuracy | 200/210 = 0.952 | scenario-bootstrap CI [0.913, 0.990] |
| Conflict P/R/F1 | 1.000 / 1.000 / 1.000 | 10 TP, 0 FP, 0 FN; F1 CI [1.000, 1.000] |
| Visual association precision | 1.000 | 30 TP, 0 FP; CI [1.000, 1.000] |
| Visual false-association rate | 0.000 | 0 FP / 15 rejected; 15 TN; CI [0.000, 0.000] |

The intervals resample 100 scenarios and preserve questions within their
scenario. Sparse conflict/visual results are controlled-test results and are
reported as counts rather than claims about natural-image prevalence.

### Baseline comparison

| System | Overall | Current | Historical | Initial | Identity | Evidence P/R | Coverage | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| No memory | 20/265 | 0/90 | 10/55 | 0/20 | 10/30 | 0.000 / 0.000 | 0/265 | n/a (0 answered) |
| Latest value | 125/265 | 75/90 | 10/55 | 0/20 | 10/30 | 0.469 / 0.429 | 170/265 | 55/170 |
| Naive multimodal | 141/265 | 60/90 | 11/55 | 13/20 | 20/30 | 0.576 / 0.535 | 230/265 | 89/230 |
| Append-only temporal | 195/265 | 75/90 | 40/55 | 15/20 | 10/30 | 0.765 / 0.731 | 250/265 | 65/250 |
| No provenance | 240/265 | 90/90 | 40/55 | 15/20 | 30/30 | 0.000 / 0.000 | 245/265 | 25/245 |
| No visual linking | 220/265 | 80/90 | 40/55 | 15/20 | 30/30 | 0.827 / 0.833 | 245/265 | 45/245 |
| No conflict handling | 220/265 | 80/90 | 40/55 | 15/20 | 30/30 | 0.827 / 0.833 | 245/265 | 45/245 |
| Complete system | 240/265 | 90/90 | 40/55 | 15/20 | 30/30 | 0.908 / 0.914 | 245/265 | 25/245 |

The proposed-minus-baseline paired overall-accuracy differences were +0.830
versus no memory, +0.434 versus latest value, +0.374 versus naive multimodal,
and +0.170 versus append-only temporal. Their scenario-bootstrap difference
intervals excluded zero and every discordant query favored the proposed system
in this controlled set. Exact McNemar p-values are stored in
`paired_comparisons.json`. These are descriptive results on a constructed
benchmark: multiple systems and metrics were compared, templates are
correlated, and no multiplicity-adjusted statistical-significance claim is
made.

The complete system tied the no-provenance ablation on answers, as expected,
while provenance removal reduced evidence precision/recall to zero. It exceeded
the visual-linking and no-conflict ablations by 20/265 questions, all in the
controlled verified-conflict family. The append-only baseline tied the complete
system on historical and initial accuracy; the measured gain came from current
state, identity isolation, evidence quality, conflict decisions, and lower
unsupported answers rather than from every temporal subgroup.

### Error analysis

The complete system produced 25 incorrect answers and 10 lifecycle errors:

1. Fifteen questions used the unseen wording `immediately preceded`. The parser
   recognizes `preceding` but not `preceded`, classified them as `CURRENT`, and
   returned the newest state. This is a temporal query-interpretation defect.
2. Five long sequences began with `Initially my <entity> is <colour>.` The
   extractor's conservative past-state guard rejected `initially` without an
   internally parsed date even though the caller supplied the observation
   timestamp. The next update became `ADD`, producing five initial-answer and
   five history-answer errors plus ten lifecycle mismatches. This is an NLP
   extraction/policy defect. A future fix should explicitly define when source
   time grounds an initial-state cue; it was not changed during this benchmark.
3. Five correctly answered previous-state queries cited both adjacent states
   while the annotations label only the minimally sufficient previous source.
   This lowers evidence precision but is primarily an evidence-label/policy
   mismatch rather than a wrong answer.
4. Ten unfamiliar evidence questions used `observations justify`, which is not
   an evidence-intent cue. They were classified `CURRENT`, but returned the
   correct scalar and supporting source. This is query-intent coverage debt
   without an answer or citation error.

All 20 required abstentions were correct: ten pre-history questions and ten
ambiguous category-only car questions. There were no malformed answer schemas,
false verified visual links, missed controlled conflicts, or complete-system
runtime failures. Five simple baselines raised session errors on corrupt images;
these are explicitly recorded and excluded from lifecycle denominators.

`reports/phase6/error_analysis.json` contains each affected question and
session. Its deterministic category is a first-pass aid; the four groups above
are the manually reviewed interpretation.

## Limitations and conclusions

RQ1 is **partly supported**. Adaptive memory substantially improved overall and
current-state QA over all simple baselines and improved identity-aware QA, but
it did not exceed append-only temporal memory on the historical or initial
subgroups. The unchanged extraction/parser failures affected both adaptive and
append-only systems.

RQ2 is **supported within Track A**. Evidence-aware retrieval outperformed
naive multimodal retrieval, and removing provenance reduced citation metrics to
zero. Precision remains sensitive to whether transition context or only the
minimal source is considered correct.

RQ3 is **partly supported**. The complete system achieved 10/10 controlled
conflicts, perfect current accuracy, and lower unsupported answers; disabling
conflict handling lost 20 answers across current/evidence questions. The
append-only implementation exposes no comparable lifecycle decisions, so the
benchmark cannot claim a direct lifecycle-accuracy improvement over it.

RQ4 is **supported for implemented, controlled cases**. Explicit ordinal
identity scored 30/30, provenance was necessary for citations, and controlled
visual association scored 30 TP and 15 TN. These results validate association
and memory logic, not detector accuracy or visual re-identification.

RQ5 is **supported and exposes clear limits**. Abstention correctness was 20/20
at 92.5% coverage. The remaining unsupported answers came from specific unseen
temporal wording and initial-observation extraction, not malformed output.

Track B was **not performed**. A read-only check found `torch` and
`ultralytics`, but no local `.pt`/`.onnx` weights, no `transformers` package,
and no cached configured CLIP model (the Hugging Face cache contained unrelated
NER/sentence/sign-language models). Running configured YOLO/CLIP could require
downloads or installation, which was prohibited. Rendered images, HSV, and
controlled detections must not be presented as pretrained or real-photo
performance.

The benchmark is large enough for stable regression comparisons but remains a
templated controlled challenge set. It has no human annotator agreement,
natural class prevalence, licensed real-photo track, calibrated confidence, or
external replication. The main supported contribution is the integrated
adaptive memory mechanism: it preserves temporally ordered states, isolates
explicit identities, handles controlled conflicts, and returns traceable
evidence. Standard NLP, HSV, detection, SQLite, and retrieval components are
infrastructure rather than separate novelty claims.

Machine-readable raw outcomes, run metadata, paired results, and individual
errors are in `reports/phase6/`. Reproduce with the command above; benchmark
runs never open the configured user database.

## Verification record

The Phase 6 annotation/reporting regression subset passed **6 tests** before
the frozen benchmark. After the successful benchmark and report audit, the
complete project suite passed:

```text
169 passed in 22.75s
```

There were no failures or skips. Pytest used
`.pytest_cache/phase6-final2`; evaluation systems used `:memory:` databases. No
configured user database was opened, reset, or copied. No dependency, model,
or external data was installed or downloaded.

Phase 6 files:

- `data/annotations/phase6_dev.jsonl` - 15 development scenarios, not scored.
- `data/annotations/phase6_test.jsonl` - frozen 100-scenario Track A set.
- `reports/phase6/ablation_results.json` - run metadata and all raw outcomes.
- `reports/phase6/research_summary.md` and `ablation_table.md` - comparison tables.
- `reports/phase6/paired_comparisons.json` - paired counts, exact tests, and bootstrap intervals.
- `reports/phase6/error_analysis.json` and `.md` - individual issues and category summary.
- `reports/phase6/run_manifest.json` - command, hashes, configuration, components, and repository state.
- `reports/phase6/model_availability.json` - read-only Track B availability audit.
