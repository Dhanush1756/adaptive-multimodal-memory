# Automatic multimodal memory: initial inspection

Inspected before this change on 18 October 2026. The working tree already
contained modified and untracked Phase 13/14 and Open Images work; it is preserved.
No commit/push or user-database access is authorized by this task.

The supplied diagram is the target architecture. The original PDF exists outside
the workspace at the previously supplied Downloads path. Although no Python PDF
reader is installed, the existing Git installation provides `pdftotext`; it was
used read-only to inspect the report directly. Its proposed contribution is a
unified lifecycle jointly considering contextual relevance, temporal validity,
contradiction resolution, evidence grounding and multimodal information. It names
Transformer/CLIP/LLaVA methods as proposed capabilities, not experimental results
of this implementation. The current task's automatic-selection and account
requirements extend that proposal; no literature results are attributed to us.

| Architectural component | Actual path before this change | Existing tests | Limitation / smallest required change |
| --- | --- | --- | --- |
| Text/image user input | `app/account_app.py` -> `Conversations.remember` or `ask` | `test_account_ui.py` | Store/Ask separate; add ordinary message send invoking selection and retrieval |
| NLP extraction | `MemoryAgent._remember` -> `extract_claims`; `project_claims` | `test_nlp.py`, `test_accounts_and_conversations.py` | One colour claim per ingest plus four project patterns; add explicit general claim grammar without replacing legacy benchmark path |
| Context and time | temporal extraction, `Candidate.timestamp`, `ingested_at` | `test_reliability.py` | Reuse event-time semantics; avoid inferring unnamed identities from unrelated turns |
| Visual extraction | `VisualPipeline.analyze` -> detector/crop -> attribute extractor | `test_cv.py`, `test_real_color_protocol.py` | Light mode has no detector; preserve contextual/non-supporting status |
| Trained visual head | opt-in `config.openimages.yaml`, histogram logistic head | actual saved-artifact run in `reports/openimages_colour_v1` | Four car colours only; no general object identity or pretrained inference |
| Evidence-grounded candidate | `fuse` -> `Candidate`, text/visual evidence | `test_multimodal_evidence.py` | Colour comparisons must not be applied to model/deadline/etc. attributes |
| Automatic selection | Absent before engine calls | None | Add independently configurable usefulness policy and persistent per-candidate decisions; do not treat extraction confidence as usefulness |
| Existing-memory comparison | `MemoryEngine.process` -> entity/attribute chain | `test_memory.py` | Existing schema supports arbitrary attributes but configuration restricts them; generalize only authenticated profile |
| Validation/lifecycle | confidence and association gates, conflict detection, chronological rebuild | `test_reliability.py`, `test_phase5_reliability.py` | Reuse; add automatic-mode weak/ambiguous claim gates before writes |
| Human verification | `verification_request`, `verify`, `Conversations.resolve`, pending observations and immutable resolutions | `test_accounts_and_conversations.py`, `test_reliability.py` | Keep human decisions distinct; never resolve automatically |
| Persistent account memory | Accounts identity -> UUID directory -> SQLite states/transcript/events | account persistence and isolation tests | Reuse authenticated scope; add additive selection/audit tables only |
| Retrieval | colour temporal retriever; `_project_answer` special case | `test_retrieval.py`, account tests | Add explicit entity/attribute lexical retrieval with temporal selection; do not label this semantic search |
| Response | deterministic `AnswerGenerator`; optional callable rephrasing | `test_end_to_end.py` | No configured operational LLM; disclose deterministic fallback, no invented provider integration |
| Memory management | memory/history/audit expanders | account AppTest | Add correction and reversible exclusion from retrieval; retain original evidence/audit rather than deleting history |
| Research evaluation | frozen Track A, exploratory Open Images, controlled cross-session | Phase 4–6 and cross-session tests | Add separate authored automatic-selection evaluation; no new frozen benchmark claims |

Implementation will remain incremental: policy/extraction tests, authenticated
automatic turn and retrieval, UI/management, then a separately versioned controlled
evaluation and full regression. No heavyweight downloads or dependency changes
are required. Natural-language coverage and missing operational LLM remain
explicit limitations; this does not justify replacing the temporal memory engine.
