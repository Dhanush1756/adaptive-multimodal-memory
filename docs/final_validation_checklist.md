# Final validation checklist

**Phase 8 update (October 14, 2026):** the identity-aware Timeline defect was
confirmed and fixed, seven Streamlit/reopen/migration integration tests were
added, and the complete suite passed **176 tests in 28.31 seconds**. Historical
Phase 1-7 status statements below are retained where they explain what had been
run at that time. Real-browser capture remains pending.

This checklist closes the existing Phase 1-5 scope. It does not add features,
change architecture, install packages, download models, or use configured user
data. Run commands from the repository root.

Status terms:

- **Already verified** means an automated test or recorded evaluation has run.
- **Manual capture pending** means the behavior has automated coverage, but a
  browser-level demonstration has not been recorded.
- **Not yet performed** means the specific validation action has not been run.

Use the existing interpreter where available:

```powershell
$python = 'C:\Users\DHANUSH S\anaconda3\python.exe'
```

## 0. Preflight and evidence folder

**Status:** Phase 5 completed with 165 passing tests; Phase 8 now completes with
176 passing tests. The following real-browser capture session has not yet been
performed.

**Command:**

```powershell
New-Item -ItemType Directory -Force .pytest_cache\final_validation | Out-Null
& $python --version 2>&1 | Tee-Object .pytest_cache\final_validation\python-version.txt
& $python -c "import streamlit; print('streamlit', streamlit.__version__)" 2>&1 | Tee-Object .pytest_cache\final_validation\streamlit-version.txt
git status --short | Tee-Object .pytest_cache\final_validation\git-status-before.txt
```

**Expected behavior:** The existing Python and Streamlit imports succeed. Do
not run `pip install`. The Git status is a provenance snapshot, not a request to
clean or reset the working tree.

**Capture:** The three text files above, the validation date/time, OS, and the
Git commit ID if one exists (`git rev-parse HEAD`).

## 1. Manual Streamlit end-to-end test

**Status:** **Manual capture pending.** Phase 1 already verified two isolated
Streamlit sessions through `AppTest`, including reruns, mode switching, and
reset isolation. A real browser session has not been recorded.

**Command:**

```powershell
& $python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

**Manual action:**

1. Open the displayed local URL in a new browser session.
2. Confirm **Light mode (no model downloads)** is enabled.
3. Store `My phone is green.` with date October 1, 2026.
4. Ask `What color is my phone now?`
5. Expand the grounded prompt and inspect the Timeline panel.
6. Refresh the page once and ask the question again.
7. Open an incognito/private window to the same URL and ask the same question.
8. In the first window, press **Reset memory**. Verify the incognito session is
   still unaffected.

**Expected behavior:** The first window answers green before reset and retains
it across an ordinary Streamlit rerun/refresh. The incognito session starts
empty. Reset affects only the first browser session. The UI shows an `ADD`
decision, a current state, source date, memory ID, and grounded evidence.

**Capture:** Screenshots of the `ADD` result, answer/evidence, timeline, empty
incognito session, and post-reset isolation. Save the terminal startup log.

## 2. Red -> blue -> black temporal-state verification

**Status:** **Already verified automatically, including the Streamlit path;
manual capture pending.** Covered by memory, retrieval, persistence,
end-to-end, Phase 5 evaluation, and Phase 8 Streamlit integration tests.

**Manual action:** In a freshly reset browser session, store:

| Date | Text | Expected decision |
|---|---|---|
| 2026-10-01 | `My car is red.` | `ADD` |
| 2026-10-10 | `I repainted my car blue.` | `UPDATE` |
| 2026-10-20 | `I painted my car black.` | `UPDATE` |

Then ask:

| Question | Expected answer |
|---|---|
| `What color is my car now?` | black |
| `What color was my car immediately before this?` | blue |
| `What color did my car start with?` | red |
| `What color was my car on 2026-10-15?` | blue |
| `Show me the history of my car's color.` | red, blue, black |

**Expected behavior:** The timeline is ordered red -> blue -> black. Red and
blue are `HISTORICAL`; black is `CURRENT`. Each state has its original event
timestamp. `previous_memory_id` links blue to red and black to blue.

**Automated command for focused confirmation:**

```powershell
& $python -m pytest tests/test_end_to_end.py::test_three_states_and_before_anchor tests/test_reliability.py::test_late_historical_evidence_does_not_replace_newest_state -q --basetemp .pytest_cache/final_validation/temporal
```

