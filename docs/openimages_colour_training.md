# Open Images car-colour training: exploratory baseline v1

An actual classifier was trained and saved on 18 October 2026. This is a
four-colour car baseline for the existing integrated memory application, not a
pretrained detector, a deep encoder, a 12-colour model or a completed Track B
research evaluation.

## Data and annotations

Sources are the [official Open Images V7 download page](https://storage.googleapis.com/openimages/web/download_v7.html)
and [Localized Narratives](https://google.github.io/localized-narratives/).
V7 reuses the official V5 validation bounding boxes and validation image
metadata. Human-written narratives provide explicit colour descriptions;
bounding boxes alone do not supply colour or physical-object identity labels.

The acquisition selected at most 50 images per class, deterministically by
image-ID hash, for black, blue, red and white cars. It required one sufficiently
large car box and excluded flagged group, depiction, inside, truncated and
occluded boxes. All 186 selected images downloaded successfully. Crops use the
official boxes and are resized to fit 512 by 512 pixels.

The assistant inspected all eight contact sheets before splitting or training.
73 examples were excluded for caption disagreement, ambiguous colour, dominant
livery, apparent rendering or heavily filtered content. The retained 113 crops
contain black 29, blue 20, red 38 and white 26. These are **caption-derived,
assistant-reviewed labels, not independently verified human gold**. Exact
decisions and index fingerprint are preserved in
`data/annotations/openimages_colour_exclusions_v1.json` and
`reports/openimages_colour_v1/review_decisions.json`.

Photographer/source-author groups and conservative perceptual duplicate clusters
give 99 groups. Train/development/test contain 69/21/23 images and 59/20/20 groups,
with no shared declared group. Physical identity across different photographers
is unverified. Open Images' validation partition is the source pool; our held-out
test is a new subset, not an official Open Images challenge score.

`attribution.json` preserves all 186 source-image titles, author/profile URLs,
original landing URLs, provider-listed CC BY 2.0 licences, boxes, captions and
checksums. The annotation sources use CC BY 4.0. Individual contemporary rights
were not independently certified. Raw photos are ignored by Git and are not
redistributed as repository assets. See the official
[licensing statement](https://storage.googleapis.com/openimages/web/factsfigures_v7.html#licenses).

## Model and observed results

The model is balanced logistic regression over a 64-bin RGB histogram, with
`C=2`, maximum 3000 iterations and seed 13. Only training images fitted the
classifier. No pretrained weights or new packages were installed. No tuning or
retraining was performed after inspecting test predictions. Probabilities are
uncalibrated.

| Evaluation | Trained classifier | Existing HSV baseline |
| --- | --- | --- |
| Development, 21 crops | 17/21 (80.95%) | 15/21 (71.43%) |
| Held-out test, 23 crops | 19/23 (82.61%) | 17/23 (73.91%) |
| Actual Light-mode visual pipeline, same test | 19/23 (82.61%) | 17/23 (73.91%) |

Test recalls are black 4/6, blue 5/5, red 7/7 and white 3/5. The descriptive
image-level 95% Wilson interval for classifier accuracy is 62.86–93.02%; it does
not account for source groups. The two-image difference is not evidence of
statistical superiority. This small, selected, weakly labelled subset does not
establish general real-photo accuracy.

The actual pipeline's median measured crop inference time was 28.187 ms and
maximum 45.884 ms on this CPU environment. These measurements exclude object
detection and do not establish scalability. The pipeline had no detector and
used the whole supplied crop. It cannot establish uploaded-object identity.

The saved artifact is `models/openimages_car_colour_v1/color_head.joblib` (2557
bytes), SHA-256:
`232658bc14429531eaaf5b3e4c86903ef1f4814d63f0d47f99edd0dd6170e62c`.
It remains locally available and ignored by Git. Use only trusted joblib files.

Reports under `reports/openimages_colour_v1/` preserve split assignments, source
hashes, predictions, per-class metrics, provenance and review decisions. The
original training output is retained unchanged. Its HSV confusion matrix was
restricted to the four target labels; the supplementary pipeline report includes
out-of-scope HSV predictions such as gray/silver in an expanded confusion matrix.
The original accuracy counts already include these errors.

## Integration and use

`config.openimages.yaml` is an explicit opt-in profile. It activates this head
only for `car` evidence and uses a separate `data/processed/openimages_demo/`
storage location. The normal `config.yaml` is unchanged. Other entity categories
retain HSV processing. Model hash, feature method, class scope and calibration
status enter evidence provenance. Without a detector/re-identification model,
association remains contextual; a colour prediction is not identity proof.

From the project directory in PowerShell, with the existing model present:

```powershell
$env:AEGM_CONFIG_PATH = (Resolve-Path config.openimages.yaml).Path
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/account_app.py --server.address 127.0.0.1
```

Keep Light mode enabled. The trained histogram head does not require heavyweight
model downloads. After stopping the app, clear the opt-in variable with
`$env:AEGM_CONFIG_PATH = $null`. A missing explicitly selected config raises an
error rather than silently opening the default database.

Actual Python integration checks used the lexicographically first held-out white
crop, selected before prediction, and in-memory SQLite. Red text plus the white
photo produced a disagreement prompt. Selecting text preserved current/original
red; selecting the visual value produced current white and original red. Both
retained an audit decision. These are executed automated checks, **not a browser
demonstration or an actual human's decisions**.

## Reproduction

Executed environment: Windows, Python 3.14.6, numpy 2.4.6, Pillow 12.3.0,
scikit-learn 1.9.0, joblib 1.5.3, PyYAML 6.0.3, Streamlit 1.58.0 and pytest 9.0.3.
No clean-environment installation was performed for this run. Commands below use
the existing environment, and the download command requires network access.

For a fresh acquisition directory, the preparation sequence is:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.data.openimages_colour --per-class 50
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.data.openimages_review
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.data.openimages_review --exclusions data/annotations/openimages_colour_exclusions_v1.json
```

The acquisition, contact sheets and freeze commands refuse to overwrite their
records. Numbered review exclusions apply only when the review-index hash
matches. Upstream changes may prevent exact reacquisition; source hashes and
the exported split manifest allow verification rather than assuming equality.
Do not delete the existing dataset to reproduce. Use a separate `--root` and
point training to that root's manifest.

The actual training invocation was:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.training.real_color_experiment --manifest data/raw/openimages_colour_v1/manifest.csv --features hist --seed 13 --out models/openimages_car_colour_v1
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.openimages_model_validation
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.openimages_provenance
```

Outputs already exist; use fresh `--out` experiment/report directories for a
repeat, and the validation tool's `--experiment` option for the new model.
Do not overwrite this recorded run. The provenance exporter
is specific to the recorded v1 paths and refuses to overwrite its report; it is
not a general exporter for alternate runs.

## Remaining work and boundaries

Verification executed: the focused acquisition/config/model protocol tests
passed **14/14 in 14.12 seconds**; the full pytest suite passed **221 tests in
112.76 seconds**, with no failures or skips. `git diff --check` passed with only
Git's existing LF/CRLF conversion warnings. Canonical LF-normalized Phase 4 test,
Phase 5 test, Phase 6 development and Phase 6 test hashes matched their recorded
values. No frozen benchmark was rerun. To run the suite in the same environment:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q
```

Independent human colour adjudication, verified physical-object grouping, larger
held-out samples, more colours/categories, confidence calibration and comparison
with actual pretrained encoders/detectors remain unperformed. The four-colour
head cannot recognise colours outside its training scope. General photos with
multiple objects or backgrounds are outside this crop-level evaluation.

Browser testing of the opt-in profile remains pending. Frozen Phase 4–6 data and
historical benchmark claims are unchanged. No existing user database was opened,
reset or overwritten, and no Git commit or push was performed.
