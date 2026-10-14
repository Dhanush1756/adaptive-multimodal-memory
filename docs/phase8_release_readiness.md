# Phase 8 - Final UI reliability and release readiness

Completed on October 14, 2026. This phase makes targeted Streamlit integration
fixes and adds release regressions. It does not change the memory engine,
evaluation rules, frozen annotations, or historical benchmark artifacts. No
dependency or model was installed or downloaded, and no configured user
database was opened, reset, copied, or migrated.

## Timeline issue investigation

The Phase 7 concern was confirmed before editing. With these stored entities:

```text
car_001 / first car  / red
car_002 / second car / blue
```

the UI iterated both entries but called `agent.timeline_for(e["entity"])` for
each. Both calls therefore became `timeline_for("car", entity_ref=None)`.
`resolve_entity_id` correctly refuses to choose between two stored car
identities and returned a new unused ID, so both UI lookups produced empty
histories. Direct calls with `entity_ref="first car"` and `"second car"`
returned the correct records. The defect was in the UI integration path, not
the memory engine.

`app/streamlit_app.py` now routes explicit identities through
`timeline_for(entity, entity_ref=...)`. Rows from older databases with an empty
`entity_ref` are loaded by their exact persisted `entity_id`, avoiding both an
invented identity and an accidental merge. The UI labels each timeline row
with its entity reference and provides an identity selector with an all-history
view. Single-entity behavior remains unchanged.

## Other confirmed UI defects and fixes

The audit traced ingestion, answering, evidence rendering, state timelines,
reset, and session construction against the backend answer/state contracts.
Three confirmed display gaps were fixed:

1. The backend answer status (`answered`, `uncertain`, or `abstained`) was not
   displayed. The answer caption now includes it, so conflicts and required
   abstentions are visible without inferring them from `found` alone.
2. Image evidence omitted its source session, source date, association status,
   and whether it supports the state. The UI now displays all four fields.
3. Identity-specific histories disappeared as described above.

No backend defect was found in text-only ingestion, current/original/previous/
as-of/history retrieval, state-specific evidence selection, required
abstention, persistence, reset isolation, unreadable-image fallback, or
transactional state updates. Those paths were retained.

## Files changed

| File | Reason |
|---|---|
| `app/streamlit_app.py` | Propagate identity references in Timeline loading; support legacy rows by exact ID; display answer status and complete image provenance. |
| `tests/test_phase8_streamlit_integration.py` | Add seven release-level integration regressions using temporary storage and Streamlit `AppTest`. |
| `README.md` | Point project status to the completed stabilization phase. |
| `docs/final_validation_checklist.md` | Record only confirmed Phase 8 automated results while preserving manual-pending status. |
| `docs/final_demo_script.md` | Replace the resolved Timeline warning with the current expected behavior. |
| `docs/research_synthesis.md` | Update the historical Phase 7 UI limitation with its Phase 8 outcome. |
| This document | Record investigation, validation, limitations, and release status. |

No file under `data/annotations/` or `reports/phase6/` was changed.

## Integration tests added

The new tests cover:

- red -> blue -> black through Streamlit, including links/statuses;
- current, previous, original, as-of, and full-history answers;
- evidence source session and timestamps;
- separate first-car and second-car Timeline rows and answers;
- Timeline selector filtering that excludes the unselected car history;
- ambiguous and unknown-entity abstention with visible status;
- a detector-free contextual image displayed as non-supporting provenance;
- a deterministic mocked detector conflict displayed as uncertain;
- a controlled CV-analysis failure that retains text memory and surfaces its note;
- file-backed reopen with two identities;
- additive migration from a temporary pre-`entity_ref` SQLite schema.

The contextual-image test uses Light mode. The conflict test injects a
deterministic detector result. Neither is evidence of pretrained CV accuracy.
Existing Phase 1-7 tests continue to cover transaction rollback, concurrency,
late event time, corrupt inputs, session reset/isolation, frozen evaluation,
and benchmark integrity.

## Commands and actual results

Focused Phase 8 integration file:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest tests\test_phase8_streamlit_integration.py -q --basetemp .pytest_cache\phase8-ui3
```

Actual result: **7 passed in 10.12 seconds**, no failures or skips.

Focused integration plus prior Streamlit/Phase 5 reliability checks:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest tests\test_phase8_streamlit_integration.py tests\test_reliability.py::test_streamlit_browser_sessions_are_isolated_and_persistent tests\test_phase5_reliability.py -q --basetemp .pytest_cache\phase8-focused2
```

