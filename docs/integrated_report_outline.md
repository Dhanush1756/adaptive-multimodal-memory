# Integrated NLP + CV report outline

This outline retains the submitted report's motivation and research question while reporting the implemented prototype in past tense.

1. **Title and abstract** — adaptive evidence-grounded memory; constrained integrated NLP/CV scope; principal Track A results.
2. **Introduction** — long-term agent memory, changing facts, stale retrieval, provenance and multimodal observations.
3. **Related work** — long-term memory architectures; temporal/context-aware memory; evidence-grounded conflict handling; multimodal memory.
4. **Research gaps** — relevance versus validity; evolution versus conflict resolution; evidence integrated with lifecycle; multimodal temporal grounding.
5. **Research question and contributions** — retain the original research question and list the implemented state chain, provenance, conflict policy, retrieval and evaluation.
6. **Integrated architecture** — multimodal input → NLP/CV extraction → unified candidate → validation → lifecycle → retrieval → grounded answer.
7. **NLP methodology** — normalization, rule-based NER/relation extraction, identity, temporal parsing, intent and grounded templates; label optional models accurately.
8. **CV methodology** — validation, detector adapter, bounding boxes, HSV/optional CLIP, embeddings, association classes and Light-mode limitations.
9. **Unified memory lifecycle** — schema, event versus ingestion time, atomic SQLite transitions, history, conflicts and human resolution.
10. **Retrieval and answering** — temporal intents, conflict query, state-scoped evidence, uncertainty and abstention.
11. **Experimental method** — frozen Track A data, systems, metrics, denominators, seed, hashes and statistical limits.
12. **Results** — QA, evidence, lifecycle, conflict and visual association; baseline and ablation tables.
13. **Error analysis** — parser coverage and evidence minimality failures.
14. **Post-benchmark implementation** — Ask-side images, human verification, ingestion/model provenance and conflict queries; regression evidence only.
15. **Limitations and threats to validity** — constrained domain, deterministic images, optional pretrained paths, environment sensitivity and pending manual validation.
16. **Conclusion and future work** — answer the research question conservatively; propose separately frozen Track B and public-dialogue validation.

The existing `docs/ieee_research_paper.tex` follows this structure and must keep frozen metrics separate from post-benchmark additions.