**Capture:** One screenshot containing the complete timeline, screenshots or a
screen recording of all five answers, and the focused pytest log. Do not use an
existing user database for this demonstration.

## 3. Persistence across application restart

**Status:** **File-backed reopen is already verified automatically. A manual
server-stop/start capture is not yet performed.** The current Streamlit app
creates a new private namespace for a new browser/server session and has no
session-resume UI. Therefore an application restart is expected to preserve the
old SQLite file on disk but not automatically reconnect the new UI to it.

**Focused regression command:**

```powershell
& $python -m pytest tests/test_reliability.py::test_file_database_reopens_with_states_links_and_evidence tests/test_reliability.py::test_merged_session_ids_are_not_reused_after_reopen -q --basetemp .pytest_cache/final_validation/reopen
```

**Independent two-process action:** These commands use only scratch storage.

```powershell
$env:FINAL_VALIDATION_DB = (Join-Path (Resolve-Path .) '.pytest_cache\final_validation\persistence.db')
Remove-Item -LiteralPath $env:FINAL_VALIDATION_DB -ErrorAction SilentlyContinue
& $python -c "import os; from src.agent.reasoning import MemoryAgent; a=MemoryAgent(db_path=os.environ['FINAL_VALIDATION_DB'], light=True); a.remember('My car is red.',timestamp='2026-10-01',session_id='r'); a.remember('My car is blue.',timestamp='2026-10-10',session_id='b'); print(a.store.db_path, [x.value for x in a.timeline_for('car')]); a.store.close()" | Tee-Object .pytest_cache\final_validation\persistence-write.txt
& $python -c "import os; from src.agent.reasoning import MemoryAgent; a=MemoryAgent(db_path=os.environ['FINAL_VALIDATION_DB'], light=True); print(a.ask('What color is my car now?').value, a.ask('What color was my car originally?').value, [x.value for x in a.timeline_for('car')]); a.store.close()" | Tee-Object .pytest_cache\final_validation\persistence-reopen.txt
```

**Manual Streamlit restart action:** Record a state, note the newly created
`data/processed/memory_sessions/<namespace>/memory.db`, stop Streamlit with
Ctrl+C, confirm that file still exists, and launch Streamlit again. Use a
disposable validation namespace and do not open or delete any existing user
database.

**Expected behavior:** The two-process check prints current blue, original red,
and `['red', 'blue']` after reopen. The old Streamlit database file remains
after shutdown. The restarted UI starts a new empty namespace; automatic UI
reconnection is outside the Phase 5 implementation.

**Capture:** Both command outputs, the focused pytest log, and before/after file
path, size, and modified time. Record the new empty UI as an expected limitation,
not a persistence failure.

## 4. Multiple-entity identity isolation

**Status:** **Already verified through the agent API and Streamlit `AppTest`;
real-browser capture pending.** Phase 5 scored 3/3 identity questions,
including correct abstention. Phase 8 also verifies that the Timeline passes
each `entity_ref`, renders both histories separately, and filters them through
the Timeline identity selector.

**Manual action:** In a fresh session, store:

1. `My first car is red.` on October 1, 2026.
2. `My second car is blue.` on October 2, 2026.

Ask:

1. `What colour is my first car?` -> red.
2. `What colour is my second car?` -> blue.
3. `What colour is my car?` -> abstained/asks which identity is meant.

**Focused command:**

```powershell
& $python -m pytest tests/test_phase5_reliability.py::test_two_explicit_car_identities_remain_separate -q --basetemp .pytest_cache/final_validation/identity
```

**Expected behavior:** The explicit references resolve different `entity_id`
values and histories. The category-only query does not select either car. Do
not infer identity from colour or an image. The current implementation supports
explicit ordinal references only; general names and visual re-identification
remain out of scope.

**Capture:** All three answers, their `status` values, the two entity IDs from
the stored records, and the focused test log. Also capture the Streamlit
Timeline panel. If the panel does not render both identities separately, record
that as a regression; do not change code or data during final validation.

## 5. Visual provenance and unrelated-image rejection

**Status:** **Already verified in automated light-mode, Streamlit, and
detector-mocked tests; manual upload capture pending.** Phase 8 displays image
source session/date plus association and supporting status. Real pretrained
detection has not run.

