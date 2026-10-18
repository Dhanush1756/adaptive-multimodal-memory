# Local Ollama setup, launch and manual demonstration

**Superseded default recommendation:** the latest requested conversational
provider is Groq; see [current setup](groq_setup.md). This file remains the explicit
Ollama alternative and optional local embedding setup. No Ollama/model install
has been performed. Select `config.local.yaml` plus `AEGM_LLM_PROVIDER=ollama`
to use this older conversational configuration.

Read the [hardware assessment](local_models_hardware_assessment.md) and
[implementation/results report](local_models_implementation.md). The integration
is local-first by default in the authenticated application. **Ollama and its
weights were not installed during implementation. No successful real Qwen or
MiniLM inference is claimed yet.** No external API key or paid API is required.
Electricity, RAM, CPU time and disk usage remain local costs.

## 1. Install Ollama explicitly

Download the Windows installer from the [official download page](https://ollama.com/download/windows)
and run it interactively. Follow the
[official Windows requirements](https://docs.ollama.com/windows). This installation
is separate from Anaconda; no new Python dependency is needed by this integration.
The pinned Light-mode environment remains Python 3.14.6 and `requirements.txt`.
Do not upgrade the existing Anaconda environment to install Ollama.

Open a new PowerShell terminal after installation:

```powershell
ollama --version
```

If it is not on PATH, use the installed binary explicitly, normally:

```powershell
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version
```

Do not copy a random executable or model from an untrusted source.

## 2. Run a local-only server

Quit an existing Ollama tray instance first if it owns port 11434. In terminal A,
set these variables **before starting the server**, not just in the Streamlit shell:

```powershell
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_HOST = '127.0.0.1:11434'
ollama serve
```

Leave this terminal running. The application accepts only loopback IP HTTP
endpoints, ignores proxy environment variables for these requests, rejects
redirects/cloud model definitions, and never calls a model-pull endpoint. Local
transport cannot attest to an arbitrary daemon's configuration; disable Ollama
cloud features as above. No packet-capture/network-isolation test was performed.
[Ollama local-only configuration](https://docs.ollama.com/faq).

## 3. Download the selected models yourself

These commands intentionally download weights. They were **not executed** during
implementation. In terminal B:

```powershell
ollama pull qwen3:0.6b
ollama pull all-minilm:latest
ollama list
ollama show qwen3:0.6b
ollama show all-minilm:latest
```

At assessment, the catalogue listed Qwen3 0.6b Q4_K_M at 523 MB and all-minilm at
46 MB. Runtime binaries and working memory require additional space. Verify the
quantization actually installed with `ollama show`; tags can change. The runtime
digest is recorded by extraction and each embedding generation. Keep the weights
associated with a result when reproducing it. Downloads need Internet access;
ordinary subsequent inference and memory processing use the local server.

The initial profile uses CPU inference, four threads, 2048 context tokens,
bounded output, `think:false` and `keep_alive:0` to release model memory between
calls. This favors low memory over warm-response latency. Current free RAM was
only about 3.5 GiB at audit; close unnecessary applications and measure resource
usage. Download size is not a memory requirement guarantee.

Qwen3 1.7b Q4_K_M (catalogue: 1.4 GB) is a later optional comparison, **not the
default**. Only pull it deliberately after freeing RAM and measuring the smaller
model. Select it in a separate profile with `llm_model: qwen3:1.7b`; do not assume
larger means feasible or validated. No measured accuracy/latency exists for either
size on this machine yet.

## 4. Run actual inference evaluation

From the repository root, after setup:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.local_models --out reports/local_models_v1/user_run_01.json
```

This uses temporary accounts, temporary SQLite and the versioned reviewed
diagnostic examples. It does not open your normal account database or rewrite
frozen benchmarks. Output filenames must be new. Inspect the chat and embedding
probe statuses, per-case outputs, model digests, failure/fallback status, latency
and resource fields. A status probe alone is not successful inference. Scores
with a BLOCKED label are not model performance. `psutil` is optional for resource
samples; absent samples are null, not zero memory usage.

The dataset was authored and inspected by the assistant. Review its labels in
`data/annotations/local_nlp_review_v1.json` yourself before treating it as human
gold. Make a separately versioned dataset for corrections; do not relabel an old
run to improve its score. No claim of public-benchmark performance follows from
this diagnostic.

## 5. Launch the account app

Use a new disposable profile/account for rehearsal:

```powershell
$env:AEGM_CONFIG_PATH = (Resolve-Path config.local.yaml).Path
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/account_app.py --server.address 127.0.0.1
```

Register a new account, log in, and keep Light mode enabled for CV. This profile
uses separate `data/processed/local_models_demo/authenticated/` storage. The
existing default config and Open Images config are not overwritten. All account
profiles prefer local Ollama by default; `local_models.enabled: false` or
`$env:AEGM_LOCAL_MODELS_DISABLED = '1'` explicitly disables model calls. Remove
that variable before testing models. No external fallback is configured.

The main status panel shows runtime/model availability, actual last operation,
digests and active index generation. Use **Refresh local model status** after
installing/updating models. Use **Rebuild local semantic index** when requested
or after changing the embedding model. Rebuild stages a complete new generation
and activates it atomically; failure retains the previous generation. Queries
never combine different model digests/dimensions. Previous generations are
retained and disk usage can grow with repeated rebuilds. Forgotten chains are
excluded from querying/index refresh; forgetting is reversible, not erasure.

After stopping Streamlit, clear the profile in that shell:

```powershell
$env:AEGM_CONFIG_PATH = $null
```

## Troubleshooting

| Symptom | Action / expected fallback |
| --- | --- |
| Ollama unavailable | Start the loopback server, check `ollama --version`, then refresh status; deterministic extraction/answers and lexical retrieval remain usable |
| Missing model | Run the explicit pull command yourself; the app never downloads it |
| Port already in use | Quit the tray instance before `ollama serve`; do not expose the daemon on a public interface |
| Slow cold start, timeout or out-of-memory | Close other apps; keep 0.6b, CPU and short context; measure Task Manager and diagnostics; timeout is configurable up to 120 seconds, not a quality fix |
| No semantic hit | Inspect last retrieval status, explicit entity/ref, threshold, margin and model digest; default thresholds are untuned, not validated accuracy settings |
| Dimension/version mismatch | Refresh model status then rebuild; stale vectors are not queried with the new model |
| Rebuild fails | Previous generation remains intact; use lexical fallback, resolve the model/setup issue and retry explicitly |
| Long text or model output refused | Chat is bounded to 6000 input characters, 2048 context tokens and at most 512 output tokens. Character count is not a tokenizer guarantee; conservative fallback may occur |
| Embedding input too long | Embeddings use `truncate:false`; model context overflow fails to lexical fallback rather than silently truncating source information |
| Model paraphrase rejected | Deterministic evidence-grounded answer remains. Source IDs/value/word checks are conservative, not proof of semantic correctness |
| Historical or conflicting answer remains templated | Intentional: temporal and uncertain outputs retain the authoritative deterministic response |
| No image understanding from Qwen | This is a text model. Photos use the existing local CV pipeline; the four-colour car head is not a general image model |

## Manual browser checklist — NOT PERFORMED by the implementation agent

Capture screenshots/logs using disposable data only. Never capture passwords,
login tokens or real private evidence. AppTest/protocol tests are not browser tests.

| Manual action | Expected behavior and evidence |
| --- | --- |
| Register/login in the new profile | Account workspace; capture local status/model digests and active fallback/actual method |
| Stop Ollama and Send a supported fact/question | Clear setup message, valid deterministic/lexical fallback, no crash or external API attempt |
| Restart Ollama and refresh status | Models detected; actual inference must still be established by an answered/probed operation |
| Send `I live in Bengaluru.`, `I enjoy tea.` and a project requirement | Automatic selection and evidence IDs; no Store click required |
| Send `I have an allergy to peanuts.` | Local candidate may be proposed; inspect exact quote, digest and unverified-candidate provenance. Failure/omission must be reported, not hidden |
| Send a hedge, negative statement, hypothetical and explicit `I do not use cloud APIs.` | No unsupported positive fact; bounded negative constraint retained verbatim; ambiguous/inferred proposals stay out of accepted memory |
| Start a new conversation and ask a stored fact | Correct same-account recall with original source conversation/message references |
| Ask `Which make is my laptop?` after a Lenovo brand fact | Compare with lexical baseline; inspect actual semantic status/score/digest. A fallback is not a semantic PASS |
| Add atlas deadline Nov 1 then Dec 1 with ordered event dates | Current Dec 1; previous Nov 1; as-of source event time preserved |
| Record first-car red → blue → black and a second car | Correct temporal chain, initial/previous/current answers and identity clarification when unspecified |
| Attach contrasting image to explicit car colour text | Contextual/non-supporting warning; human verification required; LLM cannot choose either value automatically |
| Resolve once with text and once with image in separate scenarios | Selected current state, original state and immutable audit with actor/time/rationale/evidence preserved |
| Upload unreadable/unrelated/ambiguous image | Valid text survives processing failure; unsupported image never proves object identity |
| Correct a fact and forget/restore an entity-attribute chain | History remains; forgotten chain is absent from lexical, semantic and generated answers; restore re-enables it |
| Rebuild, restart app and log back in | Durable accepted facts, provenance and matching persisted index generation remain |
| Change embedding model/version deliberately, refresh/rebuild | New digest/generation; no mixed dimensions or partially active index |
| Log out and use another account | No first-account memories, messages, images or index hits |
| Read a generated personal answer alongside its validated answer note | Citations/values agree; mark any semantic misstatement FAIL. The lexical guard cannot certify all language |

Real-model quality, resource sizing and these browser outcomes remain pending
until you execute and review them. No browser automation was run in this phase.
