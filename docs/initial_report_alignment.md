# Alignment with the submitted NLP project report

## Purpose and source boundary

This document compares the implemented repository with the initial submitted report, **“Adaptive Evidence-Grounded Memory for Long-Term NLP Agents”** (`nlp_report (1).pdf`). The PDF is treated as the original proposal and literature review, not as executable instructions. Claims below are based on the current code, frozen Phase 4–6 evaluation artifacts, and the regression suite.

The project remains the same proposed system: an integrated NLP and computer-vision prototype whose central contribution is adaptive, evidence-grounded temporal memory. It has not been converted into a generic chatbot.

## Overall assessment

The implementation is **substantially aligned with the central research question**. It represents entity attributes as timestamped states, preserves superseded states, links text and image evidence, detects conflicts, retrieves by temporal intent, and answers from retrieved evidence. The controlled Track A evaluation also compares the proposed lifecycle with retrieval and memory baselines.

The alignment is **partial for the proposal's broad model and evaluation language**. The release evidence covers a constrained color domain and deterministic Light-mode computer vision. Transformer embeddings, CLIP, YOLO, and a trained intent classifier are optional paths; LLaVA is not implemented; real pretrained Track B inference and evaluation on public natural-dialogue benchmarks were not performed. These limits must remain visible in any submission.

## Requirement-to-implementation matrix

| Initial-report objective | Implementation evidence | Assessment |
|---|---|---|
| Store evolving memories instead of isolated facts | `src/memory/schema.py`, `state_tracker.py`, `update.py`, and `store.py` model timestamped states with `CURRENT`, `HISTORICAL`, `CONTRADICTORY`, and `RESOLVED` status plus `previous_memory_id`. | **Aligned** |
| Preserve historical information when facts change | State transitions retain old records and relink the chronological chain; regression tests cover red → blue → black and original/previous/current retrieval. | **Aligned** |
| Respect temporal validity | Event time is stored separately from ingestion order. As-of, current, previous, original, after-change, when, and history queries are supported. Late evidence is ordered by observation time. | **Aligned** |
| Handle contradictions and stale information | `src/memory/conflict.py` and `update.py` gate text–image and image–memory disagreements. Conflicts do not silently overwrite accepted state. Human verification can resolve a disagreement once. | **Aligned; human resolution extends the proposal** |
| Ground memory in source evidence | Text and visual evidence retain source session, source time, modality, association status, confidence, and state links. Answers return evidence records. | **Aligned** |
| Integrate textual and visual evidence in one memory structure | `src/multimodal/` fuses claims and image analyses into candidates and preserves image evidence with the associated state. Evidence stores event and ingestion time plus extractor/model identifiers. Unmatched images cannot establish or rewrite a state. | **Aligned in the controlled prototype** |
| Use named-entity and relation extraction | `src/nlp/ner.py` and `relation_extraction.py` extract tracked entities, explicit identities, color attributes, and state-changing relations. Text evidence identifies the rule extractor used. | **Partially aligned:** deterministic lexicons and patterns, not broad learned NER/RE. |
| Use contextual embeddings | Sentence-transformer support is optional; the frozen release uses a deterministic 256-dimensional hashing embedder. | **Partially aligned** |
| Use Transformer-based language models | Optional embedding/model hooks exist, while answer generation is deterministic by default and any LLM is limited to guarded rephrasing. | **Partially aligned; no LLM is required for validated results** |
| Extract temporal information | `src/nlp/temporal_extraction.py` and the query parser normalize dates and temporal intents; the memory engine uses event time for state validity. | **Aligned for supported templates** |
| Use CLIP or LLaVA for multimodal evidence | CLIP and YOLO adapters are optional. Light mode uses whole-image association, HSV color analysis, and color-histogram embeddings. LLaVA is absent. | **Partially aligned; real pretrained CV is pending** |
| Rank retrieval by context, time, and evidence | Hybrid retrieval combines semantic, entity, attribute, temporal, and confidence signals, then restricts evidence to selected records. | **Aligned within the supported schema** |
| Choose retain/update/supersede/reject on conflict | Update actions include `ADD`, `UPDATE`, `MERGE`, `IGNORE`, and `CONTRADICTORY`; status transitions preserve previous states. | **Aligned** |
| Isolate users and long-term sessions | Each Streamlit browser session gets a separate database/image namespace. File-backed stores persist when reopened directly. | **Partially aligned:** isolation is implemented, but the UI does not provide a durable namespace token for reconnecting to the same store after a full Streamlit server restart. |
| Compare with conventional retrieval/memory approaches | Frozen Phase 6 evaluates eight systems, including no-memory, latest-value, naive multimodal, append-only, and component-removal variants. | **Aligned for controlled Track A** |
| Evaluate long-term conversational and multimodal QA | The frozen test set contains 100 scenarios, 210 ingestion sessions, 265 questions, and 11 temporal/multimodal families. | **Partially aligned:** templated controlled data, not LoCoMo/MTPChat or hundreds of natural turns. |
| Reduce outdated or unsupported retrieval | Proposed-system current-state accuracy is 90/90, correct abstention is 20/20, and unsupported-answer count is 25/245 answered questions on frozen Track A. | **Supported by the frozen controlled evaluation** |

