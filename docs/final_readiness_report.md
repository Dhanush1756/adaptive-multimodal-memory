# Final readiness report

Status reviewed on October 14, 2026. This report distinguishes executed automated evidence from unperformed browser/model work. Phase 7 did not launch an interactive browser, modify a user database, install dependencies, download models, or rerun the frozen benchmark.

## Status definitions

- **Verified by automated tests:** an executed regression or frozen evaluation directly covers the behavior.
- **Verified by manual execution:** a person launched and exercised the interactive application and captured output.
- **Pending manual execution:** automated evidence exists, but the required browser capture has not occurred.
- **Not performed:** no qualifying execution exists.
- **Blocked by missing models or dependencies:** the action requires unavailable local assets and cannot be run under the no-download constraint.

## Readiness matrix

| Validation item | Status | Evidence and exact boundary | Remaining action |
|---|---|---|---|
| Full automated regression suite | **Verified by automated tests** | Phase 6 recorded 169 passed, no failures/skips. Phase 7 rerun result is recorded below. | None if the Phase 7 run passes. |
| Red -> blue -> black state chain | **Verified by automated tests; pending manual execution** | `test_three_states_and_before_anchor`, persistence/retrieval tests, and Track A temporal families verify current, prior, initial, as-of, links, and timestamps. | Run section 2 of `final_demo_script.md` and capture all outputs. |
| Late-arriving event-time evidence | **Verified by automated tests** | `test_late_blue_observation_extends_state_using_event_time`, `test_later_support_does_not_backdate_blue`, and Track A late-arrival scenarios. | Optional browser demonstration only. |
| File-backed persistence across reopen | **Verified by automated tests; pending manual restart capture** | `test_file_database_reopens_with_states_links_and_evidence` and merged-session reopen test use temporary storage. | Run the two-process disposable check and capture Streamlit's expected new-namespace behavior. |
| Streamlit browser-session isolation/reset | **Verified by automated `AppTest`; pending manual execution** | `test_streamlit_browser_sessions_are_isolated_and_persistent` constructs two Streamlit sessions and verifies rerun, mode-change, and reset isolation. | Capture two real browser sessions. |
| Multiple-entity identity isolation | **Verified by automated tests; pending manual execution** | `test_two_explicit_car_identities_remain_separate`; Phase 6 identity accuracy 30/30. Scope is explicit ordinal references. | Capture first/second/ambiguous answers. Inspect the known Timeline panel limitation. |
| Multi-identity Streamlit timeline | **Pending manual execution; code-inspection concern** | The UI iterates entity records but calls `timeline_for(e['entity'])` without `entity_ref`; resolution can produce an unused third ID when two category instances exist. | Capture the panel behavior and log it as a UI presentation defect if histories are absent. |
| State-specific text/image provenance | **Verified by automated tests; pending manual execution** | `tests/test_multimodal_evidence.py` verifies selected current/historical evidence and timestamps; answer-contract test verifies supporting IDs. | Capture state-specific evidence in the browser. |
| Unrelated/contextual image rejection | **Verified by automated tests; pending manual execution** | Phase 5 contextual-image tests and Phase 6 0/15 controlled false associations. Light-mode contextual images are not detector-verified. | Perform the unrelated laptop upload using an existing local image. |
| Verified visual associations | **Verified only with mocks/controlled annotations** | Mocked detector integration tests; Track A recorded 30 TP, 0 FP. | Do not relabel as real-model evidence. |
| Controlled cross-modal conflict | **Verified only with mocks/controlled annotations** | End-to-end mocked conflict test and Track A 10 TP, 0 FP, 0 FN. | A browser conflict demo needs locally available verified detection. |
| Abstention and insufficient evidence | **Verified by automated tests; pending manual execution** | Missing-history and ambiguous-identity tests; Track A correct abstentions 20/20. | Capture an empty/pre-history abstention. |
| Existing SQLite `entity_ref` migration | **Not performed against a genuine legacy copy** | `MemoryStore.__init__` contains the additive `ALTER TABLE`; legacy visual JSON compatibility and ordinary reopen are tested. No standalone genuine pre-Phase-5 database-copy migration was found. | Run the copy-only procedure in `final_validation_checklist.md` if a legitimate legacy database is available. |
| Phase 6 Track A benchmark | **Verified by recorded execution and artifact audit** | 100 scenarios, 210 sessions, 265 questions, eight systems; test hash `831449...daf7`; complete-system errors/skips 0/0. | Preserve artifacts; no rerun required for Phase 7. |
| Phase 6 metric/report consistency | **Verified by Phase 7 audit** | Raw-query/session counts, aggregates, paired comparisons, error totals, family counts, manifest hash, and Markdown claims agree. | None. |
| Frozen annotation integrity | **Verified by Phase 7 audit** | Phase 4 test `579620...4bd`, Phase 5 test `b911d6...e019`, Phase 6 dev `a05c71...e02bc`, Phase 6 test `831449...daf7`. | Keep files unchanged. |
| Real pretrained CV inference | **Blocked by missing models or dependencies** | Read-only Phase 6 audit: `torch` and `ultralytics` present; no local configured YOLO weights, no `transformers`, and no configured CLIP cache. Track B unperformed. | Requires a separately approved model/data protocol. |
| Real-photo generalization | **Not performed** | No licensed real-photo dataset, labels, or pretrained Track B run exists. | Collect/approve data and execute Track B before making such a claim. |
| Interactive browser demonstration | **Pending manual execution** | No screenshots or actual interactive output were captured in this environment. | Follow `docs/final_demo_script.md`. |

