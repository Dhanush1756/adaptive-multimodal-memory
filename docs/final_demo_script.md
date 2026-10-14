# Final demonstration script

This walkthrough uses disposable test data and Light mode. It defines expected behavior; the browser steps are **pending manual execution** until a person launches the application and captures the outputs.

## 1. Preflight and launch

From the repository root:

```powershell
$python = 'C:\Users\DHANUSH S\anaconda3\python.exe'
New-Item -ItemType Directory -Force .pytest_cache\phase7-demo | Out-Null
& $python --version 2>&1 | Tee-Object .pytest_cache\phase7-demo\python-version.txt
& $python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1 2>&1 | Tee-Object .pytest_cache\phase7-demo\streamlit.log
```

Open the printed local URL in a fresh browser session and leave **Light mode (no model downloads)** enabled. Do not reuse or open an existing user database. Capture the terminal log, application title, Light-mode setting, and sidebar component status.

## 2. Red to blue to black

Use a fresh browser session. Store these observations in order:

| Step | Date | Input | Expected action | Evidence to capture |
|---|---|---|---|---|
| 1 | 2026-10-01 | `My car is red.` | `ADD` | Action, session ID, red current state, source date |
| 2 | 2026-10-10 | `I repainted my car blue.` | `UPDATE` | Action, red historical, blue current, link to red |
| 3 | 2026-10-20 | `I painted my car black.` | `UPDATE` | Complete ordered timeline and all memory IDs/links |

Ask and capture each result:

| Question | Expected value |
|---|---|
| `What color is my car now?` | black |
| `What color was my car before?` | blue |
| `What color was my car originally?` | red |
| `What color was my car on 2026-10-15?` | blue |
| `Show me the history of my car's color.` | red, blue, black |

For every answer, capture the answer text, detected intent, status/found indicator, evidence source date, and grounded prompt. The final timeline should show red and blue as `HISTORICAL`, black as `CURRENT`, and links red <- blue <- black. These outcomes have automated coverage; a manual browser capture has not yet been recorded.

## 3. State-specific evidence

Repeat the three observations with optional controlled images only if suitable local test images are already available. Do not download photographs or models. Ask:

- `How do you know what color my car was originally?` Expected: evidence dated October 1 tied to red.
- `How do you know my car is black?` Expected: evidence dated October 20 tied to black.

Capture the source timestamp and session ID for each citation. In Light mode an image without detector verification is contextual and must be labelled as such; it must not be presented as a verified match.

## 4. Two car identities

Reset the disposable session and store:

1. October 1: `My first car is red.`
2. October 2: `My second car is blue.`

Ask:

| Question | Expected behavior |
|---|---|
| `What colour is my first car?` | answered: red |
| `What colour is my second car?` | answered: blue |
| `What colour is my car?` | abstained because the category is ambiguous |

Capture both distinct entity IDs and the Timeline panel. Phase 8 fixed the panel's missing `entity_ref` propagation and verifies both histories with Streamlit `AppTest`; the real-browser capture remains pending. Treat an absent or combined history as a regression and record it rather than changing data during the demonstration.

## 5. Unrelated image rejection

Use a fresh session and an already available red laptop test image.

1. Upload it with `My car is blue.` dated October 5.
2. Capture the ingestion JSON, especially `association_status`, `association_reason`, and memory action.
3. Ask `What color is my car now?` Expected: blue from text.
4. Ask `Which evidence supports the established car colour?` Expected: supporting text; the contextual image must not be a supporting evidence ID or create a conflict.
5. Reset. Upload the same image without text. Expected: `IGNORE` and no state.

This browser scenario uses detector-free Light mode. A red laptop must not be described as a verified car observation. Mocked tests and controlled Phase 6 detections validate association logic, not pretrained detector accuracy.

## 6. Conflict and insufficient evidence

A verified text/image conflict requires a matching detector output and is covered by controlled automated tests. Without already available local model assets, do not try to demonstrate it as real pretrained inference. Instead show the safe insufficient-evidence path:

1. In a fresh session ask `What color was my car on 2026-09-01?` before storing any car state.
2. Expected: `abstained`, no invented colour, and a note that no matching memory exists.
3. After storing the first car state on October 1, ask the same pre-history question again.
4. Expected: `abstained` because no state existed on or before September 1.

For a controlled conflict demonstration, run the existing automated test and label it accordingly:

```powershell
& $python -m pytest tests/test_end_to_end.py::test_text_image_conflict_is_flagged_not_applied tests/test_multimodal_evidence.py::test_matching_detector_marks_visual_evidence_verified -q --basetemp .pytest_cache/phase7-demo/conflict
```

Capture the test output separately from the browser evidence.

## 7. Persistence using disposable storage

The UI creates a new private namespace and does not reconnect it after a new server/browser session. Demonstrate database persistence independently with a disposable file:

```powershell
$env:PHASE7_DEMO_DB = (Join-Path (Resolve-Path .) '.pytest_cache\phase7-demo\persistence.db')
Remove-Item -LiteralPath $env:PHASE7_DEMO_DB -ErrorAction SilentlyContinue
& $python -c "import os; from src.agent.reasoning import MemoryAgent; a=MemoryAgent(db_path=os.environ['PHASE7_DEMO_DB'],light=True); a.remember('My car is red.',timestamp='2026-10-01',session_id='red'); a.remember('My car is blue.',timestamp='2026-10-10',session_id='blue'); a.remember('My car is black.',timestamp='2026-10-20',session_id='black'); print([(r.value,r.status.value,r.timestamp,r.previous_memory_id) for r in a.timeline_for('car')]); a.store.close()" | Tee-Object .pytest_cache\phase7-demo\persistence-write.txt
& $python -c "import os; from src.agent.reasoning import MemoryAgent; a=MemoryAgent(db_path=os.environ['PHASE7_DEMO_DB'],light=True); print(a.ask('What color is my car now?').value,a.ask('What color was my car before?').value,a.ask('What color was my car originally?').value); print([(r.value,r.status.value,r.timestamp,r.previous_memory_id) for r in a.timeline_for('car')]); a.store.close()" | Tee-Object .pytest_cache\phase7-demo\persistence-reopen.txt
```

Expected after the second process: `black blue red` and the same red-to-blue-to-black chain. Capture both files plus database path, size, and modified time. When demonstrating Streamlit restart, capture that the old file remains but the restarted UI creates a new empty namespace; record this as the documented session-resume limitation.

## 8. Completion record

Record each step as pass, fail, or not performed. A valid final evidence package contains:

- environment and launch logs;
- screenshots of all five temporal answers and the full timeline;
- answer/evidence timestamps;
- two-identity answers, ambiguous abstention, and Timeline panel behavior;
- unrelated-image ingestion metadata and rejection behavior;
- pre-history abstention;
- controlled conflict test output;
- persistence write/reopen outputs and database metadata.

Do not mark browser steps complete from automated tests alone, fabricate screenshots, or call controlled detections pretrained inference.
