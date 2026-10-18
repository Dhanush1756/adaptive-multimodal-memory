# Phase 12: Browser Demonstration and Clean-Environment Reproducibility

Validated on October 17, 2026. This phase used only disposable browser profiles,
temporary application storage and a separate virtual environment. It did not open
or reset the configured user database, modify frozen Phase 4-6 data, install a
pretrained model, rerun the frozen benchmark, or claim new benchmark performance.

## Clean-environment result

A new virtual environment was created at
`%TEMP%\adaptive-memory-clean-py314` from the available CPython 3.14.6
interpreter. The existing Anaconda environment was not upgraded or changed.
Packages were installed only with:

```powershell
& "$env:TEMP\adaptive-memory-clean-py314\Scripts\python.exe" -m pip install -r requirements.txt
```

The first installation exposed a genuine reproducibility defect. Streamlit
1.58.0's broad transitive requirements selected Starlette 1.8.0 and Uvicorn
0.54.0. The tests passed, but a real Chrome page remained at Streamlit's loading
skeleton and the server emitted an ASGI response-order error. The supported
environment used Starlette 1.3.1 and Uvicorn 0.40.0. Those two versions are now
declared in `requirements.txt`. Reinstalling from that file produced a complete
browser render.

Final environment:

| Component | Version |
|---|---:|
| Python | 3.14.6 (Anaconda-packaged CPython used only as the venv base) |
| SQLite | 3.53.2 |
| NumPy | 2.4.6 |
| Pillow | 12.3.0 |
| PyYAML | 6.0.3 |
| scikit-learn | 1.9.0 |
| joblib | 1.5.3 |
| pytest | 9.0.3 |
| Streamlit | 1.58.0 |
| Starlette | 1.3.1 |
| Uvicorn | 0.40.0 |

`pip check` reported `No broken requirements found.` The full command

```powershell
& "$env:TEMP\adaptive-memory-clean-py314\Scripts\python.exe" -B -m pytest -q -p no:cacheprovider
```

completed with **193 passed in 36.56 seconds**, with no failures or skips.

## Genuine browser validation

The application ran from a disposable copy under `%TEMP%` so all SQLite files
and uploaded evidence stayed outside the repository and outside user storage.
Chrome 155.0.8059.82 rendered and interacted with the live Streamlit server over
its DevTools protocol. These were browser DOM/file-upload interactions, not
Streamlit AppTest or mocked UI calls.

| Check | Result | Observed behavior |
|---|---|---|
| Application render | **PASS** | Full Streamlit UI rendered after the Starlette/Uvicorn pins. |
| Red -> blue -> black | **PASS** | `ADD`, `UPDATE`, `UPDATE`; M001 <- M002 <- M003; red/blue historical and black current. |
| Current, previous, initial | **PASS** | Answers were black, blue and red respectively. |
| As-of October 15 | **PASS** | Returned blue from the October 10 event. |
| Full history | **PASS** | Returned red -> blue -> black with all three text evidence records. |
| Answer provenance | **PASS** | Browser output included stable `TXT_` IDs, source sessions, event time, ingestion time and `rules-v1`. |
| Contrasting white image | **PASS** | The image was labelled contextual and non-supporting; red/white disagreement requested human verification. |
| Text-selected resolution | **PASS** | Text/red was accepted; actor, UTC time, rationale and resulting state were shown in the audit. |
| Image-selected resolution | **PASS** | Image/white was accepted; current became white, original remained red and history retained both states. |
| Resolution evidence audit | **PASS** | Resolution, conflict, source/result state and original `TXT_`/`IMG_` evidence references were inspectable. |
| Resolved conflict status | **PASS** | No unresolved `(not applied)` warning remained after either choice. |
| First/second car separation | **PASS** | First car answered red, second car answered blue, and both appeared as separate selector entries. |
| Category-only car query | **PASS** | Abstained with `found: False` and asked which stored car identity was intended. |
| Invalid recovery code | **PASS** | Malformed code showed the generic invalid-or-missing error. |
| Unknown recovery code | **PASS** | Well-formed unknown code showed the same generic error. |
| Restart and recovery | **PASS** | Restart opened a fresh empty namespace with a different code; the saved code restored red/white history and its audit rationale. |
| Failed image decoding | **PASS** | Invalid PNG bytes produced a readable warning while the valid green text observation was added. |

Recovery codes are bearer secrets. The report and screenshot do not contain the
complete code used by the test.

Evidence files are under `reports/phase12/`:

- `temporal_browser_results.json`
- `identity_browser_results.json`
- `decode_failure_browser_results.json`
- `text_resolution_browser_results.json`
- `image_resolution_browser_results.json`
- `session_recovery_browser_results.json`
- `resolution_audit_browser.png` (recovery code redacted)

## Release assessment

The deterministic Light-mode Track A prototype is ready for an academic browser
demonstration in the tested Windows/Python environment. The demonstration can
claim integrated text/image ingestion, contextual visual evidence, explicit
human resolution, persistent temporal history, provenance and isolated session
recovery. Its visual path is HSV plus a colour-histogram embedding with a
whole-image fallback. It is not evidence of pretrained detection, CLIP inference
or real-photo accuracy.

Before Track B, create and freeze a licensed, identity-separated real-photo
dataset; document train/dev/test splits and labels; pin a separate model
environment; obtain approved YOLO/CLIP assets; evaluate detection, association,
colour accuracy, calibration, failure handling and end-to-end memory behavior;
and keep those results separate from the frozen Phase 4-6 Track A artifacts.

## Remaining limitations

- Recovery remains a local bearer-code mechanism and is not authentication for
  an exposed multi-user deployment.
- The Light-mode image result is a deterministic colour heuristic and must not
  be described as a trained or pretrained visual model.
- Browser validation covered the listed flows in headless Chrome. A projector
  or presentation-machine rehearsal is still advisable for font scaling,
  file-picker behavior and screenshot framing.
- Python 3.10.8 with Streamlit 1.31.1 remains unsupported; its AppTest lacks the
  required file-uploader interface and times out around application reruns.

The canonical LF-normalized Phase 4-6 annotation hashes were rechecked and are
unchanged:

- Phase 4 test: `5796204c446fc69a4d126d08c77a6de436fc281c3737fb72336facf4c99654bd`
- Phase 5 test: `b911d6b9993dee49b995c324eb29d53dc37bbd7e5a9b880da0f7484b54f5e019`
- Phase 6 development: `a05c713fad1d8c06159c1b6a53502ea8748ac1e76ebb3ce39225aaa91c2e02bc`
- Phase 6 test: `831449bb23989915803bf715071a656bf663c6c335320890b8340edfa9fadaf7`
