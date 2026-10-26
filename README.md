# Adaptive Evidence-Grounded Memory

An integrated NLP + computer vision research prototype that remembers changing facts, preserves historical evidence, and answers questions across conversations in an isolated local account.

Text and uploaded photos enter the same temporal memory pipeline. The memory engine controls acceptance, conflict resolution, persistence and retrieval; an optional LLM assists extraction and conversation.

**Research/privacy upgrade:** optional local SSDLite multi-object observations,
versioned candidate provenance, account-level external-processing consent,
automatic-memory controls, export/erasure/retention and a separate encrypted
workspace profile are implemented. Read the [setup and manual checklist](docs/research_upgrade_setup.md)
and [privacy threat model](docs/privacy_threat_model.md). General-object accuracy,
caption-model inference and semantic retrieval quality are not established by
these reliability changes. Historical experiments remain unchanged.

## Quick start (Windows PowerShell)

Tested environment: **Windows / CPython 3.14.6 / Streamlit 1.58.0**. Direct dependencies are pinned in `requirements.txt`. Other environments are not claimed as verified.

```powershell
# First-time installation in a separate environment:
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Offline, deterministic chat interface:
.\.venv\Scripts\python.exe -m streamlit run app/account_app.py --server.address 127.0.0.1
```

Open the printed localhost address, register a demonstration account, then log in. New chats share only that account's memory. Accounts and evidence persist after restart when you use the same configuration and data directory.

### Optional conversational responses with Groq

```powershell
.\scripts\start_groq.ps1 -Clipboard
```

On first setup, copy a new private key when prompted, then press Enter without pasting into the terminal. A successful connection test stores the key encrypted with Windows DPAPI outside this repository. Subsequent launches reuse it without prompting:

```powershell
.\scripts\start_groq.ps1
# Rotate the saved key if needed:
.\scripts\start_groq.ps1 -ReplaceKey -Clipboard
```

Each person cloning the repository supplies their own key once. GitHub does not distribute your credential. A hosted deployment needs its own server-side secret configuration. `GROQ_API_KEY` overrides the saved key; `GROQ_MODEL` selects the model. There is no automatic paid-provider fallback. [Setup, privacy and troubleshooting](docs/groq_setup.md).

Groq receives conversation text and selected relevant memories. Images are processed locally. Missing credentials, quota limits and API failures retain deterministic responses and lexical retrieval. Free-tier quotas and access are controlled by Groq.
The server key/opt-in must now be accompanied by **Allow external Groq processing
for this account** in Privacy & data controls. It defaults off and can be revoked.

## Chat and remember

- Send text, optionally attaching a PNG/JPEG. Image-only uploads can retain local visual observations; the optional research detector produces multiple category/box predictions. These do not automatically establish physical identity or accepted long-term facts. Missing models and uncertain attributes remain unavailable/unknown.
- Enable **Remember this** before sending, or write **Remember that my laptop mood is happy.** Explicit requests receive selection usefulness **1.0**, even when automatic selection would skip the fact.
- Unrecognized explicitly requested content becomes a verbatim user note, not an independently verified fact. Uncertain statements saved this way remain notes.
- Ask **Show my pinned memories** or **Show my saved notes**. Both list visible pinned current facts and notes with evidence; conflicting values remain withheld pending verification.
- In **Manage memories**, pin an existing memory, unpin it, or forget/restore its complete fact history. Priority follows the evolving fact; it does not freeze an old value as current.

Accepted memories already persist without automatic expiry. Pins record your long-term preference and add a bounded semantic-ranking bonus when local semantic retrieval is available. They never raise evidence confidence, bypass identity checks, resolve disagreements, or restore forgotten information. Forgetting excludes memory from retrieval while preserving transcripts and evidence for audit. Do not enter credentials in chat; obvious credential-bearing explicit requests are not promoted to long-term memory.
Privacy controls also provide explicit full-workspace erasure and opt-in inactivity
expiry. Obvious sensitive turns are blocked before storage/API use; this is not
comprehensive PII detection. The encrypted profile uses separate new storage and
does not convert existing plaintext accounts. Account/login metadata, exports,
provider copies and backups have separately documented protection limits.

## Temporal and multimodal demonstration

Set **Message event date** in Settings before each observation:

| Date | Message |
|---|---|
| 2026-10-01 | My first car is red. |
| 2026-10-10 | My first car is blue. |
| 2026-10-20 | My first car is black. |

Ask **What color is my first car now?**, **What color was my first car previously?**, and **What color was my first car originally?** Expect black, blue and red. Add **My second car is white.** to check identity separation. Inspect Sources & evidence and Memory & evidence for timestamps, IDs and provenance.

Contrasting images are contextual/non-supporting where association is unverified. When the application flags a disagreement, explicitly select a value in human verification. Importance never chooses a value for you. [Current manual checklist](docs/explicit_memory.md); [full demonstration history](docs/final_demo_script.md).

## Models and limitations

- Deterministic NLP extraction works offline. Optional Groq candidate extraction and responses remain subject to application validation; assistant responses are not re-ingested as evidence.
- CV includes HSV heuristics and an **exploratory trained four-colour car classifier** from Open Images crops. Its small first-party artifact, manifest and metrics are included. This is not general image understanding, a trained object detector, or proof of physical identity. The Groq launcher or `config.openimages.yaml` selects this classifier; the default offline profile uses HSV.
- [Training and label limitations](docs/openimages_colour_training.md) distinguish caption-derived, assistant-reviewed labels from independent human gold.
- Optional Ollama embeddings are separate from chat generation and never download automatically. Without the runtime/model, retrieval remains lexical. [Optional local setup](docs/local_models_setup.md).
- Authentication and isolation support a local research prototype. Public production hosting requires a separate security and deployment assessment.

## Tests and research records

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
```

Tests use temporary storage. Automated API checks use mocks; native credential-cache tests require a working Windows user profile and may skip elsewhere. Streamlit AppTest checks are not a real-browser demonstration. [Latest verification report](docs/explicit_memory.md).

Frozen Phase 4-6 annotations and benchmark reports are retained unchanged. Reliability work does not imply improved benchmark performance. The [documentation index](docs/README.md) separates current guides from historical phase reports. The previous detailed README is preserved in `docs/archive/`.

```text
app/               Account chat UI and legacy demonstration UI
src/               NLP, CV, fusion, temporal memory, accounts and providers
tests/             Regression, integration and mocked API tests
config*.yaml       Explicit profiles; default is deterministic
scripts/           Windows secure Groq launcher
models/            Small reviewed classifier and provenance
data/annotations/  Frozen/reviewed fixtures, not user memory
reports/           Research records and historical results
docs/              Setup, demonstrations, architecture and research history
```

Databases, uploaded photos, raw datasets, credentials, encrypted keys, virtual environments, caches, logs, other model weights and the pre-existing `Microsoft/` directory are excluded from Git and are not deleted. See [LICENSE](LICENSE) and dataset attribution records before redistributing research assets.
