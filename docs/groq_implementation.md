# Groq implementation and verification

The [assessment](groq_assessment.md) preceded implementation. This completes the
unfinished verification/reporting from the local-model pass and changes the
recommended conversational provider to Groq. [Setup/privacy/manual checks](groq_setup.md)
are separate from actual test evidence. No live API inference, browser test,
package installation, model download or Git mutation was authorized or performed.

## Implementation boundaries

- `src/llm_provider.py`: small provider contract. `src/groq_provider.py`: isolated
  OpenAI-compatible HTTPS adapter, environment-only key, explicit request opt-in,
  no redirects/proxies/tools, bounded context/output/response/timeout, strict JSON
  schema plus independent local type validation, sanitized failures, cooldown and
  explicit CLI probe. No provider/model upgrade or fallback.
- `src/local_memory.py`: retained class/API compatibility. Chat uses the configured
  provider; embeddings still use the independent local client/index. Groq status
  is a configuration check without network access, not a claim of live inference.
  Its provenance uses a mutable provider alias, **not a verified weight digest**.
  Bounded per-workspace extraction cache stores untrusted proposals, revalidated
  per observation. Model advice can only defer model-only candidates. Rules,
  confidence caps, exact quote/value checks, temporal parsing, contradiction gates
  and independent `SelectionPolicy` remain authoritative.
- `src/automatic_memory.py`: provider-specific extractor provenance. Generated
  replies cannot enter source evidence. Only existing engine paths write states.
- `app/account_app.py`: explicit external-processing notice and provider/embedding
  diagnostics. Unknown queries abstain and unresolved conflicts retain uncertainty.
  Current grounded responses may be rewritten conservatively; historical answers
  retain deterministic templates. Lexical guarding is not semantic proof.
- `config.groq.yaml`: separate demo storage and existing local car-colour artifact;
  `config.local.yaml`: explicit Ollama opt-in alternative. Default `config.yaml`
  and pinned requirements are preserved; the legacy UI remains deterministic.
- `conftest.py`: every test disables real local/external model access and removes
  inherited credentials; Groq-specific tests use disposable fake credentials and
  fake HTTPS only. `tests/test_groq_provider.py` covers adapter and authenticated
  pipeline behavior. Existing local tests continue to cover index generations,
  re-index failure, isolation and temporal validation.

No Groq-specific schema migration is needed. The previous local embedding phase
adds only its two account-local index tables, tested with temporary stores. No
user database was opened/reset. Conflict audits, original evidence references,
account boundaries, temporal history and reversible visibility remain intact.

## Executed tests

Executed on Windows 11 / existing Anaconda CPython **3.14.6**, Streamlit **1.58.0**,
pytest **9.0.3**, numpy **2.4.6**, Pillow **12.3.0**, scikit-learn **1.9.0**,
PyYAML **6.0.3**, joblib **1.5.3**. No packages were installed or upgraded and no
fresh-environment/Python 3.10 compatibility is claimed in this phase.

| Executed command using `C:\Users\DHANUSH S\anaconda3\python.exe` | Actual result |
| --- | --- |
| `-B -m pytest tests/test_local_models.py tests/test_automatic_memory.py -q` | 38 passed, 63.80s |
| `-B -m pytest tests/test_groq_provider.py -q` (initial) | 26 passed, 21.41s |
| `-B -m pytest tests/test_groq_provider.py -q` (expanded/final) | 30 passed, 26.89s |
| `-B -m pytest -q` | **289 passed, 0 failed, 0 skipped, 210.58s** |

All API responses and vectors in these tests are labelled fakes.
They establish protocol/control-flow behavior, not actual model precision/recall,
latency, image understanding, account quota or real provider compatibility.

The Groq tests cover missing key/consent; fixed HTTPS/schema/budget; credential
refusal; 400/401/403/404/429/500/503; seconds/date Retry-After; timeout/network
failure; invalid/extra/truncated JSON; redirects; candidate reuse with fresh
event-time parsing; both advisory outcomes; persisted unverified provenance after
SQLite reopen; grounded answer citations; lexical fallback independent of chat;
no loss of valid text on API failure; account/cache isolation; conflict uncertainty
and forgotten-state abstention. They do not use live Groq, a browser or a pretrained
vision model. Existing local-index and conflict-resolution tests ran in the full
suite, against isolated test data.

