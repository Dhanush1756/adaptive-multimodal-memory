# Release manifest

Prepared on October 14, 2026 for **Adaptive Evidence-Grounded Memory for
Long-Term NLP Agents**. This manifest describes the proposed prototype release;
it does not assert that a clean installation or real-model CV track was tested.

## Release scope

The supported release is the deterministic **Track A prototype**: rule-based
NLP, hashing embeddings, Light-mode HSV/colour-histogram vision, controlled
detector annotations in evaluation, SQLite temporal memory, Streamlit UI, the
frozen Phase 4-6 annotations/results, and the complete automated test suite.

The separate real-model research scope is not part of the validated package.
It requires approved local YOLO/CLIP assets, the missing Transformer dependency,
licensed real photographs, fixed labels, and a separately reported evaluation.

## Project structure

| Path | Release purpose |
|---|---|
| `app/streamlit_app.py` | Streamlit demonstration application. |
| `src/agent/` | End-to-end agent, query parsing, intent interface, and grounded answers. |
| `src/nlp/` | Text normalization, entity/relation/time extraction, and embeddings. |
| `src/cv/` | Image loading, optional detection/CLIP interfaces, HSV attributes, and embeddings. |
| `src/multimodal/` | Text/image evidence construction, association, and fusion. |
| `src/memory/` | Schema, SQLite store, temporal chain, conflicts, and lifecycle rules. |
| `src/retrieval/` | Temporal, entity, text, image, and hybrid retrieval. |
| `src/evaluation/` | Metrics, controlled runner, baselines, ablations, and research reports. |
| `src/data/` | Deterministic synthetic scenario/image utilities. |
| `src/training/` | Optional intent and colour-head training utilities. |
| `tests/` | Component, regression, evaluation, persistence, and Streamlit integration tests. |
| `data/annotations/` | Fixed development/test annotations and intent paraphrases. |
| `reports/phase4/`-`reports/phase6/` | Historical raw results, tables, manifests, and error analyses. |
| `docs/` | Phase records, synthesis, validation/demo procedures, and release reports. |
| `config.yaml` | Initial paths, component names, thresholds, and scoring weights. |
| `requirements.txt` | Unpinned dependency names; not a lock file. |
| `pytest.ini`, `conftest.py` | Test discovery and isolation configuration. |
| `README.md`, `LICENSE`, `.gitignore` | Entry point, license, and local-artifact exclusions. |

## Python and dependencies

The final Phase 9 run used:

```text
Python 3.14.6 (Anaconda), Windows 11
numpy 2.4.6
Pillow 12.3.0
PyYAML 6.0.3
scikit-learn 1.9.0
joblib 1.5.3
pytest 9.0.3
streamlit 1.58.0
torch 2.14.0
ultralytics 8.4.147
sentence-transformers: not installed
transformers: not installed
```

These are observed versions, not declared compatibility bounds. The repository's
`requirements.txt` is unpinned. No fresh virtual environment or clean install
was created in Phase 9, so the package must not be described as clean-install
verified. Light mode uses the installed core packages and deterministic
fallbacks without downloading model assets.

## Launch and test commands

Run commands from the repository root. In the validated environment:

```powershell
$python = 'C:\Users\DHANUSH S\anaconda3\python.exe'
& $python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Keep **Light mode (no model downloads)** enabled. A portable invocation after
activating another prepared environment is:

```powershell
python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Run the complete automated suite with scratch storage:

```powershell
& $python -B -m pytest -q --basetemp .pytest_cache\release-validation
```

Phase 9 result: **176 passed in 28.29 seconds**, with zero failures and zero
skips. Tests use temporary or in-memory databases and do not use configured
user memory.

## Evaluation reproduction

The historical Phase 6 Track A command was:

```powershell
& $python -B -m src.evaluation.ablations --data data/annotations/phase6_test.jsonl --split all --seed 20261013 --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/phase6
```

Do not overwrite the historical directory during release verification. Use a
new output location if reproduction is explicitly required:

```powershell
& $python -B -m src.evaluation.ablations --data data/annotations/phase6_test.jsonl --split all --seed 20261013 --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/reproduction/phase6
```

The benchmark was not rerun in Phase 9. The preserved reference contains 100
scenarios, 210 sessions, 265 questions, and eight systems. Expected generated
files are `ablation_results.json`, `ablation_table.md`, `research_summary.md`,
`run_manifest.json`, `paired_comparisons.json`, and `error_analysis.json/.md`.

Earlier fixed comparisons can be reproduced into separate directories with:

```powershell
& $python -B -m src.evaluation.ablations --data data/annotations/phase4_test.jsonl --split all --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/reproduction/phase4
& $python -B -m src.evaluation.ablations --data data/annotations/phase5_test.jsonl --split all --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/reproduction/phase5
```

## Configuration requirements

