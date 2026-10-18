# Phase 11: Light-Mode Reliability, Audit Trail, and Session Recovery

Prepared on October 15, 2026. This phase changed the deterministic Light-mode
prototype only. It did not install packages, initialize pretrained models,
access an existing user database, rerun a frozen benchmark, or change Phase 4-6
annotations/results.

## Implemented behavior

### Reproducible dependency profile

`requirements.txt` now pins the packages present in the environment in which
the complete suite passes: CPython 3.14.6, NumPy 2.4.6, Pillow 12.3.0, PyYAML
6.0.3, scikit-learn 1.9.0, joblib 1.5.3, pytest 9.0.3, and Streamlit 1.58.0.
SQLite is supplied by Python and was 3.53.2 in the tested environment.

Phase 11 originally recorded an environment snapshot. Phase 12 subsequently
performed a clean installation in a separate virtual environment, found and
fixed two transitive compatibility pins, and passed the full suite. See
`docs/phase12_demo_reproducibility.md`. Optional pretrained packages and model
assets remain excluded from the validated Light-mode profile.

The Timeline selector now uses displayed strings as widget values instead of a
`format_func`. This removes the original Streamlit 1.31.1 selectbox failure.
Streamlit 1.31.1 remains unsupported because its AppTest has no file-uploader
element and hangs on application-triggered reruns in the recovery/reset tests.

### Conflict-resolution audit trail

SQLite now contains a `conflict_resolutions` table. Each immutable row records:

- resolution ID and original disagreement/conflict ID;
- source memory ID and resulting memory-state ID;
- textual/memory value, image value, selected value and selected source;
- UTC resolution timestamp, decision source, actor and optional rationale;
- source session ID;
- frozen snapshots of the original text and visual evidence.

The table is created with `CREATE TABLE IF NOT EXISTS`, so opening an existing
database preserves all `memory` rows and adds the audit table. Compatibility
guards also add the two evidence-snapshot columns if an early audit table lacks
them. Older already-resolved records cannot be reconstructed automatically and
therefore have no synthetic audit entries.

Resolution and state update occur in one SQLite transaction. The original
conflicting record becomes `RESOLVED`, while its evidence remains stored. A
unique constraint on `original_conflict_id`, plus checks before and inside the
transaction, prevents a repeated request from producing another state or audit
row. Both text/memory and image choices were tested through SQLite reopen.

The Streamlit **Resolution audit** section displays the decision and the frozen
evidence IDs. It does not place resolved conflicts back in the accepted state
timeline.

### Recoverable isolated sessions

Each browser session receives a cryptographically random 32-hex-character
(128-bit) recovery code. Database and image paths remain under that session's
private directory. The application never lists codes or session directories.
Recovery validates the code strictly and opens only an already-existing
database; malformed, unknown and missing codes receive the same error and do
not create storage.

This is local bearer-code recovery. Anyone who obtains a code can open that
session, so a hosted multi-user deployment still requires authentication,
authorization and protected transport/storage. Those systems were not added.

## Automated verification

Commands were run with bytecode and pytest cache writes disabled:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q -p no:cacheprovider
python -B -m pytest -q -p no:cacheprovider
```

Results:

| Environment | Result | Status |
|---|---:|---|
| Python 3.14.6, Streamlit 1.58.0, pytest 9.0.3, SQLite 3.53.2 | **193 passed in 35.30s** | Supported and tested |
| Python 3.10.8, Streamlit 1.31.1, pytest 9.0.2, SQLite 3.37.2 | **188 passed, 5 failed in 47.87s** | Unsupported |
| Changed-area tests | **51 passed in 23.72s** | Supported environment |

Three old-environment failures are file-upload tests blocked because Streamlit
1.31.1 AppTest has no `file_uploader`. Two are AppTest timeouts after `st.rerun`
in recovery/reset flows, including with a ten-second timeout. These traces do
not prove browser failure, and no manual 1.31.1 browser test was performed.

Automated coverage includes text then image observations, uncertain conflicts,
both human choices, historical queries after resolution, same-category entity
separation, session recovery/isolation, invalid and missing recovery codes, CV
failure, evidence provenance in answers/UI, backward-compatible migration,
duplicate-resolution rejection, and persistence across SQLite reopen.

Canonical LF-normalized Phase 4-6 hashes were rechecked and remain unchanged:

- Phase 4 test: `5796204c446fc69a4d126d08c77a6de436fc281c3737fb72336facf4c99654bd`
- Phase 5 test: `b911d6b9993dee49b995c324eb29d53dc37bbd7e5a9b880da0f7484b54f5e019`
- Phase 6 development: `a05c713fad1d8c06159c1b6a53502ea8748ac1e76ebb3ce39225aaa91c2e02bc`
- Phase 6 test: `831449bb23989915803bf715071a656bf663c6c335320890b8340edfa9fadaf7`

No Phase 6 performance change is claimed.

## Pending manual browser checklist

Launch with the pinned supported environment:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Capture actual screenshots/logs for these checks:

1. Confirm Light mode and component status; save the recovery code privately.
2. Store red (October 1), blue (October 10), black (October 20); capture the
   ordered state links and current/previous/original/history answers.
3. Upload a contrasting image after a text state; capture contextual,
   non-supporting provenance and the uncertain/disagreement message.
4. In separate disposable sessions, choose text once and image once. Capture
   the resulting state and Resolution audit, including evidence IDs and times.
5. Store first-car and second-car states; capture separate Timeline filters and
   category-only abstention.
6. Stop and restart Streamlit, enter the saved recovery code, and capture the
   restored timeline. Try malformed and unknown codes and confirm the generic
   error without creating a session.
7. Upload unreadable image bytes with valid text and capture the CV warning and
   retained text state.
8. Verify answer evidence shows stable text/image IDs, source session, event
   timestamp, ingestion timestamp, association/support status and extractor/CV
   method.

Phase 11 itself did not perform a real browser demonstration. Phase 12 later
executed the listed flows with a live Streamlit server and headless Chrome; its
evidence and exact results are in `docs/phase12_demo_reproducibility.md`.