Integrity: six frozen Phase 4–6 annotation files, 14 historical benchmark reports,
`config.yaml` and `requirements.txt` match their previously recorded canonical-LF
hashes **and Git HEAD**. The existing car-head raw SHA-256 remains
`232658bc14429531eaaf5b3e4c86903ef1f4814d63f0d47f99edd0dd6170e62c`.
No frozen benchmark was rerun. See [machine-readable integrity evidence](../reports/groq_v1/integrity.json).
`git diff --check` passed (Git emitted existing LF/CRLF normalization notices,
not whitespace failures). New/untracked provider files were also checked for
trailing whitespace, Python syntax and documentation link targets. A bounded
credential-pattern scan of new/changed provider files found no matching keys;
this is not a comprehensive repository secret audit. Existing worktree changes
remain present and unstaged; no reset, clean, commit or push was performed.

The prior local diagnostic remains in `reports/local_models_v1/`. Corrected
lexical results: 4/4 precision, 4/9 recall on 12 assistant-reviewed queries; rule
extraction: 10/10 precision, 10/13 recall on 20 examples. These are small diagnostic
fixtures, not independent research gold or frozen Phase 6 metrics. Qwen/MiniLM
inference was unavailable. The actual local Open Images classifier smoke was
performed in the previous pass and documented there; no new visual accuracy claim
is made. All existing reports are preserved, including the explicit erratum for
the first diagnostic's source setup.

## Remaining limits and required action

User must confirm Groq Free plan/model access, configure a private key and opt-in,
and explicitly execute/authorize the documented synthetic probe. Only after a
real successful response can the live integration be called operational.

Follow-up secure launcher: `scripts/start_groq.ps1` prompts for a replacement key
without echo or disk storage, performs the explicit connection probe and starts
the authenticated app only on success. Its PowerShell syntax and mocked empty-key
cancellation/environment-restoration path were executed successfully. No real
key was configured in the agent environment, and no live inference/app launch was
performed. A key supplied in conversation was not copied into code, commands or
configuration; it must be revoked and replaced. The prior 289-test Python result
above predates this launcher-only follow-up; Python application code is unchanged.
Reviewed extraction/retrieval/response quality evaluation with the actual models
is pending that permission and availability. No live semantic model evaluation
or pretrained CV integration took place. The current car head recognizes only its
trained colours/category and cannot establish physical-object identity.

The cache is bounded in memory, scoped to one account workspace, and not a durable
retry/idempotency API. Changed identity context/restart may cause a new request.
Completion limits may truncate reasoning-model output and require later measured
tuning. Failures retain deterministic behavior. Server timeout may block a turn
up to 20 seconds by default; there is no retry loop. Provider model aliases can
change upstream. Privacy is now hybrid: text/context leaves the machine on opt-in,
CV/embeddings/memory stay local. Manual browser verification remains entirely
pending, with exact procedures in the setup guide.

Exact quote/value matching and confidence/usefulness checks are necessary guards,
not independent proof of the semantic relation assigned by a model. Candidate
provenance remains explicitly unverified. Independently reviewed relation-level
evaluation is required before claiming extraction accuracy or research improvement.

## Connection-error follow-up

The user's launcher received 56 key characters, then reported only a generic
HTTP failure. This confirms input length, not credential validity or a specific
HTTP status. The original diagnostic discarded the status; the root provider
error remains unconfirmed. The launcher deliberately stopped before Streamlit.

The adapter now includes the numeric HTTP status and a locally authored hint for
authentication, permissions, request/schema, quota and service failures, without
printing raw error bodies. It also sends an explicit application User-Agent and
JSON Accept header; this is not a confirmed fix for the unobserved status.
Focused offline tests: `-B -m pytest tests/test_groq_provider.py -q` — **30 passed
in 26.80s** after this change. Existing HTTP-error tests assert the safe numeric
status/hints and no retries or credential/body leakage. Scoped diff checking
passed. The full suite was not rerun for this diagnostic-only change; the 289-test
result above remains the earlier full run. No live inference, clipboard access,
user-database access or browser test was performed in this follow-up. Rerun the
launcher and inspect only the new `Groq HTTP NNN` line to identify the next step.

The later user-supplied log confirms a successful real connection probe, followed
by a separate closed-SQLite workspace error. See the [startup recovery follow-up](groq_sqlite_recovery.md)
for the reproduced failure, minimal UI fix, regression evidence and restart steps.
That successful probe was executed by the user, not by the coding agent.
