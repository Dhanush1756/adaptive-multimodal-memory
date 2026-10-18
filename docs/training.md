# Training guide

The offline reliability suite has been run; see [Phase 1 results](phase1_reliability.md).
Real-photo training and pretrained inference remain unperformed. See
`docs/phase13_14_implementation.md` for the new group-based real-photo protocol
and current blockers. Run everything from the repository root.

## What is trained, and what is not

| Component | Trainable / training role (not evidence of an executed run) | Why |
|---|---|---|
| Memory engine (ADD/UPDATE/MERGE/…) | No, rule-based | Deterministic and testable; this is the project's contribution |
| YOLO, CLIP, sentence-transformer | No, pretrained | Per the brief: no training of large models |
| Query-intent classifier | Yes (seconds, CPU) | Backs up the rules on paraphrased questions |
| Colour head (CLIP features → colour) | Yes (minutes, CPU) | Replaces CLIP zero-shot, blended with HSV |
| YOLO fine-tune | Optional | Only if your real photos are missed by COCO classes |

A learned memory-update policy is a possible extension; the engine currently has no hook for it.

## 0. Setup

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm        # optional
pytest -q                                       # run the unit tests first
```

## 1. Generate the benchmark

```bash
python -m src.data.make_dataset --n 300 --seed 0 --out data/synthetic --save-images
```

Scenarios are split 70/15/15 into train/dev/test **by scenario** (seed 0) by
`split_dataset`. Keep the seed fixed so no scenario ever moves between splits.

## 2. Smoke test without downloads

```bash
python -m src.evaluation.ablations --light --n 40 --split dev
```

`--light` uses hashing text embeddings and HSV colour only. If this fails, fix it before
loading any pretrained model.

## 3. Intent classifier

```bash
python -m src.training.train_intent_classifier
```

Prints rules-only vs model accuracy on synthetic dev questions and on held-out paraphrases
(every 4th row of `data/annotations/intent_paraphrases.csv`). To make this meaningful:
add 100+ paraphrases written by people who have not read the rules, with the label of the
`Intent` enum in `src/agent/query_parser.py`. The seed rows were written by the assistant;
review the labels.

## 4. Colour head

For real-photo work use the new manifest-based experiment below. The old
`train_color_head.py --real-dir` filename-hash split is disabled. The old script
remains usable for synthetic-only mechanics, while real-photo work requires a
group manifest.

```powershell
python -m src.training.real_color_experiment --manifest data/raw/colors/manifest.csv --features hist --out models/colour-study-v1
```

The manifest schema is illustrated in `docs/real_photo_manifest.example.csv`.
Group all views of the same physical object before splitting; record source and
permission. The experiment rejects duplicate decoded pixels, flags similar dHash
images across groups, allocates groups with a fixed seed, and requires every
included colour in train, dev and test. Human review of near-duplicates remains
necessary. It writes a model, split manifest and per-class classifier/HSV metrics.
`--features clip` requires locally cached CLIP assets and fails if unavailable;
it never silently substitutes histogram features. The optional model environment
input file is untested and is not the supported Light-mode dependency profile.

Set `cv.color_head_path` to the resulting trusted local artifact to load it.
Never load a joblib artifact from an untrusted source. Generated weights are
ignored by Git. No real-photo artifact was trained during Phase 13.

Collect lawful, labelled photographs in one folder per colour:

```
data/raw/colors/red/*.jpg   data/raw/colors/blue/*.jpg   ...
```

Folder names alone do not establish a valid split. Add reviewed physical-object
IDs and source permissions to the manifest. The target is approximately 100
images per colour with lighting/viewpoint variation where feasible. Report the
actual size and represented classes if the available dataset is smaller.

## 5. Component evaluation (NLP-only and CV-only)

```bash
python -m src.evaluation.component_eval --split test \
    --paraphrases data/annotations/intent_paraphrases.csv --out reports/results/components.json
```

## 6. Ablation study (the main table)

```bash
python -m src.evaluation.ablations --split test --out reports/results
```

Writes `ablation_results.json` and `ablation_table.md` with 95% cluster-bootstrap CIs. The
table is filled only from measured results.

## 7. Evaluation rules to follow

1. Choose thresholds and weights (`config.yaml`) on **dev**; run **test** once at the end.
2. Report synthetic results as synthetic. A real-photo set (even 50 sessions you annotate by
   hand) is what supports claims about real use.
3. Include the error taxonomy (brief §54): inspect `raw_queries` / `raw_sessions` in
   `ablation_results.json` for wrong answers and wrong actions.
4. Do not tune on the test split, and do not retrain after seeing test numbers without saying so.
5. Retrain the intent classifier and colour head only with the same `--seed` as the dataset.

## 8. Optional: fine-tune YOLO

Only needed if COCO classes miss your objects (the code maps car/truck/bus, bicycle/motorcycle,
laptop, cell phone, couch). Label images in YOLO format, then:

```bash
yolo detect train data=your_data.yaml model=yolov8n.pt epochs=50 imgsz=640
```

Set `cv.yolo_weights` in `config.yaml` to the resulting `best.pt` and extend
`COCO_TO_ENTITY` in `src/cv/detection.py` for new class names. A GPU (Colab T4 is enough)
is advisable.

## 9. Optional: LLM answers

`MemoryAgent(answer_llm=fn)` takes any `fn(prompt: str) -> str`. The prompt contains only
the retrieved timeline and evidence. Without it, answers come from deterministic templates
that cannot contain a value that is not in memory.
