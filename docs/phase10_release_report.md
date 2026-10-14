# Phase 10 - Proposed first commit and manual demonstration status

Prepared on October 14, 2026. This phase stops before staging, committing,
tagging, pushing, or publishing. The existing index was inspected and left
unchanged. Application code, frozen annotations, benchmark artifacts, and user
data were not modified.

## Git preflight

Git is initialized on branch `main`, but `HEAD` does not exist and there are no
commits or tags. The required preflight commands were run before any index
operation:

```powershell
git status --short
git diff --cached --stat
git diff --stat
git ls-files --others --exclude-standard
git status --ignored --short
```

Findings:

- The index contains 64 initially added paths (5,451 inserted lines).
- Twenty-seven of those indexed files also have newer unstaged changes: 988
  insertions and 154 deletions relative to their staged versions.
- Phase 4-10 annotations, documentation, reports, evaluation reporting code,
  and regression tests are untracked.
- Committing the current index would omit later fixes and most research
  evidence. It is therefore not the proposed commit.
- Ignored content includes pytest/Python caches and generated synthetic data.
  Some old pytest directories are inaccessible to Git status, but the parent
  `.pytest_cache/` is ignored and none belongs in the release.

No reset, clean, restore, checkout, deletion, or index change was performed.

## Protective exclusions

The root `Microsoft/Windows/PowerShell/ModuleAnalysisCache` is an 8,246-byte
local PowerShell cache unrelated to the project. It was inspected, not opened
as project data, and not deleted. `.gitignore` now excludes `Microsoft/` along
with common virtual environments, logs, coverage/build/editor output, Streamlit
secrets, environment variants, SQLite variants, and model-weight formats. This
working-tree change has not been staged.

Existing exclusions for Python/pytest caches, `.env`, generated/raw/processed
data, scratch results, joblib models, and `*.db` remain in place.

## Proposed first-commit manifest

The proposed commit is an explicit allowlist of final working-tree versions.
It includes:

| Group | Proposed paths | Reason |
|---|---|---|
| Root metadata | `.gitignore`, `LICENSE`, `README.md`, `config.yaml`, `requirements.txt`, `pytest.ini`, `conftest.py` | License, entry point, configuration, dependency names, and test setup. |
| Application | `app/streamlit_app.py` | Final Light-mode Streamlit UI with identity filtering and provenance display. |
| Implementation | all source files under `src/` | Integrated NLP, CV, multimodal evidence, memory, retrieval, evaluation, data, and training modules. |
| Tests | all `tests/test_*.py` | Complete 176-test regression and Streamlit integration suite. |
| Fixed data | all files under `data/annotations/` | Intent paraphrases and frozen Phase 4-6 development/test annotations. |
| Research evidence | `reports/phase4/`, `reports/phase5/`, `reports/phase6/` | Historical raw results, tables, manifests, paired comparisons, model audit, and error analysis. |
| Documentation | all Markdown files under `docs/` | Phase records, methodology, synthesis, demo/validation procedures, presentation outline, and release reports through Phase 10. |

The intended staging command after explicit approval is:

```powershell
git add .gitignore LICENSE README.md config.yaml requirements.txt pytest.ini conftest.py
git add app src tests docs data/annotations reports/phase4 reports/phase5 reports/phase6
```

This command updates the already-indexed files to their final working-tree
versions and adds the reviewed untracked release files. It does not include the
root `Microsoft/` directory or ignored local artifacts.

Before any commit, the staged result must be reviewed with:

```powershell
git status --short
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

The proposed initial commit message is:

```text
Release adaptive evidence-grounded memory prototype
```

No commit will be created without explicit approval of this manifest and its
contents.

## Explicit exclusions

The proposed commit excludes:

- `Microsoft/` and PowerShell analysis cache;
- `.git/`, `.pytest_cache/`, `__pycache__/`, and bytecode;
- `.env*` except an intentional `.env.example`, and Streamlit secrets;
- `data/processed/`, `data/raw/`, generated `data/synthetic/`, uploaded images,
  and all user/session databases;
- downloaded/trained model weights and local model caches;
- logs, coverage reports, build/distribution output, virtual environments, and
  IDE settings;
- `reports/results/` and any future reproduction scratch directory unless it
  is separately reviewed.

No excluded file was deleted or overwritten.

## Contributor and path review

The MIT license and README intentionally contain contributor names. Historical
phase documents and the frozen Phase 6 manifest/results also contain the
Windows/Anaconda paths used during execution, including the local username.
These are not credentials, and a pattern scan found no private keys, AWS access
keys, or quoted password/token/API-key assignments. They remain environment-
identifying metadata.

The original research artifacts were preserved exactly. If a public release
requires path redaction, create separately labelled redacted distribution
copies and retain the canonical originals; do not silently rewrite the frozen
manifest or raw results.

## Demonstration status

This environment does not provide an interactive browser/screenshot channel.
The Phase 8 Streamlit `AppTest` suite remains automated evidence, not a manual
walkthrough. Phase 10 performed only a local server startup/health smoke check:
the headless server started on `127.0.0.1:8767`, returned HTTP 200 with body
`ok` from `/_stcore/health`, and was stopped afterward. No Phase 10 test server
remained listening. This confirms startup, not browser behavior.

The following browser checks remain **pending manual verification**:

1. Red -> blue -> black ingestion and ordered Timeline.
2. Current black, previous blue, original red, October 15 blue, and complete
   red/blue/black history answers.
3. First-car/second-car separation and all/first/second Timeline filtering.
4. Evidence source timestamp, session, association, and supporting status.
5. Unrelated contextual image rejection and image-only `IGNORE`.
6. Required abstention before the first state and for an ambiguous car identity.
7. Unreadable-image warning while preserving a valid text claim.
8. File persistence after server stop and the documented new-session namespace
   behavior after restart.

For exact inputs, expected outputs, and screenshot/log requirements, follow
`docs/final_demo_script.md`, `docs/final_validation_checklist.md`, and the
condensed checklist in `docs/phase9_release_report.md`. Do not mark these items
passed until a person captures the actual browser results.

## Verification status

Phase 10 verification records:

- Full test suite: **176 passed in 31.01 seconds; 0 failed; 0 skipped**.
- `git diff --check`: **passed with no whitespace errors**; Git emitted only
  existing LF-to-CRLF working-copy warnings on Windows.
- Frozen Phase 4-6 hashes: verified unchanged in the final audit.
- Phase 6 artifact structure: verified as eight systems with 265 questions and
  210 sessions per system; the benchmark was not rerun.
- Streamlit startup/health smoke check: **HTTP 200 / `ok`**; this is not the
  browser demonstration.

## Remaining blockers

1. User approval of the proposed manifest and commit contents.
2. Staging and reviewing final working-tree versions after approval.
3. Manual browser execution with screenshots and logs.
4. Creation of the first commit after a successful staged review and explicit
   commit authorization.
5. Optional public-release decision about environment-path metadata.
6. A separate approved Track B protocol only if the assessment requires
   pretrained CV/real-photo evidence.

Phase 10 stops before staging or committing.
