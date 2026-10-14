| System | Text | Image | Temporal memory | Evidence linking | Current QA (CSA) | Historical QA (HSA) | Time/Change QA | Timeline QA | Evidence P/R | Unsupported | Update acc. | Conflict F1 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| N_no_memory | - | - | - | - | 0.125 [0.00, 0.38] | 0.333 | n/a | 0.000 | 0.000/0.000 | n/a | n/a | n/a |
| L_latest_value | yes | yes | latest only | limited | 0.625 [0.25, 0.88] | 0.333 | n/a | 0.000 | 0.385/0.333 | 0.375 | n/a | n/a |
| B_naive_multimodal | yes | yes | no | no | 0.500 [0.12, 0.88] | 0.000 | n/a | 0.000 | 0.308/0.256 | 0.733 | n/a | n/a |
| C_append_only_temporal | yes | yes | append-only | no | 0.625 [0.25, 0.88] | 0.667 | n/a | 0.000 | 0.615/0.641 | 0.462 | n/a | n/a |
| E_no_provenance | yes | yes | adaptive | citations removed | 0.750 [0.38, 1.00] | 0.667 | n/a | 1.000 | 0.000/0.000 | 0.308 | 0.833 | 0.667 |
| E_no_visual_linking | yes | yes | adaptive | no cross-modal link | 0.625 [0.25, 0.88] | 0.667 | n/a | 1.000 | 0.615/0.692 | 0.385 | 0.833 | 0.000 |
| E_no_text_image_conflict | yes | yes | adaptive | conflict gate removed | 0.625 [0.25, 0.88] | 0.667 | n/a | 1.000 | 0.615/0.692 | 0.385 | 0.833 | 0.000 |
| E_proposed | yes | yes | adaptive | yes | 0.750 [0.38, 1.00] | 0.667 | n/a | 1.000 | 0.731/0.769 | 0.308 | 0.833 | 0.667 |

_Values are accuracies on the chosen split with 95% cluster-bootstrap CIs over scenarios in brackets. Update acc. and Conflict F1 are n/a for systems without an update engine._
