| System | Text | Image | Temporal memory | Evidence linking | Current QA (CSA) | Historical QA (HSA) | Initial | Identity | Evidence P/R | Unsupported | Schema | Visual P/FAR | Update acc. | Conflict F1 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N_no_memory | - | - | - | - | 0.000 | 0.333 | 0.000 | 0.333 | 0.000/0.000 | n/a | 1.000 | n/a/0.000 | n/a | n/a |
| L_latest_value | yes | yes | latest only | limited | 1.000 | 0.333 | 0.000 | 0.333 | 0.583/0.500 | 0.222 | 1.000 | n/a/0.000 | n/a | n/a |
| B_naive_multimodal | yes | yes | no | no | 0.500 | 0.333 | 0.500 | 0.333 | 0.500/0.417 | 0.571 | 1.000 | n/a/0.000 | n/a | n/a |
| C_append_only_temporal | yes | yes | append-only | no | 1.000 | 1.000 | 1.000 | 0.333 | 0.875/0.833 | 0.154 | 1.000 | n/a/0.000 | n/a | n/a |
| E_no_provenance | yes | yes | adaptive | citations removed | 1.000 | 1.000 | 1.000 | 1.000 | 0.000/0.000 | 0.000 | 1.000 | n/a/0.000 | 1.000 | n/a |
| E_no_visual_linking | yes | yes | adaptive | no cross-modal link | 1.000 | 1.000 | 1.000 | 1.000 | 0.958/1.000 | 0.000 | 1.000 | n/a/0.000 | 1.000 | n/a |
| E_no_text_image_conflict | yes | yes | adaptive | conflict gate removed | 1.000 | 1.000 | 1.000 | 1.000 | 0.958/1.000 | 0.000 | 1.000 | n/a/0.000 | 1.000 | n/a |
| E_proposed | yes | yes | adaptive | yes | 1.000 | 1.000 | 1.000 | 1.000 | 0.958/1.000 | 0.000 | 1.000 | n/a/0.000 | 1.000 | n/a |

_Values are accuracies on the chosen split with 95% cluster-bootstrap CIs over scenarios in brackets. Update acc. and Conflict F1 are n/a for systems without an update engine._
