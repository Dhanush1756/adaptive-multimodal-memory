# Research upgrade setup and manual verification

Read [compatibility/model assessment](research_upgrade_assessment.md) and
[threat model](privacy_threat_model.md) first. No browser tests were executed for
this phase. Normal legacy profiles remain available and are not silently migrated.

## Protected local profile (PowerShell)

Use the tested CPython 3.14 environment and core requirements. cryptography 49.0.0
was already installed and exercised; no packages were installed during this phase.
For another environment, these are explicit setup commands, not a fresh-install
verification claim:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-privacy.txt
.\scripts\start_protected.ps1 -Python 'C:\Users\DHANUSH S\anaconda3\python.exe'
```

The launcher creates/reuses a Windows current-user DPAPI-encrypted data key at
`%LOCALAPPDATA%\AdaptiveEvidenceGroundedMemory\credentials\data-key.dpapi`.
It is separate from the Groq key and never printed or committed. The child app
receives `AEGM_DATA_KEY`; the calling environment is restored afterward. Do not
delete/replace this key to troubleshoot: losing it can make data unrecoverable.
DPAPI recovery depends on the Windows user/machine profile; arrange protected
backup/recovery separately before storing important data.

The profile uses new `data/processed/protected_demo/` storage. Register a new
demonstration account there. An account from another profile is not automatically
imported. Content and photo files are encrypted; registry usernames and login
metadata are not. Existing plaintext memory.db files are explicitly refused by
the protected profile; a reviewed copy migration is still future work.

## Optional general-object detector

Existing environment versions `torch==2.14.0` and `torchvision==0.29.0` imported and
ran CPU inference successfully. They are recorded in `requirements-research.in`;
a clean installation of this optional combination was not attempted.

The explicit downloader retrieves only the official 14,069,355-byte SSDLite file,
checks its published filename SHA prefix and refuses to overwrite a destination:

```powershell
python -m src.data.local_detector_setup
.\scripts\start_protected.ps1 -Python 'C:\Users\DHANUSH S\anaconda3\python.exe' -Research
```

The file already exists on this development machine; do not redownload over it.
Full SHA-256: `a79551df90c79834bcd3bb3845ef9d966b5449a3a9b2833ae8404778ca5d65d2`.
Weights are ignored under `models/local/`. The research profile uses its own
`data/processed/research_upgrade/` account storage. In Settings, **turn Light mode
off** to run cached detector assets. Missing packages/assets give a fallback,
not an implicit download. Keep Light mode on for deterministic testing.

SSDLite has COCO's 80 meaningful object labels; that is category vocabulary, not
80 categories validated by this project. Multi-object records preserve boxes,
scores, model hash and timestamps. They are unassociated observations and do not
automatically create facts about existing possessions. General-profile attributes
below the configured threshold remain unknown. The historical car-colour head
remains scoped to cars and its artifacts/results are unchanged.

## Optional Groq and consent

Without `-Groq`, the protected launcher disables external calls. To deliberately
reuse a separately configured environment/saved Groq credential:

```powershell
.\scripts\start_protected.ps1 -Python 'C:\Users\DHANUSH S\anaconda3\python.exe' -Research -Groq
```

No credential is prompted or invented. If absent, use the existing documented
Groq setup separately. After login, open **Privacy & data controls**, enable
**Allow external Groq processing for this account**, and save preferences.
Server opt-in alone no longer authorizes transmission of account content.
Disabling consent retains deterministic responses. No live Groq requests were
performed in this phase. The extraction schema is `candidate-memory-v2`, with
exact source-message/quote-span metadata and unverified model proposals.

## Optional descriptions and embeddings: not operationally verified

No large caption model or embedding model was downloaded. No transformers or
sentence-transformers package was installed. SmolVLM-compatible description
loading requires cached safetensors and processors, no remote code and no implicit
downloads. Set `cv.description_model_path` to approved local assets only after a
separate compatible environment/setup and resource check. The adapter is implemented,
but its actual caption inference and output quality remain **unverified**.

The existing Ollama embedding index retains model/dimension/version tracking and
lexical fallback. Actual MiniLM/Ollama semantic inference and comparative retrieval
quality remain unverified. Do not describe hashing or RGB histograms as semantic
model results. Consult `local_models_setup.md` for the earlier optional runtime.

## Verification commands

```powershell
python -B -m pytest tests/test_privacy_upgrade.py tests/test_research_upgrade.py -q
python -B -m pytest -q -p no:cacheprovider
python -B -m src.evaluation.research_upgrade --out reports/research_upgrade_reproduction/nlp_diagnostics.json
```

Use a fresh evaluation output directory; outputs are never overwritten. Optional
native DPAPI tests require Windows with a working user profile; actual new-model
quality is not established by mocked/unit tests. See the implementation report
for executed results and intermediate failures.

## Manual browser checklist — all pending for this phase

Use a new disposable account in the selected profile. Capture screenshots and
sanitized logs, never keys or private user material.

1. Start without Groq: verify login, plaintext/encrypted status and deterministic
   response status. With the research profile, turn Light mode off and verify
   `ssdlite` plus a model hash in status.
2. Upload an authorized multi-object photo without text. Inspect separate
   detections, source message, event/ingestion timestamps, unassociated identities,
   unknown attributes and local evidence preview. Expect no accepted memory state
   simply because the objects were detected.
3. Enter first-car red/blue/black with ordered dates. Verify current, previous,
   original and full history; add second-car facts and check isolation.
4. Use a contrasting image with a sufficiently confident colour result. Inspect
   contextual warnings; if disagreement is flagged, resolve using each value in
   separate examples and inspect original evidence and decision audits. Unknown
   colours must not be represented as a confident disagreement.
5. Test model absence/corrupt upload: valid text must survive, descriptions become
   unavailable/unknown, and no general-purpose inference claim appears.
6. Confirm account external consent defaults off even with a server key. Enable
   deliberately only if live API processing is approved; revoke it and verify
   deterministic fallback. The provider can retain previously transmitted data.
7. Submit a disposable secret-like/medical-like example. It must not enter history,
   memory or external processing. Do not use a real credential to test this.
8. Disable automatic memory; ordinary facts stay in history. Explicit Remember
   requests remain possible. Verify provenance and that importance does not raise
   factual confidence or resolve identity ambiguity.
9. Forget a fact and ask paraphrases: no answer may use its hidden state. Inspect
   index invalidation; restore explicitly to make it available again.
10. Export your data intentionally; inspect absence of filesystem paths, credentials
    and model vectors. Treat the exported personal text as sensitive plaintext.
11. In the disposable account only, type `DELETE MY STORED DATA` and erase. Relogin:
    expect no prior conversations/facts/summaries/visual observations. Inspect the
    cleanup count and confirm a second account remains intact.
12. Test opt-in inactivity retention on disposable fixtures; expiry is evaluated on
    interaction using ingestion time, not the observation's historical date.
13. Restart with the same data key/profile and verify persistence. A wrong key must
    fail closed; a second concurrently open protected workspace must be refused.

## New independent evaluation still required

Before a general-purpose model-quality claim, independently review a new licensed
image set with categories/boxes, optional attribute labels, lighting, occlusion,
multiple instances and unrelated-image cases. Freeze it before tuning. Compare
SSDLite with an explicitly licensed detector baseline and HSV/scoped colour-head
attributes. Measure detection precision/recall or mAP, attribute accuracy/unknown
coverage, false identity association, cold/warm latency and peak RAM. Captions need
human factuality/unsupported-attribute assessment. New NLP/retrieval examples need
independent review and an untouched split. Preserve every historical benchmark.