**Manual action:**

1. Keep Light mode enabled.
2. Upload an unrelated red laptop image with `My car is blue.` and date October
   5, 2026.
3. Inspect the ingestion JSON and ask `What color is my car now?`
4. Ask `Which evidence supports the established car colour?`
5. In a fresh reset, upload the unrelated image without text.

**Expected behavior:** With text, the decision is `ADD` or `UPDATE` based on the
existing car history and the established value is blue. The UI ingestion JSON
shows `association_status: contextual` and its reason. The stored visual record
also retains its image/session ID and source timestamp with `supports_state`
false. It cannot create a conflict or appear in `supporting_evidence_ids`.
Those latter fields are verified by the focused API tests because the current
UI does not display the complete `Answer.to_dict()` payload. Without text, the
contextual image is `IGNORE` and creates no state. An `unmatched` or `ambiguous`
detector result likewise cannot support or contradict a state.

**Focused command:**

```powershell
& $python -m pytest tests/test_phase5_reliability.py::test_contextual_laptop_image_cannot_contradict_car_text tests/test_phase5_reliability.py::test_multiple_contextual_images_never_establish_or_change_state tests/test_multimodal_evidence.py -q --basetemp .pytest_cache/final_validation/visual
```

**Capture:** The uploaded source image, ingestion JSON showing status/reason and
timestamp, memory decision, answer payload with supporting IDs, and focused
pytest log. Label detector-mocked tests as unit/integration evidence rather than
real pretrained inference.

## 6. Existing SQLite migration and regression checks

**Status:** **General reopen, legacy visual JSON, transactions, concurrency,
rollback, and migration from a synthetic pre-`entity_ref` schema are verified.**
Migration of a copied genuine pre-Phase-5 user database remains not performed.

**Full regression command:**

```powershell
& $python -m pytest -q --basetemp .pytest_cache/final_validation/full 2>&1 | Tee-Object .pytest_cache\final_validation\pytest-full.txt
```

**Expected result:** `176 passed`, with no failures or skips. A different timing
is normal. All test databases and images remain under pytest temporary storage
or use `:memory:`.

**Migration action:** Work on a copy of a pre-Phase-5 database only:

```powershell
Copy-Item -LiteralPath '<path-to-legacy-memory.db>' -Destination '.pytest_cache\final_validation\legacy-copy.db'
$env:FINAL_LEGACY_COPY = (Join-Path (Resolve-Path .) '.pytest_cache\final_validation\legacy-copy.db')
& $python -c "import os; from src.memory.store import MemoryStore; s=MemoryStore(os.environ['FINAL_LEGACY_COPY']); print([r[1] for r in s.conn.execute('PRAGMA table_info(memory)')]); print([(r.entity_id,r.entity_ref,r.value) for r in s.all()]); s.close()" | Tee-Object .pytest_cache\final_validation\migration.txt
```

The Phase 8 synthetic legacy-schema regression verifies the additive migration.
If no genuine legacy database is available, mark the genuine-copy check **not
performed**; do not manufacture a pass and do not point it at configured user data.

**Expected behavior:** Opening the copy adds `entity_ref` without deleting or
rewriting existing states/evidence. Existing rows read with an empty
`entity_ref`; current, historical, and legacy visual evidence remain readable.

**Capture:** SHA-256 of the source and copy before opening, the copied file's
post-migration hash, `PRAGMA table_info(memory)`, record count and redacted
state summary, pytest output, and any migration exception. Never capture secret
or private evidence text from a real user database.

## 7. Decision on real pretrained CV inference

**Decision:** **Not required to close the Phase 5 light-mode prototype
validation. Required before claiming real-photo performance, detector-verified
association precision, or pretrained YOLO/CLIP conflict performance.**

**Status:** Phase 4 found `torch` and `ultralytics` installed, no local YOLO
weights, no `transformers`, and no local CLIP cache. Pretrained inference and
real-photo testing were not performed. No model should be initialized if that
could trigger a download.

**Read-only availability check:**

```powershell
& $python -c "import importlib.util, pathlib; print({m:bool(importlib.util.find_spec(m)) for m in ('torch','ultralytics','transformers')}); print('local_yolo_weights', [str(p) for p in pathlib.Path('.').rglob('*.pt')]); print('local_clip_cache', pathlib.Path.home().joinpath('.cache','huggingface','hub').exists())" | Tee-Object .pytest_cache\final_validation\cv-availability.txt
```