Actual result at that point: **12 passed in 9.47 seconds**, no failures or
skips. Two additional Phase 8 UI cases were subsequently added and included in
the final focused/full runs.

Complete suite:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q --basetemp .pytest_cache\phase8-full2
```

Actual result: **176 passed in 28.31 seconds**, no failures or skips.

## Manual validation status

Streamlit `AppTest` executed the UI script and user-facing widgets against
temporary SQLite and image directories. It is automated application testing,
not a manual browser session. A person has not yet launched the server,
captured screenshots, uploaded a real file through the browser, or performed a
stop/start screen recording. Follow `docs/final_demo_script.md` for those exact
steps. Do not mark them complete from this automated run.

The file-backed reopen test passed. On a real Streamlit server restart, the old
private SQLite file should remain, while a new session receives a new namespace;
automatic session restoration is still not implemented.

## Launch instructions

From the repository root, using the already-provisioned environment:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Keep **Light mode (no model downloads)** enabled for the validated demo. Each
browser session receives a private database below
`data/processed/memory_sessions/<namespace>/memory.db` and a private image
directory. The unscoped configured database is not opened by the UI.

## Release-readiness audit

- **Dependencies/configuration:** `requirements.txt` lists core, demo, and
  optional model packages; versions are not pinned. `config.yaml` contains
  initial thresholds and relative storage paths. Light mode avoids model
  initialization/downloads.
- **SQLite migration:** a temporary old schema without `entity_ref` migrated
  additively and retained its state/evidence. A genuine user database was not
  used. Legacy visual JSON and normal reopen remain covered.
- **Errors:** unreadable/CV-failed images retain usable text and expose an
  uncertainty note. Optional LLM failures fall back to templates. Logging is
  console/UI oriented rather than structured production logging.
- **Data safety:** benchmark agents use `:memory:`; tests use temporary paths;
  Streamlit namespaces storage per browser session. Reset clears database rows
  but intentionally does not delete saved images.
- **Session isolation:** independent agents and Streamlit sessions, mode
  changes, reruns, and reset isolation are automated regressions.
- **Repository state:** this checkout has no available Git commit and contains
  many pre-existing staged/untracked Phase 1-7 files. A clean, versioned release
  snapshot is still needed before submission.

## Benchmark integrity

The Phase 6 benchmark was not rerun and no score change is claimed. Frozen
hashes remain:

| File | SHA-256 |
|---|---|
| `phase4_test.jsonl` | `5796204c446fc69a4d126d08c77a6de436fc281c3737fb72336facf4c99654bd` |
| `phase5_test.jsonl` | `b911d6b9993dee49b995c324eb29d53dc37bbd7e5a9b880da0f7484b54f5e019` |
| `phase6_dev.jsonl` | `a05c713fad1d8c06159c1b6a53502ea8748ac1e76ebb3ce39225aaa91c2e02bc` |
| `phase6_test.jsonl` | `831449bb23989915803bf715071a656bf663c6c335320890b8340edfa9fadaf7` |

Phase 6 remains the historical controlled Track A result.

## Known limitations and blockers

- Real-browser screenshot/demo capture remains pending.
- Automatic reconnection to an earlier Streamlit namespace after server restart
  is not implemented.
- Only colour and a constrained entity lexicon are supported; one claim is
  processed per ingestion.
- Identity resolution supports explicit ordinal references, not names, aliases,
  ownership, or visual re-identification.
- Equal-time updates use insertion order.
- Reset leaves image files on disk; retention cleanup remains a future policy.
- Dependency versions are not locked and the repository lacks a clean commit.
- A genuine copied pre-Phase-5 database migration has not been performed.
- Structured production logging and authentication are not implemented.

## Real pretrained CV status

Track B remains **not performed**. The Phase 6 read-only audit found PyTorch and
Ultralytics, but no local configured YOLO weights, no `transformers` package,
and no configured CLIP cache. No model was initialized or downloaded in this
phase. Mocked detections, rendered images, and HSV fallback behavior must not be
presented as pretrained or real-photo performance.

Before final submission, the required remaining actions are a real-browser
walkthrough with captured evidence, creation of a clean versioned release
snapshot, and an explicit decision whether the assessment requires a separately
approved real-photo/pretrained CV protocol. Phase 8 stops here.
