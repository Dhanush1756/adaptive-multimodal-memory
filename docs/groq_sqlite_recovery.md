# Groq startup and closed SQLite connection follow-up

The user-supplied terminal log shows `PASS: actual Groq inference` with 152 input,
38 completion and 190 total tokens, followed by Streamlit startup. This is a
user-executed synthetic connection test, not an independently executed API call,
browser validation or extraction-quality evaluation by the coding agent.

The subsequent exception is independent: `ProgrammingError: Cannot operate on a
closed database`, from `app/account_app.py` -> `MemoryAgent.status` ->
`MemoryStore.stats`. The missing sentence-transformers/CLIP messages describe
existing hashing/histogram fallbacks; neither is the reported fatal exception.

The UI reused `session_state.workspace` based on existence and Light-mode value
without checking its connection. It also closed a workspace during a mode rebuild
before removing its cached reference. That leaves a stale-reference window if a
rebuild is interrupted. The specific event that originally closed the user's
connection is not established by the log.

`app/account_app.py` now probes a cached memory connection using `SELECT 1`.
Only the closed-database `sqlite3.ProgrammingError` invalidates the cached
workspace; other database failures still surface. Reconnection uses the current
authenticated account and existing configured storage. A rebuild removes the
cached reference before closing it. There is no reset, deletion or schema change.

The existing AppTest scenario in `tests/test_account_ui.py` now closes the cached
workspace deliberately, reruns, asserts a new workspace and the same selected
conversation, and compares the complete persisted memory/evidence records before
and after recovery. It then asks the same question and continues normal chat,
logout and login checks. This uses temporary SQLite and disabled external models.

Before the fix, this regression reproduced the exact exception: **1 failed in
11.49s**. After the fix, focused UI/account tests: **14 passed in 69.30s**.
Additional record-equality assertions were then added for the final full run.
The first version of those assertions incorrectly called an authenticated service
method from AppTest's control thread, hitting the registry's thread-affinity
guard: an intermediate full run had **1 failed, 288 passed in 195.89s**; a focused
diagnostic had **1 failed in 10.61s**. This was a test-harness defect, not a reason
to relax account-registry thread checks. Comparing records through the temporary
memory store (already configured for cross-thread access) corrected the test:
**1 passed in 13.42s**, including identity and full-record equality. Authentication
and subsequent questions continue to execute through the app thread.
Final full-suite execution on Windows / Anaconda Python **3.14.6**, Streamlit
**1.58.0**, pytest **9.0.3**:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q -x --tb=short
```

**289 passed, 0 failed, 0 skipped in 190.96s.** This includes the corrected AppTest
record-equality regression. Frozen annotations, 14 historical benchmark reports,
default config/requirements and the trained car-head hash match the previously
recorded integrity manifest (22 text files plus the model). Scoped diff checking
passed. No user database was
opened by the coding agent, and no live browser or additional Groq request was
performed in this follow-up.

After the code update, stop the running Streamlit with Ctrl+C and run:

```powershell
.\scripts\start_groq.ps1 -Clipboard
```

When prompted, copy the replacement key and press Enter without pasting. Open
the displayed local URL, log in to the same account/profile, and verify the saved
conversations and evidence. Capture any new traceback with credentials omitted.
