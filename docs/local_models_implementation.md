# Local-first NLP, extraction and semantic memory phase

**Follow-up:** conversational provider selection is superseded by the requested
[Groq phase](groq_implementation.md); the local embedding component and recorded
diagnostics below remain valid. Earlier pending full-suite output was lost when
the execution session ended; no success is inferred for that run. The follow-up
report records a fresh full-suite execution against the combined implementation.

Date: 18 October 2026. The [hardware assessment](local_models_hardware_assessment.md)
preceded model selection and implementation. [Exact setup and manual checks](local_models_setup.md)
are separate from executed results below. Existing user work and prior reports
remain intact.

## Implemented, with availability explicitly distinguished

Authenticated `Conversations` now initializes `LocalMemoryServices` by default.
It uses `OllamaLocal` over numeric loopback HTTP, never an external LLM/embedding
API. There are no API-key requirements, new pip dependencies, automatic pulls,
provider SDKs or browser actions. The selected initial models are Qwen3 0.6b
Q4_K_M and separate Ollama all-minilm embeddings, based on the measured limited
free RAM. The latter is a MiniLM-family model, not an experimentally established
equivalent of Hugging Face all-MiniLM-L6-v2.

**Real Qwen and MiniLM inference are BLOCKED in this environment:** Ollama was
not found on PATH/default installation path, no process was running, and the
loopback API was unavailable. Integration is implemented and protocol/flow tests
execute with labelled fakes, but neither model's quality or runtime footprint has
been verified. No runtime or weight installation was performed. The app reports
setup/status clearly and retains deterministic response and lexical fallbacks.

## Execution paths and safeguards

1. `AutomaticMemory.chat` extracts deterministic candidates, then optionally calls
   `LocalMemoryServices.extract` against the local text model. Only the current
   user message supplies evidence. Returned quotes and values must occur literally
   in it. Hypotheticals, inference, unsupported negation and unstated identities
   are independently rejected even if the model labels them explicit.
2. Model claims have capped heuristic confidence 0.8 and a model/digest/quote audit
   marked `verified:false`. They pass the original configurable usefulness policy
   and temporal engine. Weaker changed claims require clarification unless an
   explicit correction/change cue is supplied. No generated answer is re-ingested
   as evidence, and the model has no tools, database connection or human-decision API.
3. `general-explicit-rules-v2` adds bounded deterministic forms for residence,
   preferences, relationships, project obligations/deadlines and verbatim negative
   constraints. Existing v1 evidence stays readable and is not rewritten. Other
   negation remains transcript-only; arbitrary negative logic is not implemented.
4. Queries retain the original lexical/temporal path when it already answers or
   is uncertain. Otherwise, local semantic matching may nominate an entity/attribute
   group. Explicit category/reference restrictions, duplicate-identity ambiguity,
   an untuned cosine threshold/margin and evidence/current-state ranking apply.
   The original temporal selector then resolves current/previous/original/as-of;
   a vector hit never directly becomes an answer. Pending image conflicts still
   return uncertain and require the existing explicit human workflow.
5. A local response may rephrase supported current facts or provide non-personal
   conversation. Citations, selected values and a conservative vocabulary/negation
   guard are checked. Historical/conflicting answers retain deterministic templates.
   A validated answer note remains inspectable. This guard is **not a proof of
   semantic entailment**; independently reviewed answer-quality evaluation remains
   necessary. With forgotten chains, historical transcript context is omitted so
   it cannot reintroduce them. All unanswered questions preserve deterministic
   abstention, including forgotten objects without a `my` pronoun. Open-domain
   factual Q&A is not an automatic fallback. Non-question conversation can use
   local generation but cannot claim to have saved or resolved a memory.

The existing optional manual Ask route also receives local retrieval/response
fallbacks. Legacy manual extraction remains available for compatibility. Generic
automatic memory continues through normal Send; this phase does not rebuild the
application as a new server or generic chatbot.

## Persisted index and migration

Only two additive account-local tables are introduced:
`local_embedding_generations` and `local_memory_embeddings`. They record model
name/digest, dimensions, document-schema version, source-content hashes, generation
and original memory IDs. Embeddings describe entity, explicit reference, attribute
and value; original evidence IDs/references remain on the unchanged memory records.

Re-indexing prepares complete vectors, checks the model digest again, and switches
the unique active generation in one SQLite transaction. Old generations remain.
Failures and dimension/version mismatches do not activate partial vectors. Search
filters hidden/changed/nonmatching source records and never mixes model versions.
Indexes live inside each account's own SQLite database; no cross-user vector store
or global memory cache is introduced. Tests cover persistence after reopen,
failed rebuild, changed model version/dimension, isolation and forgotten chains.

No existing user database was opened to perform migration; migration execution
uses disposable test databases. User login later creates the additive tables in
that user's database. Old states/evidence/audits are not reset or overwritten.
The small prototype index is limited to 512 documents by default; old generations
can accumulate. Local inference remains bounded but may hold the existing request
transaction/agent lock while running. Multi-process throughput, streaming and
high-concurrency deployment are not evaluated here.

