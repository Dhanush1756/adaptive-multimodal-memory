# Automatic general-claim memory: implementation and demonstration

Date: 18 October 2026. The [initial audit](automatic_memory_architecture_audit.md)
maps the submitted PDF and supplied diagram to actual functions and tests. The
[updated diagram](integrated_nlp_cv_architecture.md) retains the temporal memory
architecture. Pre-existing uncommitted Phase 13/14 and Open Images work is preserved.

## Implemented behavior

The authenticated app's primary **Message / Send** flow calls
`AutomaticMemory.chat` through `Conversations`. No Store click is needed for
normal supported facts. Every submitted user message is persisted in conversation
history and evaluated; assistant messages are not fed back as new user evidence.

The stages are explicit extraction, usefulness selection, supported image
processing/fusion, existing-state comparison, existing engine validation/lifecycle, account-local persistence,
query-time retrieval and deterministic evidence-grounded response. Unsupported
language remains transcript-only. Optional manual Store/Ask controls remain for
compatibility. No operational conversational LLM or open-domain learned extractor
is claimed; the interface discloses the deterministic fallback.

`src/memory/selection.py` separates extraction confidence from future usefulness.
Policy settings include `minimum_confidence`, `minimum_usefulness`,
`default_usefulness`, per-attribute usefulness and transient attributes. They can
be supplied under `automatic_memory` in an explicit profile;
`config.automatic.yaml` demonstrates the settings without modifying default
`config.yaml` or the Open Images profile. Scores are heuristic, not calibrated.

Policy outcomes are `promote`, `duplicate`, `history_only`, `reject` and `clarify`.
A duplicate with an explicitly associated colour image is evaluated as a
`crosscheck`, rather than discarded before CV. Promotion is a selection decision,
not proof that engine validation accepted it: the audit also records the actual
lifecycle action and resulting memory ID. Engine `ADD`, `MERGE`, `UPDATE`,
`HISTORICAL`, `CONTRADICTORY` and `IGNORE` retain their original meanings.

Questions, hedges, negation, greetings and unsupported prose do not become
asserted facts. Sensitive attribute names are rejected from automatic promotion;
their original messages remain in the transcript, so this is not a secret-storage
or encrypted-chat facility. Configurable low-utility transient attributes stay
in history. Ambiguous identities require an explicit reference. Duplicate accepted
facts do not add redundant long-term evidence; their new messages and selection
decisions remain inspectable.

## General entities and attributes

The authenticated engine now accepts arbitrary explicit entity and attribute
strings. The legacy Store/Ask demo and frozen evaluation retain their original
configured domain. Explicit supported forms include:

| Message | Structured interpretation |
| --- | --- |
| `My laptop brand is Lenovo.` | laptop / brand / lenovo |
| `My project named atlas deadline is 2026-12-01.` | project identity atlas / deadline / date value |
| `My document named thesis status is draft.` | document identity thesis / status / draft |
| `My event named conference location is Bengaluru.` | event identity conference / location / bengaluru |
| `Alice is my supervisor.` | current user / supervisor / alice |
| `I prefer tea.` | current user / preference / tea |
| `My mug named desk is green.` | mug identity desk / colour / green |

Multiple explicit sentences in one message can produce separate candidates.
Decimal values such as version `3.14` remain intact. A deadline/date-valued
attribute is not silently interpreted as the observation date. Other supported
event expressions use the existing temporal extractor.

This is extensible structured grammar, not arbitrary language understanding.
Category names and named references use single word/hyphen identifiers; general
coreference, arbitrary relationship inference, multi-valued preference sets and
unrestricted event extraction remain gaps. Several values of one attribute are
temporal alternatives, not a general knowledge graph. Negation is not represented
as a positive fact.

`MemoryAgent.remember(..., explicit_claim=...)` lets this reviewed extraction
path reuse the original image fusion and lifecycle without reparsing it as a
car-colour statement. Human verification now supplies an explicit confirmed claim
with the original identity rather than relying on the old noun lexicon. The
actor, selected value, original evidence and resolution audit remain separate
from automatic selection decisions.

Confirmed defects fixed while generalizing:

- `MemoryEngine` normalized non-colour values with colour aliases. It now applies
  those aliases only to `color`, preserving names such as model `Gold`.
- Absolute date extraction discarded the reference timezone, causing naive/aware
  datetime comparison failures for account as-of queries. It now preserves that
  timezone while leaving legacy naive reference behavior intact.
- The optional manual project/preference path could interpret a value such as
  model `Gold` as the colour of an unrelated recently mentioned car. Explicit
  non-colour facts now bypass that implicit colour context and use their own
  attribute path. A regression verifies the car stays red.
- Direct structured-claim/image calls could compare an arbitrary brand/model
  value with the image's colour. Fusion now keeps those image observations
  non-supporting with no colour-agreement score; colour-based verification is
  never offered as a choice for a non-colour attribute.

## Storage, isolation and retrieval

