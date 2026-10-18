# Phases 13-14: training readiness and persistent conversational memory

Implementation record, October 18, 2026. This extends the original memory
architecture. It does not establish unrestricted conversational understanding,
pretrained inference, real-photo accuracy or improvements to Phase 6 metrics.

## Scope and prerequisites

The complete seven-page submitted `nlp_report (1).pdf` was read from the supplied
Downloads location before implementation. Its RQ1 and four gaps are preserved.
The original PDF was not copied into the release; keep a permission-reviewed
reference copy with the submission. PDF extraction used pypdf 6.21.1 in a
disposable virtual environment, not in the application environment.

Audit findings:

- The original colour trainer silently selected histogram features if CLIP was
  absent, split real photographs using filename hashes and had no separate real
  development/test partitions. Its unsafe real-photo split is now disabled;
  synthetic-only training remains available for historical compatibility.
- No real-photo dataset or production colour-head artifact was available. Twelve
  empty class directories were prepared under the ignored `data/raw/colors/`.
- The supported Light environment lacks Transformers and local verified CLIP
  assets. No pretrained weights were downloaded and no expensive training began.
- Recovery-code namespaces were persistent but were not authenticated accounts.
- Transcripts, login history and general project facts were not stored by the
  original colour-only UI.

## New files and execution paths

| File | Role |
|---|---|
| `src/accounts.py` | Registration, scrypt hashing, random session tokens stored only as digests, login throttling, absolute expiration, explicit logout and private login history. |
| `src/conversations.py` | Authorizes every public operation, resolves a stable account-owned SQLite path, and uses the original MemoryAgent and MemoryEngine. Adds transcripts, lifecycle/evidence links, persistent pending disagreements and extractive summaries. |
| `app/account_app.py` | Separate authenticated Streamlit entry point; login, conversation selection, observations, cross-conversation questions, pending decisions, histories and audit. |
| `src/training/real_color_experiment.py` | Explicit histogram or local-only CLIP feature experiment with real-photo manifest validation, group splits and classifier/HSV evaluation. |
| `data/annotations/phase14_track_c_v1.json` | New controlled conversational evaluation; independent of frozen Phase 4-6 files. |
| `src/evaluation/cross_session.py` | Reproducible temporary-storage Track C and controlled Track D evaluation. |
| `requirements-models.in` | Untested optional model-environment input; not a lock or claim of model compatibility. |
| `docs/real_photo_manifest.example.csv` | Schema example, not a real dataset. |

`VisualAttributeExtractor` additionally accepts `cv.color_head_path` and validates
the artifact schema. `VisualPipeline.status()` exposes the classifier, feature
kind and dataset fingerprint. CLIP accepts an explicit local-files-only option;
the new experiment uses it and raises an error if CLIP cannot load. Existing HSV
and Light-mode behavior stays available. Model artifacts are ignored by Git.

## Authentication and persistence design

This is a **local research authentication profile**. Run on `127.0.0.1`. The
application has real password verification and server-side account scoping; it
is not a hosted identity-provider implementation.

Passwords use `hashlib.scrypt` with independent random 32-byte salts, N=32768,
r=8, p=3 and a 32-byte derived key. Passwords must be 12-1024 characters. No
plaintext password is stored. Random 256-bit session tokens are stored only as
SHA-256 digests, expire after eight hours and are revoked on explicit logout.
Five failed attempts trigger a five-minute per-name cooldown. Secrets are not
written to application logs or returned in login-history views.

The registry path is derived from the configured database's parent:
`authenticated/accounts.db`. Each registered user's memory is at
`authenticated/users/<server-generated-user-id>/memory.db`; images remain in
that same private account root. Callers provide a session token, not a user ID
or user-selected path. Unauthenticated callers cannot construct the service.
Every conversation operation checks both the active token and conversation
ownership. Separate accounts cannot enumerate one another's conversation IDs.

Account identity and memory persist after application restart. Browser refresh
may require logging in again; this intentionally avoids storing bearer tokens
in URLs or an insecure client-side workaround. Re-login to the same account
resolves the same private database. Browser close is not a reliable logout
event: the login record retains its explicit expiration time, and an expired
token is rejected if presented again.

The legacy `app/streamlit_app.py` remains the standalone local anonymous demo.
Its recovery codes cannot authenticate the account application or open account
databases. No anonymous memory is automatically claimed, moved or copied into
an account. Stop the anonymous demo before using the authenticated profile for
an account-based demonstration.

