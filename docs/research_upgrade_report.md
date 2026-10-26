# General CV/NLP and privacy upgrade — implementation report

Date: 26 October 2026. This phase extends the existing temporal memory engine; it
does not replace it. No commits/pushes, dependency installations, user-database
access or live-browser checks were performed. One documented compact model file
was explicitly downloaded; no large caption/embedding models were downloaded.

## Implemented versus evaluated

| Capability | Implementation and evidence | Status / limitation |
|---|---|---|
| Common-category detector | `ObjectDetector` optional torchvision SSDLite path; `weights_only=True`, no implicit downloads; weight hash enters observations | Actual CPU inference executed. 80 meaningful COCO labels are model vocabulary, not 80 evaluated categories. |
| Multiple objects | `VisualPipeline.analyze` emits separate boxes/categories/uncertain attributes; `AutomaticMemory._observe_image` stores image-only observations with message/event/ingestion provenance | Mocked multi-category tests and actual recorded-crop smoke. No general-category accuracy claim. |
| Physical identity safety | General research profile downgrades category matches to contextual; object observations stay unassociated/non-supporting | No automatic re-identification or inferred ownership. Legacy frozen profile behavior remains scoped and unchanged. |
| Scoped car model | Existing first-party head remains car-only; artifacts and original experiment unchanged | Historical baseline, not general image understanding. |
| Descriptions | `LocalDescriptions` supports cached SmolVLM-compatible safetensors; local-only, no remote code, bounded output, no acceptance authority | **Not executed**: transformers/model assets absent; actual caption quality and sensitive-output protections unverified. |
| Structured NLP | `candidate-memory-v2` provider schema; exact source-message/quote-span metadata; deterministic extractor v3 adds workplace and commitment statements | Mocked Groq tests; deterministic diagnostic evaluation executed. No real API quality score. |
| Semantic retrieval | Existing persisted index and model/dimension checks retained; hiding/erasure purge derivatives | Configured Ollama/MiniLM unavailable at loopback; actual semantic comparison **blocked**, lexical fallback retained. |
| External consent | Account preference defaults off, independent from server key/opt-in; consent rechecked before extraction/response | Mocked transport/account tests; no live API calls. |
| Sensitivity minimisation | Conservative pre-storage/transport gates for obvious credentials and highly sensitive terms; persist images without source metadata | Not a general PII detector; legacy stored content is not retrospectively scrubbed. |
| Account controls | Automatic-memory opt-out, inspect/export, reversible hiding, explicit full-workspace erasure, opt-in inactivity expiry | Tests cover persistence, authorization, missing consent, cache/index invalidation and other-account isolation. |
| Encryption | Separate protected profile: cryptography Fernet, HKDF-separated account keys, in-memory SQLite, atomic encrypted snapshots and encrypted evidence | Executed reopen/wrong-key/busy-lock/publish-failure tests. Registry metadata remains plaintext; not E2EE or forensic erasure. |
| Secure launcher | New protected launcher uses a separate Windows DPAPI data-key file; optional explicit reuse of saved Groq key | Native DPAPI create/reuse test with disposable profile and fake app process; not a browser/server deployment test. |

## Changed files and purpose

- `src/privacy.py`: classification, authorized evidence reads/export, account
  preferences, cache invalidation, complete content erasure and inactivity policy.
- `src/protected_storage.py`, `src/memory/store.py`: encrypted snapshots, key
  derivation, OS lock, RAM-only database and rollback on failed publication.
- `src/conversations.py`, `src/automatic_memory.py`: privacy integration across
  account APIs, exact candidate references and persistent visual observations.
- `src/local_memory.py`, `src/groq_provider.py`, `src/memory/selection.py`: consent,
  sensitive-payload refusal, versioned schema and additional explicit rules.
- `src/cv/detection.py`, `src/cv/descriptions.py`, `src/cv/embeddings.py`: optional
  compact detector, cached description adapter and local-only cache separation.
- `src/multimodal/{visual_pipeline,evidence,fusion}.py`, `src/memory/schema.py`,
  `src/agent/{reasoning,answer_generator}.py`: multi-object provenance, unknown
  attributes, encrypted metadata-free image persistence and answer evidence.
- `app/account_app.py`: privacy controls, evidence previews, explicit erasure,
  retention notices and general visual observations; legacy workflow preserved.
- `config.protected.yaml`, `config.research.yaml`, `scripts/start_protected.ps1`:
  explicitly separate new storage; protected deterministic/research startup.
- `src/data/local_detector_setup.py`, `requirements-privacy.txt`,
  `requirements-research.in`, `.gitignore`: bounded explicit model setup,
  optional tested dependencies and exclusion of local encrypted/model files.
- `src/evaluation/research_upgrade.py`, new diagnostic annotation and reports:
  new non-frozen experiments, no overwriting of historical artifacts.
- New privacy/research tests and updates to existing Groq/local/UI-related tests.
  Model-extraction fixtures now use ordinary hobbies rather than sensitive health
  statements; explicit account consent is granted where a mocked provider is
  intentionally exercised. Original privacy gates are not bypassed.
