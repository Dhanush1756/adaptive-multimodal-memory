# Phase 9 - Release packaging and submission readiness

Reviewed on October 14, 2026. Phase 9 changed documentation only. It did not
modify application behavior, frozen annotations, benchmark artifacts, user
data, dependencies, or model assets, and it did not create a Git commit.

## Status summary

| Item | Status | Evidence / boundary |
|---|---|---|
| Complete automated suite | **Verified automatically** | 176 passed in 28.29 seconds; 0 failed; 0 skipped. |
| Streamlit integration | **Verified automatically** | Existing `AppTest` covers temporal QA, identity filtering, provenance, conflict/abstention display, CV failure, reset, and session isolation. |
| Frozen Phase 4-6 hashes | **Verified automatically** | Values below match Phase 6/8 records. |
| Phase 6 result preservation | **Verified automatically** | All JSON files parse; reference remains 8 systems, 265 queries and 210 sessions per system. Benchmark was not rerun. |
| Documentation paths | **Verified automatically** | Release documentation reference audit passed. |
| Pattern-based secret check | **Verified automatically** | 104 readable text files scanned; no credential-like match. Historical paths remain environment metadata. |
| Interactive browser walkthrough | **Pending manual verification** | No browser or screenshot capture was available in this environment. |
| Manual upload/restart evidence | **Pending manual verification** | Exact procedure below. |
| Clean Git release commit/tag | **Not performed** | Git exists on `main`, but there are no commits and the worktree/index are not clean. |
| Genuine legacy user-DB migration | **Not performed** | Synthetic legacy-schema migration is tested; no user database was opened or copied. |
| Real pretrained CV / real photos | **Blocked by missing dependencies or model assets** | Configured weights/CLIP cache absent; `transformers` absent. No download authorized. |

## Repository and packaging findings

Git is initialized, but `git rev-parse --verify HEAD` fails because branch
`main` has no commit. The index contains 64 paths from the initial project,
many of those paths also have later modifications, and Phase 4-9 material is
untracked. A commit was not authorized and was not made.

The root `Microsoft/` directory contains only
`Microsoft/Windows/PowerShell/ModuleAnalysisCache` (8,246 bytes). It is local
PowerShell analysis state, not project source. It remains untouched and should
be ignored/excluded from the release.

The current ignore rules correctly exclude Python/pytest caches, `.env`, local
SQLite databases, generated/raw/processed data, scratch results, and local
joblib models. `docs/release_manifest.md` lists additional recommended rules
for virtual environments, coverage/build/log/editor files, model weights, and
`Microsoft/`. No files were deleted.

## Phase 9 verification

Full suite command:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q --basetemp .pytest_cache\phase9-full
```

Actual result:

```text
176 passed in 28.29s
```

There were no failures or skips. `git diff --check` completed with no whitespace
errors; Git printed existing LF-to-CRLF working-copy warnings on Windows.

Frozen hashes:

| File | SHA-256 |
|---|---|
| `data/annotations/phase4_test.jsonl` | `5796204c446fc69a4d126d08c77a6de436fc281c3737fb72336facf4c99654bd` |
| `data/annotations/phase5_test.jsonl` | `b911d6b9993dee49b995c324eb29d53dc37bbd7e5a9b880da0f7484b54f5e019` |
| `data/annotations/phase6_dev.jsonl` | `a05c713fad1d8c06159c1b6a53502ea8748ac1e76ebb3ce39225aaa91c2e02bc` |
| `data/annotations/phase6_test.jsonl` | `831449bb23989915803bf715071a656bf663c6c335320890b8340edfa9fadaf7` |

No configured user database was accessed, reset, copied, or overwritten.

## Manual browser demonstration checklist

Use disposable browser-session data and keep Light mode enabled. Create a
folder outside the release package for screenshots and terminal logs.

### 1. Start the application

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

- **Expected:** application opens with Light mode enabled and an empty Timeline.
- **Capture:** terminal startup log plus one screenshot showing model status,
  empty memory statistics, and Light mode.

### 2. Verify red -> blue -> black

In a fresh session store:

1. `My car is red.` on 2026-10-01: expect `ADD`.
2. `I repainted my car blue.` on 2026-10-10: expect `UPDATE`.
3. `I painted my car black.` on 2026-10-20: expect `UPDATE`.

- **Expected:** ordered Timeline red (`HISTORICAL`) -> blue (`HISTORICAL`) ->
  black (`CURRENT`), with original dates and consecutive previous-memory IDs.
- **Capture:** each action result and one full Timeline screenshot.

Ask:

| Question | Expected |
|---|---|
| `What color is my car now?` | black; status `answered` |
| `What color was my car before?` | blue; status `answered` |
| `What color was my car originally?` | red; status `answered` |
| `What color was my car on 2026-10-15?` | blue; status `answered` |
| `Show me the history of my car's color.` | red, blue, black |

