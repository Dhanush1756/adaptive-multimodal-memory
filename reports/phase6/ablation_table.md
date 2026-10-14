| System | Text | Image | Temporal memory | Evidence linking | Current QA (CSA) | Historical QA (HSA) | Initial | Identity | Evidence P/R | Unsupported | Schema | Visual P/FAR | Update acc. | Conflict F1 |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N_no_memory | - | - | - | - | 0.000 [0.00, 0.00] | 0.182 [0.08, 0.28] | 0.000 [0.00, 0.00] | 0.333 [0.33, 0.33] | 0.000/0.000 | n/a | 1.000 | n/a/0.000 | n/a | n/a |
| L_latest_value | yes | yes | latest only | limited | 0.833 [0.76, 0.91] | 0.182 [0.08, 0.28] | 0.000 [0.00, 0.00] | 0.333 [0.33, 0.33] | 0.469/0.429 | 0.324 | 1.000 | n/a/0.000 | n/a | n/a |
| B_naive_multimodal | yes | yes | no | no | 0.667 [0.58, 0.76] | 0.200 [0.10, 0.33] | 0.650 [0.45, 0.85] | 0.667 [0.67, 0.67] | 0.576/0.535 | 0.387 | 1.000 | n/a/0.000 | n/a | n/a |
| C_append_only_temporal | yes | yes | append-only | no | 0.833 [0.76, 0.91] | 0.727 [0.66, 0.82] | 0.750 [0.55, 0.90] | 0.333 [0.33, 0.33] | 0.765/0.731 | 0.260 | 1.000 | n/a/0.000 | n/a | n/a |
| E_no_provenance | yes | yes | adaptive | citations removed | 1.000 [1.00, 1.00] | 0.727 [0.66, 0.82] | 0.750 [0.55, 0.90] | 1.000 [1.00, 1.00] | 0.000/0.000 | 0.102 | 1.000 | 1.000/0.000 | 0.952 | 1.000 |
| E_no_visual_linking | yes | yes | adaptive | no cross-modal link | 0.889 [0.82, 0.96] | 0.727 [0.66, 0.82] | 0.750 [0.55, 0.90] | 1.000 [1.00, 1.00] | 0.827/0.833 | 0.184 | 1.000 | 1.000/0.000 | 0.905 | 0.000 |
| E_no_text_image_conflict | yes | yes | adaptive | conflict gate removed | 0.889 [0.82, 0.96] | 0.727 [0.66, 0.82] | 0.750 [0.55, 0.90] | 1.000 [1.00, 1.00] | 0.827/0.833 | 0.184 | 1.000 | 1.000/0.000 | 0.905 | 0.000 |
| E_proposed | yes | yes | adaptive | yes | 1.000 [1.00, 1.00] | 0.727 [0.66, 0.82] | 0.750 [0.55, 0.90] | 1.000 [1.00, 1.00] | 0.908/0.914 | 0.102 | 1.000 | 1.000/0.000 | 0.952 | 1.000 |

_Values are accuracies on the chosen split with 95% cluster-bootstrap CIs over scenarios in brackets. Update acc. and Conflict F1 are n/a for systems without an update engine._