Before Internet-facing deployment, use a reviewed authentication provider or a
secure proxy with TLS, secure cookies, deployment-level rate limits, account
recovery controls and protected filesystem/backups. No such deployment was
performed here.

## Tables and migration behavior

The registry has `accounts`, `logins` and `login_attempts` tables. It is separate
from the memory database. Account memory databases keep the existing `memory`
and `conflict_resolutions` schemas and add:

- `conversations`: stable account ownership, title and creation time;
- `messages`: original user/assistant messages linked to conversations;
- `memory_events`: message -> state/action/evidence IDs;
- `conversation_summaries`: extractive content plus its source message IDs;
- `pending_observations`: original ingestion payload and resolution status.

Additions use `CREATE TABLE IF NOT EXISTS` and do not replace memory rows.
Existing legacy databases are not opened or migrated automatically. The
existing MemoryStore migrations remain responsible for backward-compatible
memory/audit columns. A registry transaction governs credentials/login records;
the private MemoryStore transaction atomically covers transcripts, memory
transitions, evidence links and pending/resolved decisions. If transcript
linking fails, only the newly generated evidence upload is removed as part of
that failed operation; earlier evidence remains unchanged.

Pending disagreements are reloaded from persisted ingestion payloads. Resolution
uses the server-stored payload, checks ownership and the existing resolution
uniqueness gate, and records the decision plus transcript link in one transaction.
Both original modalities remain available. Corroboration links only the new
source evidence to the new conversation; it does not reassign earlier sources.

## What enters long-term memory

The original colour extraction/fusion pipeline still handles tracked objects.
Additional explicit patterns support project `model`, project `requirement` and
user `preference` facts. Examples:

```text
My project model is CLIP.
We decided to train a colour classifier.
My requirement is offline inference.
I prefer concise answers.
My project named alpha model is CLIP.
```

Multiple supported statements separated by sentence/semicolon boundaries become
separate candidates in the **existing** adaptive engine. Queries support current,
previous, initial, history and ISO-date scopes for those project attributes.
"Last week" means the previous Monday-to-Monday calendar week relative to the
supplied query reference time. Unnamed project statements use one explicit
default identity; named projects remain separate and ambiguous questions abstain.

Other messages remain transcript-only. Uncertain, quoted or conditional project
statements do not match the explicit-statement extractor. The system does not
infer arbitrary facts from narrative paragraphs or treat transcripts as verified
memory. Unknown project attributes abstain. Summaries concatenate up to ten
source user messages; they are **extractive summaries**, not LLM reasoning.
Answer evidence includes original source messages, event/ingestion timestamps,
extractor method and conversation/message references. General coreference,
open-domain multi-hop dialogue and Transformer generation remain unimplemented.

Corrections create new historical/current versions instead of erasing old
observations. Data is retained until the operator performs a separately reviewed
erasure procedure. No deletion UI or automatic retention purge is supplied;
this phase does not claim compliance with a regulatory erasure requirement.

## Real-photo training protocol and blocker

No production real-photo model was trained. Supply approximately 100 lawful
images per configured colour where feasible, or document the smaller actual
scope. Each CSV row requires `path,label,object_id,source,license`; paths are
relative to the CSV and may not escape its directory. Use **reviewed object
crops** for this first classifier experiment. Background colour is not object
localization. Keep every physical object's views, bursts and augmentations in
one group. Review group identities and near-duplicates before freezing the CSV.

The new experiment rejects duplicate decoded pixels, flags similar dHash
patterns across groups, uses a fixed seed to allocate complete groups to
60/20/20 train/dev/test, and requires each included class in all three splits.
The checks cannot prove that human-supplied object IDs are correct. A conservative
near-duplicate warning can include false positives and requires data review.
Weights are fit only on train data. C is fixed before test execution; the code
does not select hyperparameters using test scores.

```powershell
python -m src.training.real_color_experiment --manifest data/raw/colors/manifest.csv --features hist --seed 13 --out models/colour-study-v1
```

For the preferred experiment replace `hist` with `clip`, after separately setting
up a verified model environment and locally cached encoder. The experiment will
not download weights or silently switch features. `requirements-models.in` is
only a proposed input; its package combination remains untested. No YOLO
inference or licensing claim is made until actual weights are obtained/reviewed.