## Experimental consistency audit

The frozen Phase 6 artifacts are internally consistent:

- All eight system records contain 265 raw queries and 210 raw sessions.
- The complete system has 240 correct of 265, 245 answered, 20 abstentions, and 25 wrong answered outputs. These counts reconcile with coverage, abstention, and unsupported-answer metrics.
- Current, historical, initial, history, and identity counts are respectively 90/90, 40/55, 15/20, 25/30, and 30/30.
- Lifecycle accuracy is 200/210. The confusion matrix contains five gold `ADD` cases predicted `IGNORE` and five gold `UPDATE` cases predicted `ADD`, matching the documented five ignored initial observations and ten lifecycle errors.
- Controlled conflict counts are 10 TP, 0 FP, 0 FN. Controlled visual counts are 30 TP, 0 FP, 0 FN, and 15 TN.
- Paired overall differences against no memory, latest value, naive multimodal, and append-only memory are +0.830, +0.434, +0.374, and +0.170. The no-provenance difference is zero; no-visual and no-conflict differences are +0.075 each.
- The deterministic error report and manual interpretation agree on the 15 `immediately preceded` query failures and the ten answer failures caused by five ignored initial observations.

No historical reporting defect requiring correction was found. One naming caveat remains in the machine-readable metric structure: `abstention_correctness` is computed over actual abstentions, while `abstention_rate` is the count of abstentions over all queries. Their values and denominators are consistent, despite both being represented with the generic `correct`/`denominator` metric shape.

## Reproducibility assessment

The run manifest records the command, Python/platform details, full configuration and hash, dataset hash, components, seed, scenario/session/query counts, system list, and dirty repository status. The runner loads static JSONL and writes reports; it does not rewrite input annotations. Benchmark agents explicitly use in-memory SQLite. Bootstrap and rendered-image seeds are fixed.

Material limits are that the repository had no available Git commit, the working tree was dirty, dependencies are not locked to exact versions, and Track A data is manually templated. The artifacts are reproducible within the recorded environment, but they are not an independently replicated or natural-distribution study.

## Phase 7 verification record

The final test and documentation-check results are populated after execution:

- Full pytest suite: **169 passed in 26.35 seconds; no failures or skips**.
- Documentation/reference checks: **passed**. All four Phase 7 files exist; required headings are present; every referenced repository path exists; all Phase 4/5/6 frozen hashes match; all Phase 6 JSON artifacts parse; eight systems each contain 265 queries and 210 sessions.
- Interactive Streamlit browser run: **not performed**.
- Pretrained/real-photo Track B: **not performed; blocked as described above**.

The project is ready for a controlled Light-mode demonstration after the pending browser walkthrough. It is not ready for claims about real-photo CV performance, broad identity resolution, external generalization, or manual UI validation until those specific checks are completed.