Account identity still comes solely from the authenticated token. Each account
has its own SQLite and image directory. Caller-supplied conversation IDs are
authorized against that account. The extension adds only
`memory_selection_audit` and `memory_visibility_events` with `CREATE TABLE IF NOT
EXISTS`; it does not rewrite states, evidence, transcripts or conflict resolutions.
New decisions and their source message links share the outer SQLite transaction
with state transitions. If persistence fails, it rolls back the transcript and
state changes and removes only newly created UUID evidence files from that attempt.

`_automatic_answer` performs explicit **lexical** entity/attribute matching and
uses existing temporal selection. It does not claim semantic retrieval. Unknown
attributes, unrelated named categories and ambiguous identities abstain. Relevant
colour queries reuse the original image/conflict-aware retriever where its parser
can resolve the identity. Pending text–image disagreements return `uncertain`.
Generic answers include selected state IDs, evidence IDs, event/ingestion times,
extractor and source conversation/message references. Current, original, previous,
history and supported as-of intents remain distinct.

The management panel accepts corrections as new explicit facts. **Forget from
retrieval** reversibly excludes the entire entity/attribute chain, including
historical states, from account-service retrieval; Restore re-enables it. It is
not physical erasure. Transcripts, original evidence, audit records and memory
inspection remain available to the same account. Direct low-level `MemoryAgent`
API access is outside this account-service visibility layer. Existing authenticated
API reopen/isolation tests pass; no real user's pre-upgrade database was migrated
or opened during development.

## Visual integration boundaries

The saved `openimages_car_colour_v1` model and its reports are unchanged. Its
explicit profile limits the trained head to cars and four training labels.
Other supported categories use available HSV processing; no new detector,
vision-language model, object re-identification or weights were installed.

A message with exactly one explicit colour claim can carry its photo through
the real existing `VisualPipeline` and fusion path. Detector-free evidence remains
contextual/non-supporting. Both human choices preserve original evidence and
history. An image with no safe explicit colour context, or several colour claims,
requests clarification and is not guessed to belong to the most recent object.
In this automatic flow such an unassociated upload is not persisted as accepted
visual evidence; the message and clarification decision are retained. Photos are
not interpreted as evidence of a brand, project deadline or document content.
General visual/document understanding is not implemented.

## Executed verification and separate evaluation tracks

Environment: Windows, CPython 3.14.6; existing pinned numpy 2.4.6, Pillow 12.3.0,
scikit-learn 1.9.0, joblib 1.5.3, PyYAML 6.0.3, Streamlit 1.58.0 and pytest 9.0.3.
No dependencies were installed and no clean-environment claim is added here.

