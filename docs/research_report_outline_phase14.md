# Revised integrated research report outline

Retain the original submitted report's title, motivation, literature review,
four gaps and RQ1. This outline records the implemented scope; it does not
replace the frozen historical paper or invent external benchmark results.

1. **Abstract:** adaptive temporal evidence memory, constrained NLP/CV scope,
   persistent local accounts and controlled evaluation. Do not claim a trained
   real-photo model or Transformer generation.
2. **Introduction and related work:** retain the submitted framing. Verify
   bibliographic claims independently before publication; implemented features
   alone do not demonstrate novelty over the reviewed work.
3. **Research gaps and question:** use the four original gaps and RQ1, followed
   by the code/test/experiment mapping in the Phase 13-14 implementation report.
4. **System:** original NLP/CV -> fusion -> adaptive memory -> evidence retrieval
   architecture. Add the authenticated account boundary and distinct login,
   transcript, memory-event and pending-observation structures.
5. **NLP:** rule-based colour extraction and explicit project/model/requirement/
   preference patterns; multi-statement support only for that constrained grammar.
   Other narrative messages remain transcript-only. No learned NLP claim.
6. **CV:** HSV/histogram profile, trained-head interface and group-aware real-photo
   protocol. Keep actual model training and Track B results explicitly blocked.
7. **Memory and provenance:** event versus ingestion time, state chains,
   corroboration, cross-conversation source IDs, transactional updates,
   unresolved disagreement persistence and immutable resolution audit.
8. **Methods:** preserve Track A dataset and historical metrics; describe Track C
   authored scenarios and controlled Track D fixtures separately. State exact
   denominators, 120 intervening notes, test environment and service-reopen method.
9. **Results:** reference the actual versioned JSON artifacts. Conversation-set
   citation metrics must not be relabelled token-level evidence accuracy. Report
   regression counts separately from research benchmark accuracy.
10. **Ablations and external validity:** historical Track A comparisons retain
    their original scope. New real-photo and long-dialogue ablations, human-authored
    holdouts, calibration and public LoCoMo/MTPChat comparisons remain pending.
11. **Security, privacy and cost:** local password/session controls, account
    scoping, retention of corrections, per-query timing and small-workload storage.
    Discuss hosted identity, secure transport and erasure as limitations.
12. **Limitations and conclusion:** identify which gaps are addressed by system
    behavior, which have controlled experimental evidence, and which require
    real data or additional research. Do not claim unrestricted long-term memory.

## Core traceability

| Original objective | Function/path | Verification |
|---|---|---|
| Temporal validity | `MemoryEngine.process`, `select_states`, `Conversations._project_answer` | Existing temporal regressions; `test_project_temporal_multi_claim_and_intervening_turns`; Track C temporal questions. |
| Contradiction management | `fuse`, `MemoryAgent.verification_request/verify`, `Conversations.pending/resolve` | `test_authenticated_resolution_and_reopen`, `test_unresolved_observation_survives_restart_and_cannot_be_resolved_twice`; controlled Track D outcomes. |
| Evidence-grounded lifecycle | `Conversations._link/ask`, `evidence_items`, `MemoryStore.transaction` | `test_corroboration_does_not_reassign_original_evidence`, rollback tests and source-conversation evaluation. |
| Shared multimodal memory | `VisualPipeline.analyze`, `fuse`, original `MemoryEngine` | Existing multimodal suite; trained-head fixture integration; production real-photo evaluation blocked. |
| Persistent interactions | `Accounts.identity`, `Conversations` account database resolution | Cross-login reopen/isolation tests and authenticated UI AppTest. New browser rehearsal remains pending. |
