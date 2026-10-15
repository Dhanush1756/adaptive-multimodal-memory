# Submitted-report implementation traceability

This audit uses the submitted report *Adaptive Evidence-Grounded Memory for Long-Term NLP Agents* as the research reference. The report's prose describes intended behavior; the repository code and executed tests determine implementation status. Frozen Phase 4–6 data and results remain historical artifacts.

Status meanings: **implemented** means code and regression evidence exist; **partial** means the constrained prototype implements part of the claim; **unverified** means an adapter exists without an executed experiment; **missing** means no implementation exists.

| Submitted-report requirement | NLP component | CV component | Current implementation | Status | Required follow-up | Verification |
|---|---|---|---|---|---|---|
| Adaptive memory rather than isolated facts | Claim/event extraction | Visual observation candidate | `memory/schema.py`, `update.py`, `state_tracker.py` maintain linked states and lifecycle actions | Implemented | Extend beyond color only after a versioned schema/evaluation plan | State-chain tests; lifecycle metric |
| Preserve current and historical truth | Temporal query parsing | Images remain attached to selected state | `temporal_retriever.py`; `previous_memory_id`; `CURRENT`/`HISTORICAL` | Implemented | Add uncertain-time semantics for equal/approximate dates | Red→blue→black tests |
| Event-time validity | Temporal extraction and as-of intent | Image event date supplied by observation | Event time is distinct from ingestion time; late evidence is backfilled chronologically | Implemented | UI namespace recovery after server restart | Late-arrival and persistence tests |
| Named entities and attributes | Finite lexicon, ordinal references, rule-based relation extraction | Detector labels map to tracked entities | `nlp/ner.py`, `relation_extraction.py`, `cv/detection.py` | Partial | Learned/open-domain NER and relation evaluation | NLP unit tests; entity-identity benchmark |
| Context and relationship extraction | Pronoun context and explicit identity references | Preferred entity constrains object selection | `MemoryAgent.context_entity*`, fusion precedence rules | Partial | General coreference and visual re-identification | Identity-isolation tests |
| Temporal language and question answering | Current, previous, original, after, when, history, evidence, as-of, conflict intents | Selected state's image evidence is retrieved | Query parser, temporal retriever, deterministic answer generator | Implemented for supported language | Expand paraphrase coverage | QA family accuracy and parser tests |
| Contextual embeddings | Optional sentence transformer; hashing fallback | — | `nlp/embeddings.py` reports active backend | Partial | Separately evaluate a pinned pretrained backend | Component status; Track A uses hashing-256 |
| Object localization | Text entity guides association | Optional YOLO adapter; bounding box retained | `cv/detection.py`, `visual_pipeline.py` | Unverified for release model | Approved weights and real-image annotations | Detection mAP/precision/recall when assets exist |
| Visual attribute extraction | Attribute schema defines color | HSV, optional CLIP/head, histogram embedding | `cv/attributes.py`, `cv/embeddings.py` | Implemented in deterministic Light mode; pretrained path unverified | Frozen real-photo Track B | Color accuracy and calibration |
| Unified text/image evidence | Text evidence ID, session, event/ingestion time, extractor | Image ID/path/box, event/ingestion time, detector/attribute/embedding methods | `schema.py`, `fusion.py`, SQLite JSON evidence | Implemented | Normalize existing legacy metadata where source is known | Unified-provenance regression test |
| Correct image/entity association | Explicit text identity and entity context | verified/contextual/ambiguous/unmatched association | Visual pipeline and memory gates | Implemented for supported identities | Instance-level re-identification | Association precision/FAR tests |
| Reject unrelated or ambiguous images | Query/claim context is preserved | Ambiguous/unmatched images cannot support state | `visual_pipeline.py`, `update.py` | Implemented | Real-image stress evaluation | Unrelated/ambiguous families |
| Evidence-aware conflict handling | Text claim confidence and value | Visual confidence, value and association | `conflict.py`, `update.py`; conflict records never silently overwrite state | Implemented | Calibrate thresholds on development data | Conflict F1 and regression tests |
| Human verification | Confirmation becomes a normal text observation | Conflicting image remains preserved | `MemoryAgent.verification_request/verify`; UI review control; `RESOLVED` status | Implemented after frozen benchmark | Multi-reviewer audit trail if required | Persistence and both-choice tests |
| Ask whether modalities disagree | Conflict query intent | Returns conflicting visual provenance | `Intent.CONFLICT`, temporal retrieval, grounded answer | Implemented in this extension | Add more paraphrases to versioned evaluation | Conflict-query regression test |
| Evidence-grounded answers | Deterministic templates and guarded optional rephrasing | State-scoped image retrieval | `answer_generator.py`, `image_retriever.py` | Implemented | Improve evidence minimality | Evidence precision/recall, unsupported rate |
| Uncertainty and abstention | Missing/ambiguous identity returns abstention | Conflicts return uncertain; unsupported images do not answer | Structured `answered`/`uncertain`/`abstained` response | Implemented | Confidence calibration | Abstention and conflict tests |
| Persistence and isolation | Session source retained | Images use session namespace | SQLite file stores; independent Streamlit namespaces | Implemented with limitation | Durable UI reconnection token | Reopen and two-session tests |
| Comparative evaluation | NLP and temporal QA metrics | Visual linking/conflict metrics | Frozen Track A: eight systems, 100 scenarios, 265 questions | Implemented for controlled data | Public dialogue and real-image studies | `reports/phase6/` artifacts |
| LLaVA or general vision-language reasoning | No dependency | No LLaVA adapter | None | Missing | Separate approved research phase only | No claim permitted |

## Architecture decision

The existing modular architecture already matches the submitted pipeline, so no second database, generic chatbot layer, or unrelated model stack was added. This extension strengthens the shared evidence representation and disagreement retrieval while preserving the same NLP → CV → fusion → validation → lifecycle → retrieval → answer path.

## Frozen versus new evidence

- Frozen Phase 6 results remain unchanged and continue to describe deterministic Track A.
- The ingestion/model-provenance fields and conflict-query intent are post-benchmark functionality.
- Their evidence is regression testing, not a new accuracy claim.
- Pretrained Track B, public-dataset evaluation, and browser-based manual validation were not performed in this extension.

## Executed verification

- Python 3.14.6, Streamlit 1.58.0, pytest 9.0.3: **185 passed, 0 failed, 0 skipped** in 30.32 seconds.
- Python 3.10.8, Streamlit 1.31.1, pytest 9.0.2: **178 passed, 7 failed** in 27.26 seconds. The failures are confined to Streamlit's older AppTest API: it lacks file-uploader automation and mishandles a formatted selectbox's internal value. This environment is not claimed as compatible.
- Focused changed-area run: **43 passed** for multimodal evidence, reliability, and Streamlit integration.
- No frozen benchmark was rerun and no new aggregate performance result is claimed.