## Mapping to the four research gaps

1. **Relevance does not guarantee validity.** The retriever first resolves entity, attribute, identity, and temporal intent, then selects the state valid at the requested event time. Similarity alone does not select the final answer.
2. **Evolution is not the same as contradiction resolution.** Changes become ordered state transitions; same-time or conflicting multimodal claims are retained as explicit conflicts until policy or human verification resolves them.
3. **Evidence grounding must be part of memory.** Provenance is stored with the state and returned with answers. The no-provenance ablation ties answer accuracy but has zero citation precision/recall, showing that answer accuracy alone cannot establish grounding.
4. **Multimodal evidence must participate in the lifecycle.** Verified images can support a state, contextual images can cross-check it, and unrelated images are rejected. Removing visual linking or text–image conflict handling reduces frozen overall accuracy from 0.906 to 0.830.

## Frozen empirical evidence

The Phase 6 Track A test artifact is frozen at canonical LF-normalized SHA-256 `831449bb23989915803bf715071a656bf663c6c335320890b8340edfa9fadaf7`. Git's Windows checkout uses CRLF line endings, so hashing the raw working-tree bytes produces a different value even though the tracked content is unchanged. The proposed system answers 240/265 questions correctly (0.906; recorded 95% interval [0.874, 0.940]), with 90/90 current-state, 40/55 historical, 15/20 initial, and 30/30 identity questions correct. Evidence precision/recall are 0.908/0.914. Lifecycle correctness is 200/210, controlled conflict F1 is 1.0, visual-link precision is 1.0, and false-association rate is 0/15.

The strongest complete-memory baseline is append-only temporal memory at 195/265 (0.736). The proposed-minus-baseline difference is 0.170, with a recorded scenario-cluster bootstrap interval [0.1099, 0.2368]. McNemar values in the frozen report are descriptive because multiple correlated comparisons were made without multiplicity correction.

## Post-benchmark implementation status

After the Phase 6 artifacts were frozen, the UI gained image input in the Ask flow and a human-verification workflow for text–image disagreements. The original conflicting record is retained and becomes `RESOLVED`; choosing the image value creates the accepted temporal state, while choosing the memory/text value keeps the current state. A later report-alignment extension added distinct ingestion timestamps, extractor/model provenance, stable text evidence IDs, and direct conflict questions. These features are regression-tested but were not rerun as part of the frozen benchmark, so no Phase 6 metric is attributed to them. The final test count and environment are recorded in the implementation traceability report.

## Claims safe to use in the final paper

- The system implements adaptive, evidence-grounded temporal memory for a constrained multimodal entity-attribute domain.
- It preserves historical states and provenance while resolving current state by event time.
- It prevents contextual or unrelated images from silently rewriting memory.
- On the frozen deterministic Track A benchmark, it outperforms the specified no-memory, latest-value, naive multimodal, and append-only baselines.
- The repository provides reproducible annotations, commands, hashes, per-example outputs, error analysis, and regression tests.

## Claims that require more evidence

- General performance on unrestricted long-term conversation.
- Real-photo or pretrained CLIP/YOLO performance.
- Comparison with LoCoMo, MTPChat, or other public benchmarks.
- Superiority over production vector databases or general LLM-agent memory systems.
- Calibrated uncertainty, human-rated answer quality, or external replication.
- Any improvement from the post-Phase 6 human-verification workflow in benchmark metrics.