## Local image processing

The authenticated config enforces cached/local-only optional NLP/CV weights.
Missing YOLO weights now skip initialization before a downloader can run; CLIP
uses its existing local-files-only option, and sentence-transformer loading is
also local-only. Light mode still uses actual HSV/histogram computation. A test
verifies the missing-weight detector path without importing/downloading a model.

An actual **existing Open Images crop** was processed with the unchanged saved
car-colour artifact and `light=True`: output white, `hsv+head`, detector absent,
association contextual, visual confidence 0.305. Model hash stayed
`232658bc14429531eaaf5b3e4c86903ef1f4814d63f0d47f99edd0dd6170e62c`.
Cold initialization plus analysis took 6530.10 ms in that process; this includes
imports/loading and is not comparable with warm per-image timings.
`reports/local_models_v1/cv_local_smoke.json` records the actual observation.
This is one local loading/inference smoke check, **not new accuracy, pretrained
inference, object identity proof or general image understanding**. Images are not
sent to the Qwen text model. The classifier remains four colours for car crops.

## Actual diagnostic evaluation

Executed command:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.local_models --out reports/local_models_v1/final_run.json
```

The output already exists; use a new filename to reproduce. It uses temporary
accounts/databases, 20 assistant-authored/inspected extraction messages and 12
retrieval questions over eight controlled source states. Independent human review
is pending; this is not natural-dialogue gold, a statistical held-out experiment
or public-benchmark performance.

| Measurement actually executed | Result |
| --- | --- |
| Deterministic extraction precision | 10/10 (1.0) |
| Deterministic extraction recall | 10/13 (0.7692) |
| Exact extraction cases | 17/20 |
| Lexical retrieval precision / recall | 4/4 (1.0) / 4/9 (0.4444) |
| Correct negative-query abstention | 3/3 |
| Exact retrieval cases | 7/12 |
| Local path with unavailable-model fallback | Same 7/12, **not semantic model performance** |
| Real local LLM extraction comparison | BLOCKED; model metrics null |
| Real local embedding comparison | BLOCKED; no semantic-quality claim |

The three missed extraction claims are allergy paraphrases and a natural
commitment. Paraphrased retrieval remains limited without the model. Median lexical
query time was 1.428 ms; the **additional** unavailable-local fallback path was
0.223 ms median. These are separate stages, not evidence that semantic inference
is faster. Per-case latencies are recorded. Python RSS point samples were
46,092,288 → 53,465,088 bytes; Ollama process RSS was zero because no runtime was
running. These are not peak/model-memory measurements. Optional psutil sampling
may miss peaks/shared-memory effects.

Dataset byte SHA-256:
`d10d83b5b4e01a225f9f976400c3324408f88c93d6452f70ac232e3a545d2054`.
`run.json` preserves an initial evaluation setup error; its retrieval figures are
invalid because it populated unsupported generic fields through the legacy
manual path. `run_notes.md` explains the correction. `final_run.json` populates
facts through the actual automatic path with models disabled and asserts eight
states before comparing retrieval. No metric was silently overwritten.

## Tests and environment

Supported execution: Windows 11, CPython 3.14.6, Streamlit 1.58.0, numpy 2.4.6,
Pillow 12.3.0, PyYAML 6.0.3, scikit-learn 1.9.0, joblib 1.5.3, pytest 9.0.3.
The first transport checks passed 7 tests in 0.93 seconds. An expanded focused
account/UI run passed 41 tests in 65.70 seconds. Protocol tests exercise real
loopback HTTP against an explicitly synthetic stub server; semantic-flow tests
use deterministic fake vectors/responses. Neither is real model inference.

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest tests/test_local_models.py tests/test_accounts_and_conversations.py tests/test_account_ui.py -q
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q
```

Final combined full-suite results are recorded in `docs/groq_implementation.md`.
No packages were installed and no clean-install/Python 3.10 compatibility claim
is added. Tests explicitly disable access to any real local runtime unless they
provide their own fake, preventing fixture data from reaching an existing daemon.

## Changed files and remaining work

New runtime/service/index files: `src/local_runtime.py`, `src/local_memory.py`,
`src/retrieval/local_index.py`. Existing authenticated chat, reasoning, config copy,
UI, deterministic selection and local-only NLP/CV loaders connect them. New
`config.local.yaml`, local diagnostic dataset/runner/reports and
`tests/test_local_models.py` provide setup and regression coverage. The existing
automatic-memory provenance assertion now expects v2 for newly extracted facts;
historical v1 records and reports are preserved. `conftest.py` isolates tests from
real runtimes. No new database engine, model training or external service exists.

Remaining blockers: install the runtime/weights explicitly, execute actual Qwen
and MiniLM probes/evaluation, independently review annotations and generated
answers, measure real latency/RSS and tune on separate development data. Literal
quote/value gates restrict extraction recall; confidence and thresholds are
heuristics. No GPU, real conversational-model quality, semantic improvement or
general visual ability is established. The user will perform the documented
browser checks; none were executed in this phase. No commit, push or destructive
Git operation was performed.