The initial six regression tests failed before the new modules existed. The final
focused account/UI run passed **23 tests in 62.28 seconds**, including the manual
project/colour isolation regression. Subsequent fusion coverage passed **25 tests
in 19.66 seconds**, and the final automatic-flow plus UI check passed **10 tests
in 24.81 seconds** after simplifying user acknowledgements. The final full suite
passed **230 tests in 95.49 seconds**, with **zero failures and zero skips**.
Commands:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest tests/test_automatic_memory.py tests/test_accounts_and_conversations.py tests/test_account_ui.py -q
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest tests/test_automatic_memory.py tests/test_multimodal_evidence.py -q
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest tests/test_automatic_memory.py tests/test_account_ui.py -q
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m src.evaluation.automatic_memory --out reports/automatic_memory_v1/final_run.json
```

The final evaluation command was actually executed using temporary accounts,
temporary SQLite and generated solid-colour images. Its output already exists;
choose a fresh `--out` filename to repeat without overwriting it.

| Track | Actual evidence and boundary |
| --- | --- |
| A: Frozen deterministic benchmark | Phase 4–6 annotations and published results preserved; no replacement metrics attributed to this extension |
| B: Open Images car crops | Existing 23-image held-out study and model preserved; no retraining or new general-vision claim |
| C: Automatic selection | 20 assistant-authored diagnostic messages; 20/20 exact cases; precision 12/12, recall 12/12 accepted claims; no independent human annotation or statistical held-out split |
| D: Cross-conversation retrieval | One explicit project fact recalled in a new conversation and after SQLite reopen; source metadata present; a separate account cannot retrieve it or open its transcript |
| E: Temporal updates | 5/5 constructed current/previous/original/as-of/history queries; red → blue → black with late blue evidence; duplicate retry produces 0/1 extra states |
| F: Integrated images | Two generated-white-image diagnostics using actual HSV, one per human-choice branch; uncertain before resolution, selected current and red original afterward, one audit each; no pretrained or real-photo metric |

The policy-versus-promote-all diagnostic reports two unwanted promotions for
promote-all-extracted (sensitive and transient attributes); the history-only
baseline recalls 0/12 desired claims. These are illustrative diagnostic baselines,
not the frozen comparative systems or estimates of natural-dialogue performance.
Dataset SHA-256: `ebbfdee481b63c8da8351a8d4ffe000e3aa7c1d081d8b615c9cbda1b82b8abcc`.

`reports/automatic_memory_v1/integrity.json` records canonical LF comparisons
against Git HEAD for all six frozen annotation files and 14 historical Phase 4–6
report files: all matched. Default `config.yaml` and `requirements.txt` also
matched, and the Open Images model hash remained
`232658bc14429531eaaf5b3e4c86903ef1f4814d63f0d47f99edd0dd6170e62c`.
The final diff check passed, with only Git's LF/CRLF conversion warnings.

## Manual demonstration: NOT TESTED in a live browser for this change

Use a fresh disposable profile and new account, not an existing user's storage:

```powershell
$env:AEGM_CONFIG_PATH = (Resolve-Path config.automatic.yaml).Path
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -m streamlit run app/account_app.py --server.address 127.0.0.1
```

| Action in browser | Expected behavior / evidence to capture |
| --- | --- |
| Register a new disposable account and log in; leave Light mode enabled | Conversation Send flow; capture title and component status; do not record password/token |
| Send `Hello!`, then `Maybe my car is blue.` | Transcript retained, no accepted state; screenshot selection outcomes |
| Set message dates Oct 1/10/20; send `My first car is red.`, `I repainted my first car blue.`, `My first car is black.` | Automatic ADD/UPDATE, preserved predecessor chain; capture selection and memory panels |
| Send current, previous, original and history colour questions for first car | black / blue / red / full chronological chain; capture evidence IDs and both times |
| Send `My second car is white.`; query each explicit identity | Separate histories; ambiguous `my car` requests clarification |
| Send project named atlas deadline and laptop brand examples above | Independent arbitrary attributes; screenshot accepted structured states |
| Start a new conversation and ask the atlas deadline | Same account recalls it with original conversation/message reference |
| Attach a contrasting readable image to `My first car is black.` | Contextual/non-supporting cross-check warning and human review; current query uncertain until reviewed |
| Choose text with a rationale; repeat a disagreement and choose image | Both audits show actor, timestamp, original evidence and selected result; initial state retained |
| Upload an image without a safe explicit colour context | Clarification, no invented same-object association; unsupported image not promoted |
| Submit an unreadable file with valid explicit text | Decode warning; valid text still evaluated; capture warning and stored evidence |
| Forget an entity/attribute; query it, then Restore and query again | Abstain while excluded, supported answer after restore; transcript/audit retained |
| Submit a correction with a later event date | New state and previous state retained, not destructive replacement |
| Restart Streamlit and log back in; then test a separate account | Own history/accepted facts recover; second account sees none of the first account's evidence |

Capture only disposable data. AppTest exercises the actual Streamlit application
logic but is not a live browser. After stopping, clear the explicit profile with
`$env:AEGM_CONFIG_PATH = $null`. Prior browser evidence from another phase does
not verify this newly added flow.

## Remaining research gaps

Files changed for this task (separate from the pre-existing uncommitted work):

- `src/memory/selection.py`, `src/automatic_memory.py`: extraction, configurable
  selection, atomic automatic turns, lexical temporal retrieval and visibility.
- `src/conversations.py`, `app/account_app.py`: authenticated integration and
  ordinary Send, inspection, correction and reversible forget controls.
- `src/agent/reasoning.py`: explicit reviewed claims and identity-preserving human
  confirmations reuse the original multimodal lifecycle.
- `src/memory/update.py`, `src/memory/conflict.py`,
  `src/multimodal/fusion.py`, `src/nlp/temporal_extraction.py`: attribute-scoped normalization/conflicts and
  timezone-preserving absolute dates.
- `config.automatic.yaml`: an explicit disposable demonstration profile.
- `tests/test_automatic_memory.py`, `tests/test_account_ui.py`: nine new regression
  tests and extension of the existing authenticated AppTest.
- `data/annotations/automatic_selection_v1.json`,
  `src/evaluation/automatic_memory.py`, `reports/automatic_memory_v1/`: separately
  authored controlled diagnostics and two preserved executed runs.
- The audit, this report, architecture diagram, demo cross-reference and README:
  current behavior, reproducible commands and limitations.

A live conversational LLM, learned general extraction, unrestricted attributes
from free-form language, independently reviewed dialogue evaluation, calibrated
selection, natural-dialogue retrieval metrics and broader pretrained vision are
still unperformed. A provider-neutral LLM callable exists in the legacy answer
generator, but no provider is configured or exercised here; generic automatic
answers use deterministic evidence rendering. Broader model work requires a
separate compatibility/licensing/resource review; Python 3.14 and existing
uninstalled optional libraries cannot be assumed compatible. This phase does not
download or assert operational CLIP/YOLO/LLaVA inference.

No real-user database, frozen annotation, historical metric or Open Images model
artifact was intentionally changed. No commit, push, reset, clean or dependency
installation was performed.
