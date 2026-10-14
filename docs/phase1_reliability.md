# Phase 1 — Reliability and regression tests

Reviewed and verified on October 12, 2026. The existing integrated NLP/CV pipeline and
SQLite memory architecture are retained. No dependencies were installed, models downloaded,
configuration values changed, or existing user databases opened/reset for verification.

## Temporal contract

`remember(..., timestamp=...)` supplies the source observation/reference time. An explicit
date in the text supplies the event time; otherwise the supplied timestamp is the event time.
Arrival order is never substituted for an explicitly supplied date.

As confirmed for this phase, red on October 1, blue on October 20, then a compatible blue
observation dated October 10 produces these earliest-known states:

| Interval | Value |
|---|---|
| October 1 through before October 10 | red |
| October 10 onward | blue |

The existing blue memory ID is retained, its start is extended to October 10, and both source
observations keep their original dates. October 15 therefore returns blue because of the
October 10 observation. A statement arriving on October 30 that explicitly confirms an
October 20 event leaves October 15 red. These are state estimates from evidence, not proof
of the exact physical instant when an object changed.

## Confirmed causes and fixes

| Cause confirmed by a regression | Fix |
|---|---|
| Earlier compatible evidence was appended without updating the state's start | Extend the adjacent compatible state's start and rebuild links inside the transaction |
| `MemoryAgent` ignored `paths.db_path`; the UI explicitly used RAM | Honor configured paths; give each browser session a separate persistent database |
| SQLite connection failed when database parents were absent | Create parent directories without replacing existing files |
| `st.cache_resource` shared mutable user memory | Store the agent in `st.session_state`; mode changes reuse that memory |
| Individual store methods committed before a whole transition completed | Nested SQLite transactions/savepoints cover ID allocation, evidence and chain updates |
| Image save errors occurred after database commits | Save inside the ingestion transaction and remove only a newly created file on failure |
| Image filenames came from reusable source session IDs | Generate independent UUID image IDs and use exclusive file creation |
| Image citations used the state's date and inferred session from filenames | Store source timestamp/session in visual-evidence JSON; retain legacy fallbacks |
| Reopening forgot session IDs belonging to merged evidence | Check persisted text and visual evidence when allocating source session IDs |

File-backed SQLite round trips and independently constructed agents already worked when
their paths were explicitly supplied and parent directories existed. They are now protected
by regression tests; they were not reported as newly discovered failures.

## Files changed

| Files | Purpose |
|---|---|
| `src/memory/store.py` | Parent creation, transactions, atomic evidence writes, state-start updates |
| `src/memory/update.py` | Transactional memory decisions and event-time-aware compatible merges |
| `src/memory/schema.py`, `src/multimodal/fusion.py`, `src/agent/answer_generator.py` | Preserve and cite independent visual-evidence dates/sessions |
| `src/agent/reasoning.py` | Configured persistence, per-agent locking, unique image files, rollback on failed ingestion, persisted session-ID checks |
| `app/streamlit_app.py` | Per-browser-session agent/storage; Light mode on by default |
| `src/evaluation/ablations.py` | Explicit in-memory agents so benchmark resets never target user storage |
| `tests/test_reliability.py` | 20 new parameterized regression cases |
| `tests/test_end_to_end.py`, `tests/test_memory.py` | Stronger history/link/date assertions and explicit store cleanup |
| `conftest.py` | Isolate optional trained artifacts from the offline test baseline |
| `README.md`, `docs/training.md`, this file | Updated runtime status, storage contract, verification and manual demo |

## Executed verification

Environment: Anaconda Python 3.14.6 and Streamlit 1.58.0, using already-installed packages.

| Run | Actual result |
|---|---|
| Original test suite before edits | 122 passed |
| New regression file plus strengthened end-to-end tests, before implementation fixes | 12 failed, 10 passed |
| Focused tests after fixes and resolving test-runner directory issues | 22 passed |
| Full final suite, including concurrency and legacy-format checks | 142 passed in 17.26 seconds; no failures or skips |

Intermediate verification attempts encountered a sandbox parent-directory access error,
an inaccessible pre-existing pytest system-temp directory, and a missing parent for the
new scratch location. Those setup errors did not count as passes. The final run used the
explicit Anaconda interpreter and a fresh, verified workspace scratch path under
`.pytest_cache/phase1-<uuid>` with pytest's cache provider disabled.

All test database/image writes used temporary paths or `:memory:`. Optional trained model
paths were redirected to test-local locations. The Streamlit test used two independent
`AppTest` sessions, real SQLite-backed agents and Light-mode components. It checked isolation,
rerun reuse, mode switching and reset isolation. It did not run a manual browser session or
pretrained models. Concurrent-writer checks cover both a shared connection and separate
connections to the same temporary database. Injected failures verify rollback, and a second
connection verifies that partially applied state transitions are not visible.

Normal local test command from the project root:

```powershell
python -m pytest -q
```

If multiple Python installations are present, select the tested interpreter explicitly:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m pytest -q
```

## Manual demonstration

From the project root:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Keep Light mode enabled. In one browser session, store the following with the specified dates
(optional matching photos may be added):

1. October 1, 2026: `My car is red.`
2. October 10, 2026: `I repainted my car blue.`
3. October 20, 2026: `I repainted my car black.`

Ask current, previous and original color: expect black, blue and red. Ask the color on
October 15: expect blue. The timeline must retain all three states, with red and blue
HISTORICAL and black CURRENT. `Show the evidence for my car.` displays supporting records.

Open a separate browser tab/session: it starts empty. Store a different color there, then
reset the first session. The second session must retain its own memory. Switching Light
mode or interacting with widgets in a session preserves that session's stored state.

For the late-evidence example, use a fresh session: red on October 1, blue on October 20,
then blue dated October 10. October 15 should return blue; October 9 should return red.

## Remaining limits

- A fresh browser connection/server restart does not automatically reconnect to a previous
  private namespace. SQLite files persist and can be explicitly reopened by database path.
  There is no account authentication or session-resume UI in this phase.
- Reset clears only that agent's database. Saved images remain on disk; retention/deletion
  policy is deferred. UUID filenames prevent reuse from overwriting another observation.
- SQLite and the filesystem do not form a crash-atomic distributed transaction. Handled
  failures roll back the database and clean up the new image, but a process/power failure
  can leave an unreferenced image file.
- Legacy images without source timestamps retain their previously available state-date
  fallback; missing historical metadata cannot be reconstructed.
- Current means the latest recorded state. Same-time claims retain insertion-order behavior;
  timezone normalization, future-event policy and broader temporal ambiguity remain unchanged.
- One color attribute, one claim per ingestion and one entity instance per type remain the
  prototype's limits. Late compatible merging assumes continuity between adjacent observations.
- Pretrained model inference, real-photo performance, model training and research ablations
  were not executed. No research-performance claims follow from these regression results.