Output contains `color_head.joblib`, `manifest.json` and `metrics.json`, including
class mapping, seed, input fingerprint, environment, class denominators,
classifier/HSV accuracy, per-class precision/recall/F1, both confusion matrices,
head-only prediction time and decode/feature/head time. Outputs refuse to
overwrite an existing experiment directory. Probabilities are explicitly
uncalibrated. Set `cv.color_head_path` to the trusted output artifact; the active
classifier/feature kind appears in the sidebar after restarting the app. A reviewed final artifact may
later be copied to `models/color_head.joblib` without overwriting an existing
artifact. No trained weight is added to this release.

## Verification and experiment scope

Tests use temporary accounts and SQLite files. No configured user database was
accessed. The pre-existing 193 tests and the new account, protocol and UI tests
are run together. Exact final counts and commands are recorded in the completion
section below. Streamlit AppTest validates the new authenticated UI flow; it
must not be described as an actual browser login/restart demonstration.

The standalone evaluation command is:

```powershell
python -B -m src.evaluation.cross_session --out reports/phase14/new-run.json
```

It refuses an existing output path. Track C contains twelve assistant-authored
queries, two source conversations, 120 intervening unrelated notes, stable and
changing preferences, late arrival, historical/initial questions, two car
identities and unknown-fact abstention. Login and both service/registry objects
are reconstructed before answering. Track D checks both human choices with
generated contrasting white-image fixtures. These are deterministic fixtures,
not natural dialogue, real photos, pretrained inference or Track B results.

Conversation-evidence precision/recall measure **sets of source conversations**,
not token-level citation quality. Small denominators do not establish general
long-term retrieval performance. No public LoCoMo/MTPChat result or superiority
claim is made. The published Track A metrics remain historical and unchanged.

## Demonstration procedure

```powershell
python -m streamlit run app/account_app.py --server.address 127.0.0.1
```

Use disposable accounts and record each action as PASS/FAIL/BLOCKED/NOT TESTED.
Never capture passwords, tokens, registry rows or complete recovery codes.

1. Register Alice, login, and capture the empty account interface and Light-mode
   status. A password shorter than twelve characters must be rejected.
2. Store `My project model is CLIP.` on October 1 and `My requirement is offline
   inference.`. Start a new conversation and store `My project model is YOLO.` on
   October 20. Ask current, previous, initial and history model questions.
   Capture values, dates and conversation evidence links.
3. Logout, stop Streamlit, restart with the same configuration, and login as
   Alice. Reopen the earlier conversation. Capture restored transcript, facts
   and login history. Browser refresh may require re-login.
4. Register Bob. Bob must see no Alice memories or conversations. Account login
   does not accept an anonymous recovery code as a password/session token.
5. In Alice's disposable account, store first-car red and second-car blue.
   Explicit identity questions must answer separately; a category-only query
   must abstain. Capture memories and evidence references.
6. Upload a white colour fixture with red-car text. Capture contextual,
   non-supporting provenance and the human prompt. Logout/restart before
   resolving; reopen the conversation and confirm the pending choice remains.
   Resolve one case to text and another to image. Capture accepted/current and
   original values, rationale, decision time, original IDs and resolution audit.
7. Upload corrupt image bytes with valid text. Capture the decoding warning and
   retained observation. Ask about an unstated project budget and capture abstention.
8. After a separately trained real-photo artifact exists, select its explicit
   configured path and capture the actual classifier/encoder/detector status,
   prediction, confidence and evidence provenance. **This final model step is blocked.**

## Research traceability and remaining gaps

| Requirement / gap | Implementation and evidence | Status / limits |
|---|---|---|
| Gap 1: temporal validity | Original state engine/retriever; account project facts use the same engine; current/previous/initial/as-of tests. | Implemented for constrained attributes; controlled evaluation only. |
| Gap 2: contradiction handling | Original fusion/verification, persistent pending observations, transactional resolution and audit; tests of both choices after reopen. | Implemented for controlled colour conflicts; real-photo uncertainty not evaluated. |
| Gap 3: provenance | Text/image evidence plus message/conversation links and audit snapshots; attribution/rollback tests. | Implemented for explicit facts; general evidence entailment remains open. |
| Gap 4: integrated CV memory | Existing CV -> fusion -> MemoryEngine; explicit trained-head loader and protocol tests. | Real trained production model and Track B evaluation blocked on data/assets. |
| Persistent identity | Scrypt registry, expiring sessions, stable account paths and authorization checks. | Tested local profile; hosted auth and cookie persistence not provided. |
| Semantic long-conversation recall | Structured project/preference retrieval, 120 intervening notes. | Partial; no learned extractor or natural-dialogue semantic retrieval experiment. |
| Calibration | Uncalibrated flag, existing confidence/association gates. | No real-photo calibration result; requires validation data. |
| Computational/storage cost | Per-query timings and database size in Track C; model timing fields in training protocol. | Measured small internal workload only; no scaling study. |
| Privacy/retention | Per-account access, private audit/history, retained corrections. | No automatic deletion policy or hosted privacy review. |
| External validity | Separate versioned artifacts and immutable output paths. | Public benchmarks, real-photo study and new comparative ablations remain pending. |