- README, documentation index and architecture updated; assessment, setup,
  threat model and this report added.

## Migration and storage behavior

Account initialization adds `privacy_preferences`, `privacy_audit` and
`visual_observations` with `CREATE TABLE IF NOT EXISTS`. Additional visual-evidence
fields have defaults for older JSON evidence. No existing database was opened for
this work. Existing accounts default to external processing disabled when they
next initialize this additive schema.

The protected profiles use separate account registries/directories. No plaintext
database is read, converted or overwritten by that path. Existing plaintext
workspace paths are refused. A genuine copied legacy-to-encrypted migration and
key rotation are **not implemented**. Protected workspace concurrency is limited
to one open instance per account; a second is refused rather than risking a stale
snapshot overwrite. The key is held separately from ciphertext and must be backed
up securely. Lost data keys cannot be reconstructed from a password or Groq key.

Erasure covers content/history/evidence/derived indexes within the authorized
workspace; minimal counts/timestamps and account/login metadata remain. Erasure is
not deletion of external exports, provider copies, backups, RAM or SSD remnants.
Evidence unlink failures are counted for retry; SQLite/files are not crash-atomic.

## Executed verification

Environment: Windows 11 x64, CPython 3.14.6, SQLite in the existing Anaconda build,
Streamlit 1.58.0, pytest 9.0.3, cryptography 49.0.0, torch 2.14.0+cpu and torchvision
0.29.0. No clean optional-environment installation was attempted.

- Focused privacy/Groq/local/UI/explicit-memory run: **75 passed in 88.63 s**.
- Focused privacy/research/UI run: **13 passed in 41.96 s**.
- Intermediate full suite: **315 passed in 202.35 s**.
- Final full suite after legacy API guards and protected-launcher coverage:
  **317 passed, 0 failed, 0 skipped in 202.46 s**.

Final command used a newly generated, previously absent temporary directory:

```powershell
python -B -m pytest -q -x --tb=short -p no:cacheprovider --basetemp=<fresh-temporary-directory>
```

Native DPAPI tests used disposable Windows profile paths and fake application/API
processes. They did not read the user's saved keys. AppTest upload payloads remain
injected fixtures, not actual browser-upload verification.

Intermediate findings were corrected rather than hidden: an encrypted-erasure
reopen regression exposed that publishing a serialization before SQLite commit
did not capture the expected deletion. The implementation now commits RAM,
publishes authenticated ciphertext atomically and restores the previous RAM
snapshot on publication failure. A separate early assertion searched for a
three-byte word in random ciphertext; it was replaced by a source-phrase and
authenticated-decryption check. A mocked second-account Groq case initially lacked
the newly required consent and was updated to grant consent explicitly.

## Actual inference and diagnostics

Official SSDLite weights downloaded: **14,069,355 bytes**, full SHA-256
`a79551df90c79834bcd3bb3845ef9d966b5449a3a9b2833ae8404778ca5d65d2`.

Actual protected image-only account turn: **304.64 ms**, model/account startup
**12.53 s**, two car-box predictions, uncertain colour values left unknown,
zero accepted memory states, encrypted snapshot/evidence, no plaintext memory.db.
Process RSS point samples were 228,917,248 bytes before model load and 516,644,864
after the turn. These are not peak RSS, broad accuracy or a latency distribution.
See `reports/research_upgrade_v1/integrated_inference.json`.

An earlier constructed two-crop collage was incorrectly labelled parking meter
at score 0.891. This negative result is preserved in `detector_smoke_limits.json`.
The examples do not establish detector precision/recall, mAP or robustness.

The new 16-case assistant-authored diagnostic had 10/10 expected explicit facts
recovered with no extra facts: precision/recall 1.0/1.0 and 16/16 exact cases.
The narrow legacy colour extractor recovered 0/10 on these non-colour facts.
This is a deliberately narrow domain baseline, not proof of superiority over
modern NLP models or the previous generic extractor. Median rule latency was
0.175 ms; the tiny authored set is not independent natural-dialogue gold. No real
Groq extraction, captioning or embedding-quality result is attributed to it.

## Integrity and pending work

All **22** recorded Phase 4–6/default-config/dependency integrity values and **10**
original Open Images experiment files match their earlier contents. The first-party
classifier binary hash matches. No benchmark runner was used to regenerate frozen
performance, and no historical metrics were changed. `git diff --check` passed;
only existing Windows line-ending conversion warnings were emitted.

Pending: independent new image/NLP gold review and held-out evaluation; caption
runtime/assets and actual inference; actual semantic comparison; clean optional
dependency installation; genuine legacy encryption migration; key rotation and
backup deletion/recovery operations; public-host security assessment and cloud
deployment. Browser validation for this phase was deliberately **not performed**.
The historical anonymous demo and direct low-level engine APIs remain outside
the account privacy boundary; the protected launchers select the account UI.

Follow [exact setup and manual checks](research_upgrade_setup.md). Do not present
this phase as universal recognition, complete privacy, production security,
independent research replication, fairness validation or improved frozen scores.
