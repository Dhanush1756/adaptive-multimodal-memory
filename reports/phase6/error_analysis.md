# Phase 6 error analysis

Every incorrect output, runtime failure, invalid schema, and incomplete citation is listed in the JSON artifact.

| System | Query issues | Session issues | Categories |
|---|---:|---:|---|
| N_no_memory | 245 | 210 | conflict_resolution: 10, entity_identity_resolution: 40, evidence_retrieval: 180, nlp_extraction: 20, nlp_extraction_or_lifecycle: 130, temporal_interpretation: 35, visual_evidence_association: 40 |
| L_latest_value | 170 | 210 | answer_generation: 10, conflict_resolution: 10, entity_identity_resolution: 40, evaluation_runtime: 5, evidence_retrieval: 100, nlp_extraction: 15, nlp_extraction_or_lifecycle: 130, temporal_interpretation: 35, visual_evidence_association: 35 |
| B_naive_multimodal | 154 | 210 | answer_generation: 10, conflict_resolution: 10, entity_identity_resolution: 30, evaluation_runtime: 5, evidence_retrieval: 81, nlp_extraction: 18, nlp_extraction_or_lifecycle: 130, temporal_interpretation: 45, visual_evidence_association: 35 |
| C_append_only_temporal | 105 | 210 | answer_generation: 10, conflict_resolution: 10, entity_identity_resolution: 40, evaluation_runtime: 5, evidence_retrieval: 40, nlp_extraction: 10, nlp_extraction_or_lifecycle: 130, temporal_interpretation: 35, visual_evidence_association: 35 |
| E_no_provenance | 245 | 10 | entity_identity_resolution: 20, evidence_retrieval: 190, nlp_extraction: 10, nlp_extraction_or_lifecycle: 10, temporal_interpretation: 25 |
| E_no_visual_linking | 60 | 20 | conflict_resolution: 10, evidence_retrieval: 25, nlp_extraction: 10, nlp_extraction_or_lifecycle: 10, temporal_interpretation: 25 |
| E_no_text_image_conflict | 60 | 20 | conflict_resolution: 10, evidence_retrieval: 25, nlp_extraction: 10, nlp_extraction_or_lifecycle: 10, temporal_interpretation: 25 |
| E_proposed | 40 | 10 | evidence_retrieval: 5, nlp_extraction: 10, nlp_extraction_or_lifecycle: 10, temporal_interpretation: 25 |

Categories are deterministic first-pass labels for review; they do not replace individual inspection.
