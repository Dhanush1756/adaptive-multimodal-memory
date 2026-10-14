# Research presentation outline

This 12-slide outline uses only implemented behavior and frozen Phase 6 results. Visuals should be recreated from the recorded counts or captured from an actual demo; do not invent screenshots, model outputs, or graphs.

## Slide 1 — Title and problem

- **Main message:** Long-term agents need to preserve changing facts and their evidence across time.
- **Key content:** Project title; one-line definition; example `red -> blue -> black`; current versus historical questions.
- **Recommended visual:** A simple three-state timeline with text/image evidence icons and timestamps.

## Slide 2 — Motivation and simpler-system limits

- **Main message:** Chat history, latest-value storage, and similarity retrieval do not provide the same temporal state contract.
- **Key content:** Latest-value loses red/blue history; append-only logs do not resolve validity; naive multimodal retrieval can associate unrelated images.
- **Recommended visual:** Three columns showing transcript, latest-value cell, and adaptive state chain, with their supported query types.

## Slide 3 — Research objectives and questions

- **Main message:** The evaluation asks about temporal QA, evidence quality, lifecycle/conflict handling, identity, and abstention.
- **Key content:** Condensed RQ1–RQ5 and conservative claim boundaries.
- **Recommended visual:** Five question cards mapped to the primary metrics.

## Slide 4 — Proposed architecture

- **Main message:** Text and image observations become structured candidates before an independent memory engine updates SQLite.
- **Key content:** NLP extraction, CV analysis, fusion, lifecycle engine, store, temporal retrieval, grounded answer.
- **Recommended visual:** The end-to-end flow diagram from `docs/research_synthesis.md`.

## Slide 5 — Adaptive memory lifecycle

- **Main message:** State changes preserve rather than overwrite history.
- **Key content:** `ADD`, `UPDATE`, `MERGE`, `HISTORICAL`, `CONTRADICTORY`, `IGNORE`; event time versus arrival time; atomic chain rebuild.
- **Recommended visual:** A state-machine/table paired with a red-to-blue-to-black linked timeline.

## Slide 6 — Multimodal evidence and provenance

- **Main message:** An image can affect state only when one detected object verifies the claim entity.
- **Key content:** `verified`, `contextual`, `ambiguous`, `unmatched`; `supports_state`; source timestamps/session IDs; conflict remains outside the established chain.
- **Recommended visual:** Evidence card examples for verified association and rejected unrelated image. Label controlled detections clearly.

## Slide 7 — Temporal question-answering demonstration

- **Main message:** Query intent selects a state or chain and returns state-specific evidence.
- **Key content:** Current black, previous blue, original red, October 15 blue, full history; first/second car isolation; pre-history abstention.
- **Recommended visual:** Actual screenshots captured by `docs/final_demo_script.md`. Until captured, use a clearly labelled expected-output storyboard.

## Slide 8 — Evaluation methodology and baselines

- **Main message:** Phase 6 compares eight systems on identical frozen Track A inputs.
- **Key content:** 100 scenarios, 210 sessions, 265 questions, 11 families; no memory, latest value, naive multimodal, append-only, three ablations, complete system; scenario-cluster intervals.
- **Recommended visual:** Dataset-family distribution plus the eight-system comparison matrix. State that rendered images and controlled detections are not pretrained inference.

## Slide 9 — Results and ablations

- **Main message:** The complete system improved overall controlled temporal QA and provenance while retaining clear subgroup limits.
- **Key content:** 240/265 overall; 90/90 current; 40/55 historical; 15/20 initial; 30/30 identity; evidence P/R 0.908/0.914 over 245; lifecycle 200/210; correct abstentions 20/20.
- **Recommended visual:** Bar chart generated from recorded overall counts: no memory 20, latest 125, naive 141, append-only 195, complete 240 of 265. Add a provenance annotation: no-provenance also 240 answers but citation P/R is 0/0.

## Slide 10 — Controlled visual/conflict findings

- **Main message:** Association and conflict logic worked on controlled detector inputs, with no real-model claim.
- **Key content:** 30 visual TP, 0 FP, 15 TN; 10 conflict TP, 0 FP/FN; no-visual and no-conflict systems each 220/265 versus 240/265 complete.
- **Recommended visual:** Confusion-count tiles and a large “Track A controlled annotations” label.

## Slide 11 — Error analysis and limitations

- **Main message:** Failures are concentrated in specific rule-coverage gaps, and external validity remains untested.
- **Key content:** 15 `immediately preceded` errors; five ignored initial observations causing ten answer and ten lifecycle errors; citation-policy mismatch; templated data; colour-only scope; ordinal identity; pending manual UI; Track B unperformed.
- **Recommended visual:** Error taxonomy with exact counts and a boundary table: tested, controlled-only, pending, not performed.

## Slide 12 — Conclusion and future work

- **Main message:** The implemented contribution is an inspectable adaptive evidence-grounded temporal memory framework, validated in a controlled benchmark.
- **Key content:** Preserved history, event-time ordering, state-specific provenance, conflict isolation, explicit identity, grounded abstention; future new test set after language fixes, broader identity, calibrated confidence, licensed real photos, approved pretrained Track B, external replication.
- **Recommended visual:** Contribution stack leading to a short future-work roadmap. Keep standard NLP/CV/SQLite components outside the novelty claim.