**Expected behavior:** The command only reports availability. It must not load a
model or access the network. If weights/dependencies remain unavailable, retain
the existing report language: light HSV and rendered-image integration were
validated; real pretrained CV was not.

**Evidence to capture:** Availability output and the exact claim boundary used
in the final report. If the project assessment explicitly requires real-image
CV metrics, stop and create a separately approved protocol covering model
assets, licensed images, labels, and acceptance thresholds; do not download
anything as part of this checklist.

## 8. Reproducible frozen evaluation and existing baselines

**Status:** **Already performed.** The Phase 5 matrix completed for eight
systems. The existing artifacts are under `reports/phase5/`. Reproduction into
a separate output directory remains optional final evidence capture.

**Verify frozen inputs before running:**

```powershell
Get-FileHash data\annotations\phase4_test.jsonl,data\annotations\phase5_dev.jsonl,data\annotations\phase5_test.jsonl -Algorithm SHA256 | Format-Table Path,Hash -AutoSize
```

Expected SHA-256 values:

| File | SHA-256 |
|---|---|
| `phase4_test.jsonl` | `5796204c446fc69a4d126d08c77a6de436fc281c3737fb72336facf4c99654bd` |
| `phase5_dev.jsonl` | `9e488655eb1a0ecd7c6f429abead042e1cbacbaeafa412bc94f0f4e5a57b1462` |
| `phase5_test.jsonl` | `b911d6b9993dee49b995c324eb29d53dc37bbd7e5a9b880da0f7484b54f5e019` |

Do not edit either frozen test file. The Phase 4 set is a historical,
already-inspected benchmark. The Phase 5 test set is the final fixed set.

**Reproduction command:**

```powershell
& $python -B -m src.evaluation.ablations --data data/annotations/phase5_test.jsonl --split all --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/final_validation/phase5 2>&1 | Tee-Object .pytest_cache\final_validation\phase5-evaluation.txt
```

**Expected complete-system results:**

| Metric | Expected |
|---|---:|
| Overall query accuracy | 14/14 |
| Current state | 4/4 |
| Historical state | 3/3 |
| Initial state | 2/2 |
| Entity identity | 3/3 |
| Evidence precision / recall | 0.958 / 1.000 over 12 labelled questions |
| Unsupported answers | 0/12 answered questions |
| Lifecycle accuracy | 13/13 |
| Answer-schema validity | 14/14 |
| False visual associations | 0/2 rejected images |
| Visual association precision | n/a: no verified predictions in light mode |
| Conflict F1 | n/a: no positive detector-verified conflicts in this set |

**Historical comparison command:**

```powershell
& $python -B -m src.evaluation.ablations --data data/annotations/phase4_test.jsonl --split all --light --systems N_no_memory L_latest_value B_naive_multimodal C_append_only_temporal E_no_provenance E_no_visual_linking E_no_text_image_conflict E_proposed --out reports/final_validation/phase4_historical 2>&1 | Tee-Object .pytest_cache\final_validation\phase4-historical.txt
```

**Expected behavior:** Both commands use in-memory agents and do not open the
configured database. Preserve all system rows, raw per-question/session results,
metadata, console logs, and generated Markdown tables. The Phase 4 result must
remain labelled historical: two labels encode assumptions superseded by Phase
5, so its current/conflict scores are not an untouched final-test claim.

**Capture:** Input hashes, command line, console logs,
`ablation_results.json`, `ablation_table.md`, interpreter/component status, and
Git commit/status. Compare generated JSON metrics with the expected table; do
not silently overwrite the Phase 5 recorded artifacts.

## Final acceptance record

Mark final validation complete only when:

- the full regression suite passes with its exact count recorded;
- the browser captures confirm the temporal, isolation, identity, and unrelated
  image scenarios;
- file-backed reopen succeeds and the Streamlit restart limitation is stated;
- a copied legacy database migration succeeds, or its absence is explicitly
  recorded as not performed;
- frozen input hashes match before evaluation;
- the complete baseline matrix finishes without session errors;
- light-mode and real-pretrained-CV claims remain clearly separated.

Record failures as failures. Do not change code, annotations, or thresholds
during this final validation run; any defect found should be logged separately
for review.