- **Capture:** the five answer/status views and one expanded grounded prompt.

### 3. Verify identity separation and Timeline filtering

Reset the disposable session. Store `My first car is red.` on October 1 and
`My second car is blue.` on October 2.

- **Expected:** all-identities view shows `car_001 / first car / red` and
  `car_002 / second car / blue`. Selecting each Timeline identity hides the
  other. Explicit questions return red and blue respectively. `What colour is
  my car?` abstains and asks for an identity.
- **Capture:** all-identities, first-only, second-only, both explicit answers,
  and the ambiguous abstention/status.

### 4. Verify evidence and unrelated-image handling

Use an existing disposable red laptop image; do not download one. In a fresh
session upload it with `My car is blue.` dated October 5. Ask `How do you know
my car is blue?`

- **Expected:** blue is established by text. In Light mode the image is
  `contextual, non-supporting`, retains source session/date, and does not create
  a conflict. Uploading that image without text after a reset produces `IGNORE`
  and no state.
- **Capture:** ingestion JSON, answer/evidence line showing date and association
  status, Timeline, and image-only `IGNORE` result.

### 5. Verify uncertainty and abstention

Before any car observation, ask `What color was my car on 2026-09-01?`; repeat
after the first state dated October 1.

- **Expected:** both are `abstained` with no invented value. Real verified
  conflict uncertainty cannot be claimed in Light mode; retain the Phase 8
  controlled mocked-test evidence separately.
- **Capture:** both abstention captions and explanations. Label any automated
  conflict output as controlled/mock evidence.

### 6. Verify CV/unreadable-file failure

Create a disposable text file named `invalid.png`, enter `My phone is green.`,
and upload that file.

- **Expected:** the UI reports that the image could not be read, still stores
  the text claim, and answers the phone as green. No image supports the state.
- **Capture:** upload warning, `ADD` result, green answer, and Timeline row.

### 7. Verify session isolation and reset

Open an incognito/private window to the same server. Store a different value
there, reset the original window, and query both.

- **Expected:** private databases differ; reset affects only the original
  browser session.
- **Capture:** both session states before reset and the unaffected second
  session afterward.

### 8. Verify persistence boundary after restart

Record the current disposable session database path from
`data/processed/memory_sessions/<namespace>/memory.db`, its size, and modified
time. Stop Streamlit, verify the file remains, then restart the application.

- **Expected:** the old SQLite file persists. The restarted/new browser session
  is empty because automatic namespace restoration is not implemented. This is
  the documented persistence boundary, not a failed database write.
- **Capture:** file metadata before and after shutdown, terminal restart log,
  and the new empty UI.

Mark every step pass, fail, or not performed. Phase 9 leaves all eight steps
pending because no interactive browser capture was available.

## Assessment release scopes

### A. Prototype release — currently supported

Supported by actual evidence:

- deterministic Track A frozen evaluation and raw reports;
- 176 automated component/regression/Streamlit integration tests;
- temporary/in-memory SQLite safety, migration, rollback, concurrency, reopen,
  reset, and session isolation;
- Light-mode rendered-image/contextual provenance handling;
- current, historical, identity-aware, evidence-grounded QA;
- exact manual browser procedure.

Pending within this scope: the real-browser screenshots, upload interaction,
and restart capture. These are submission-evidence tasks rather than missing
backend implementation.

### B. Real-model research release — not currently supported

This scope needs separately approved dependency/model setup, locally controlled
weights, licensed real photographs, independent labels, fixed acceptance
metrics, and a new report. It is blocked in the current environment by missing
configured YOLO/CLIP assets and `transformers`. Phase 9 makes no pretrained CV,
real-photo generalization, or new benchmark claim.

## Remaining release blockers

1. Perform and capture the manual browser checklist.
2. Add/review appropriate ignore rules, then review and create the first Git
   commit; no commit or tag currently identifies this source snapshot.
3. Review environment-identifying Windows paths in historical documentation
   and manifests before public distribution. They contain no credential found
   by the scan, but expose contributor/environment metadata.
4. Decide whether the assessment accepts prototype scope A or explicitly
   requires scope B. Scope B needs a separate approved protocol.
5. If claiming clean installation, create a fresh isolated environment and
   record dependency resolution; that validation has not been performed.

No release-blocking application code defect was found during Phase 9. Phase 9
stops here.