The revised paper should preserve the submitted motivation, literature review,
four gaps and RQ1, then describe the shared memory lifecycle, local identity
layer, controlled Track A/C/D evidence and the **unperformed** Track B protocol.
Use the historical Phase 6 tables unchanged. Treat persistence and auditability
as implemented system properties, not automatic claims of research novelty.

## Completion record

The final full-suite command was:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q -p no:cacheprovider
```

**212 passed in 110.00 seconds; zero failures and zero skips.** The environment
was Python 3.14.6, SQLite 3.53.2, Streamlit 1.58.0, pytest 9.0.3, NumPy 2.4.6,
scikit-learn 1.9.0, Pillow 12.3.0, PyYAML 6.0.3 and joblib 1.5.3. No model
dependency was installed into that environment. The new optional model profile
has not been installed or tested. Earlier focused runs passed the new behavior
tests; the full count includes all existing 193 regressions.

The final versioned evaluation command was:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.cross_session --out reports/phase14/track_c_d_v1_final.json
```

Executed results:

| Metric | Result |
|---|---:|
| Controlled cross-session query accuracy | 12/12 |
| Current/historical temporal accuracy subset | 4/4 |
| Source-conversation evidence precision | 11/11 |
| Source-conversation evidence recall | 11/11 |
| Unsupported answers on unknown-fact queries, divided by all queries | 0/12 |
| Abstention accuracy | 3/3 |
| Explicit identity accuracy | 2/2 |
| Service/registry reopen success | 1/1 |
| Controlled cross-user isolation scenario | 1/1 |
| Text-selected controlled image case | Prompted; current and original correct |
| Image-selected controlled image case | Prompted; current and original correct |

The small controlled run used 208,896 bytes for the account memory/transcript
database and measured median query latency 12.667 ms, maximum 16.533 ms. These
measurements do not include pretrained inference or establish scaling behavior.
Dataset byte SHA-256 for that run:
`7f8137269ad899d42653545ce120cddb1ccd0d7561674ac5f8e09a1680e69680`.

The old real-photo CLI was also executed with `--real-dir ... --light`; it
correctly exited nonzero with a migration message before opening a dataset or
initializing a visual pipeline. A regression test verifies the disabled splitter.

`git diff --check` passed. The supported `requirements.txt`, `config.yaml`, frozen
Phase 4-6 annotations and historical benchmark results show no changes. Canonical
LF-normalized hashes remain:

- Phase 4 test: `5796204c446fc69a4d126d08c77a6de436fc281c3737fb72336facf4c99654bd`
- Phase 5 test: `b911d6b9993dee49b995c324eb29d53dc37bbd7e5a9b880da0f7484b54f5e019`
- Phase 6 development: `a05c713fad1d8c06159c1b6a53502ea8748ac1e76ebb3ce39225aaa91c2e02bc`
- Phase 6 test: `831449bb23989915803bf715071a656bf663c6c335320890b8340edfa9fadaf7`

No Git commit/push/reset/clean was performed. No existing user database was
opened, reset or overwritten. No production trained artifact or pretrained CV
result is claimed. The new account UI's browser checks are **NOT TESTED**;
AppTest covers registration/login/logout, a new conversation and cross-login
recall. The manual procedure above remains necessary for browser verification.

Phase 14's constrained local implementation is tested. Phase 13's reproducible
training/loading infrastructure is tested with temporary generated fixtures;
its real-photo training/evaluation remains **BLOCKED** by the dataset and model
assets. The master plan's public-benchmark, natural-dialogue, calibration and
new comparative-ablation experiments remain unperformed. These are explicit
remaining deliverables, not completed research claims.

## Follow-up: Open Images baseline trained

The later [Open Images training report](openimages_colour_training.md) records
actual training and saved-artifact integration using 113 real car crops with
caption-derived, assistant-reviewed labels. This supersedes the dataset-blocked
status above **only for the four-colour histogram/logistic-regression baseline**.
It does not complete pretrained inference, independent human annotation,
12-colour coverage or verified physical-object grouping. The follow-up full
suite passed 221 tests; the historical 212-test run above is preserved.
