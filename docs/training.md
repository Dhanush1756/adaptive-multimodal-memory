# Training guide

**Nothing in this repository has been run yet.** Commands below are the intended workflow;
expect to fix small bugs on the first run. Run everything from the repository root.

## What is trained, and what is not

| Component | Trained? | Why |
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

Synthetic images are an easy domain, so training on them only checks the pipeline. For a
result you can defend, collect real photos (no faces or people, legally yours, permission
if not) in one folder per colour:

```
data/raw/colors/red/*.jpg   data/raw/colors/blue/*.jpg   ...
```

```bash
python -m src.training.train_color_head --data data/synthetic --real-dir data/raw/colors
```

A fifth of the real photos (chosen by file-name hash) is held out and never trained on; the
script prints head vs HSV-only accuracy on them. Report the held-out number only. Aim for
30+ photos per colour across different lighting. If CLIP is not installed the head falls back
to histogram features.

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
