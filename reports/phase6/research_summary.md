# Phase 6 comparison summary

Counts are shown as correct/denominator. Coverage is answered/all questions.

| System | Overall | Current | Historical | Initial | Identity | Evidence P/R | Coverage | Abstention correct | Unsupported | Lifecycle | Conflict F1 | Visual P/FAR | Schema | Errors (session/query) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N_no_memory | 20/265 | 0/90 | 10/55 | 0/20 | 10/30 | 0.000/0.000 | 0/265 | 20/265 | 0/0 | n/a | n/a | n/a/0.0 | 265/265 | 0/0 |
| L_latest_value | 125/265 | 75/90 | 10/55 | 0/20 | 10/30 | 0.469/0.429 | 170/265 | 10/95 | 55/170 | n/a | n/a | n/a/0.0 | 265/265 | 5/0 |
| B_naive_multimodal | 141/265 | 60/90 | 11/55 | 13/20 | 20/30 | 0.576/0.535 | 230/265 | 0/35 | 89/230 | n/a | n/a | n/a/0.0 | 265/265 | 5/0 |
| C_append_only_temporal | 195/265 | 75/90 | 40/55 | 15/20 | 10/30 | 0.765/0.731 | 250/265 | 10/15 | 65/250 | n/a | n/a | n/a/0.0 | 265/265 | 5/0 |
| E_no_provenance | 240/265 | 90/90 | 40/55 | 15/20 | 30/30 | 0.000/0.000 | 245/265 | 20/20 | 25/245 | 0.9523809523809523 | 1.0 | 1.0/0.0 | 265/265 | 0/0 |
| E_no_visual_linking | 220/265 | 80/90 | 40/55 | 15/20 | 30/30 | 0.827/0.833 | 245/265 | 20/20 | 45/245 | 0.9047619047619048 | 0.0 | 1.0/0.0 | 265/265 | 0/0 |
| E_no_text_image_conflict | 220/265 | 80/90 | 40/55 | 15/20 | 30/30 | 0.827/0.833 | 245/265 | 20/20 | 45/245 | 0.9047619047619048 | 0.0 | 1.0/0.0 | 265/265 | 0/0 |
| E_proposed | 240/265 | 90/90 | 40/55 | 15/20 | 30/30 | 0.908/0.914 | 245/265 | 20/20 | 25/245 | 0.9523809523809523 | 1.0 | 1.0/0.0 | 265/265 | 0/0 |

## Paired overall-accuracy comparisons against E_proposed

| Candidate | n | Candidate | Proposed | Difference | Discordant (candidate/proposed only) | McNemar exact p | Cluster-bootstrap CI |
|---|---:|---:|---:|---:|---:|---:|---:|
| N_no_memory | 265 | 0.075 | 0.906 | 0.830 | 0/220 | 0.000000 | [0.7954, 0.8648] |
| L_latest_value | 265 | 0.472 | 0.906 | 0.434 | 0/115 | 0.000000 | [0.3709, 0.4963] |
| B_naive_multimodal | 265 | 0.532 | 0.906 | 0.374 | 0/99 | 0.000000 | [0.3145, 0.4286] |
| C_append_only_temporal | 265 | 0.736 | 0.906 | 0.170 | 0/45 | 0.000000 | [0.1099, 0.2368] |
| E_no_provenance | 265 | 0.906 | 0.906 | 0.000 | 0/0 | 1.000000 | [0.0, 0.0] |
| E_no_visual_linking | 265 | 0.830 | 0.906 | 0.075 | 0/20 | 0.000002 | [0.0328, 0.127] |
| E_no_text_image_conflict | 265 | 0.830 | 0.906 | 0.075 | 0/20 | 0.000002 | [0.0328, 0.127] |

McNemar p-values are descriptive paired tests. Multiple systems and correlated metrics are compared; no multiplicity-adjusted significance claim is made.