- Relative paths in `config.yaml` resolve from the repository root.
- `paths.db_path` is the base location. Streamlit derives a private
  `memory_sessions/<namespace>/memory.db` rather than opening the unscoped file.
- `paths.image_dir` is similarly namespaced for the UI.
- Tests/benchmarks explicitly use temporary files or `:memory:`.
- Thresholds and scoring weights are initial engineering values, not calibrated
  probabilities.
- Configured `yolov8n.pt` and `openai/clip-vit-base-patch32` assets are not
  locally available in the validated environment. Do not disable Light mode if
  doing so could initiate an unapproved download.
- No LLM provider is configured; deterministic answer templates are the
  validated default.

## Required release files and outputs

Include:

- application, source, and tests listed above;
- `config.yaml`, `requirements.txt`, `pytest.ini`, and `conftest.py`;
- `data/annotations/*.jsonl` and `intent_paraphrases.csv`;
- Phase 4-6 report artifacts, especially all eight files under `reports/phase6/`;
- Phase documentation, final validation/demo procedure, research synthesis,
  presentation outline, and Phase 8-9 release reports;
- README, MIT license, and `.gitignore`.

The Streamlit launch should create a private SQLite database only after a new
browser session starts. Tests should report 176 passing tests in the current
source snapshot, although runtime can vary. Phase 6 reproduction should write
to a new directory and retain raw outcomes for all eight systems.

## Files intentionally excluded

Do not package or commit:

- `.git/` when distributing a source archive;
- `.pytest_cache/`, `__pycache__/`, and `*.pyc`;
- `.env` or local credential/configuration variants;
- `data/processed/`, `data/raw/`, and generated `data/synthetic/` contents;
- `*.db` and other user/session SQLite files;
- uploaded images and per-session image directories;
- downloaded model weights, local model caches, and trained local artifacts;
- logs, coverage output, build output, virtual environments, and editor state;
- the root `Microsoft/` directory. It contains a local PowerShell
  `ModuleAnalysisCache` and is unrelated to the project. It was inspected but
  not deleted.

The current `.gitignore` already excludes Python caches, pytest cache, `.env`,
`models/*.joblib`, generated/raw/processed data, results scratch output, and
`*.db`. Before a public first commit, review adding:

```gitignore
Microsoft/
.venv/
venv/
env/
.coverage
htmlcov/
coverage.xml
build/
dist/
*.egg-info/
*.log
models/*.pt
models/*.onnx
.idea/
.vscode/
```

These are recommendations only; Phase 9 did not edit `.gitignore` or remove any
local data.

## Git snapshot state and safe first commit

Git is initialized on branch `main`, but `HEAD` does not exist: there are **no
commits**. Sixty-four paths are currently in the index, many have additional
working-tree edits, and all Phase 4-9 annotations/docs/reports/tests are still
untracked. This is not a clean or versioned release snapshot.

Do not use a blind broad add until `Microsoft/` and other local artifacts are
ignored. A safe review sequence is:

```powershell
git status --short --ignored
git diff --cached --name-only
git diff --name-only
git diff --cached --check
```

After reviewing/adding the recommended ignore rules, stage an explicit release
allowlist rather than unrelated root content:

```powershell
git add .gitignore LICENSE README.md config.yaml requirements.txt pytest.ini conftest.py
git add app src tests docs data/annotations reports/phase4 reports/phase5 reports/phase6
git status --short
git diff --cached --check
git diff --cached --stat
```

Review the entire staged file list and credential scan before making the first
commit. Phase 9 did not commit because the user did not authorize a commit.

## Privacy and secret audit

A filename and pattern-based scan inspected 104 readable project text files
without printing values. It found no credential-like filenames, private-key
headers, AWS access-key patterns, or quoted password/token/API-key assignments.
No database/model/log/key files were found outside excluded cache/data areas.

This is a practical pre-release check, not a formal secret-scanner guarantee.
Historical documentation and Phase 6 manifests contain the contributor name
and Windows/Anaconda paths used for reproduction. These are not credentials,
but they are environment-identifying metadata and should be reviewed before a
public distribution. Preserve the canonical frozen reports; if public privacy
policy requires redaction, publish a separately labelled redacted copy rather
than silently modifying the historical artifact.

## Known limitations

- Manual real-browser screenshots and restart capture remain pending.
- A new Streamlit session does not reconnect to a prior private namespace.
- Only colour and a constrained entity lexicon are implemented.
- Identity resolution covers explicit ordinal references, not general aliases
  or visual re-identification.
- Equal-time updates use insertion order.
- Reset clears SQLite rows but does not remove saved images.
- Dependency versions are unpinned; clean installation is unverified.
- Structured production logging and authentication are absent.
- Real-photo/pretrained CV validation and external replication were not run.
- The repository has no commit and therefore no release tag or immutable source
  revision.
