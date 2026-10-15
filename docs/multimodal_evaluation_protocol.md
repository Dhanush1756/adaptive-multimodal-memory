# Multimodal evaluation protocol

## Scope separation

Results must always identify one of these scopes:

1. **Frozen Track A:** existing deterministic annotations and Phase 6 artifacts. Do not edit or overwrite them.
2. **Post-benchmark regression:** code-level behavior added after Phase 6, including provenance metadata and conflict questions. No aggregate research metric is claimed.
3. **Future Track B:** separately approved pretrained CV and real-photo evaluation. Not yet executed.

## Frozen Track A

The frozen Phase 6 test set contains 100 scenarios, 210 ingestion sessions, 265 questions, and 11 families. It compares no memory, latest value, naive multimodal retrieval, append-only temporal memory, three component removals, and the proposed system. Reproduce into a new directory:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.ablations `
  --data data/annotations/phase6_test.jsonl --split all --seed 20261013 --light `
  --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal `
  E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed `
  --out reports/reproduction/phase6
```

Do not compare a future real-image result directly with Track A unless inputs, denominators, and protocol are identical.

## Measures

### NLP

- entity/attribute extraction exact match;
- temporal-intent and slot accuracy;
- current, previous, initial, history and as-of QA accuracy;
- identity-isolation accuracy;
- evidence precision/recall;
- unsupported-answer rate, coverage and correct abstention.

### CV

- detector precision/recall and mAP only with object boxes;
- visual color accuracy and confusion matrix;
- association accuracy by `verified`, `contextual`, `ambiguous`, and `unmatched` class;
- false-association rate;
- confidence reliability by fixed threshold;
- evidence traceability: image ID, box, event time, source and model metadata completeness.

### Integrated system

- agreement-case answer accuracy;
- contradiction detection precision/recall/F1;
- temporal lifecycle correctness;
- historical preservation and identity isolation;
- multimodal evidence precision/recall;
- ambiguous-evidence abstention;
- text-only, image-only and combined-input performance.

All reported metrics require counts and denominators. Scenario-cluster bootstrap intervals are preferred for QA. Multiple paired comparisons must be described as exploratory unless corrected.

## Future Track B dataset

Create new versioned files outside frozen Phase 4–6 annotations. A suitable manifest records dataset version, license, image SHA-256, entity identity, bounding box where available, color label, event time, source, annotators, agreement/adjudication, split and exclusion reason. Freeze configuration, model names/versions, thresholds, seed, environment and output directory before test execution.

Recommended baselines are text-only, vision-only observation, combined NLP+CV, no lifecycle, no evidence validation, and append-only memory. Model downloads and real-photo collection require separate approval.

## Current post-benchmark checks

Regression tests verify that event time and ingestion time remain distinct, extractor/model identifiers survive storage and retrieval, text and image evidence expose stable IDs, unresolved conflict queries return `uncertain`, and human resolution removes the unresolved conflict while retaining the record. These tests validate behavior; they are not a new benchmark.
