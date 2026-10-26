# Research upgrade assessment — 26 October 2026

## Inspected baseline

The working tree was clean. Current accounts, SQLite schemas, temporal lifecycle,
Groq extraction/response adapter, local embedding index, visual fusion, Open Images
experiment and latest regression reports were inspected. The existing prototype
has 304 passing tests in its recorded environment; that is not a new-model score.

Hardware inspection: Windows 11 x64, CPython 3.14.6, 15.34 GiB physical RAM,
approximately 2.99 GiB available and 119.91 GiB disk free at inspection. Installed:
torch 2.14.0, torchvision 0.29.0, ultralytics 8.4.147, cryptography 49.0.0,
Streamlit 1.58.0, numpy 2.4.6. transformers, sentence-transformers and onnxruntime
are absent. No pretrained weights were found in the project's model directory.

## Model choices before installation or download

| Candidate | Scope / licence | Resource and compatibility assessment | Decision |
|---|---|---|---|
| YOLO11n | COCO 80 categories; Ultralytics AGPL-3.0 or enterprise | 2.6M parameters; approximately 5–6 MB weight download. Vendor CPU ONNX timing 56.1 ms is not this laptop's PyTorch latency. Installed Ultralytics/torch still require actual weight and inference verification. | Optional local-files-only adapter; no project relicensing and no automatic download. |
| torchvision SSDLite320 MobileNetV3 | COCO category subset; torchvision BSD code, dataset/weight terms must also be respected | Approximately 13.4 MB weights; installed torchvision. COCO labels include background/N/A slots, not 91 meaningful categories. | Alternative detector for a separately measured run; no claim of inference yet. |
| SmolVLM-256M-Instruct | Descriptions/VQA; Apache-2.0 | 256M-class model, roughly 0.5 GB 16-bit weights plus processor/runtime/activations. transformers absent; 3 GiB currently free leaves little headroom for concurrent services. CPU latency is unmeasured. | Optional cached-files-only description adapter, short generation, no sensitive-person inference or automatic fact promotion. Installation/download requires a separate setup step. |
| BLIP base | Captioning; model card BSD-3-Clause | Approximately 1 GB FP32 weights plus working RAM. transformers absent. Captioning is not identity proof. | Not the first candidate on available RAM. |
| Existing RGB histogram logistic regression | Four car colours only; first-party historical experiment | 2,557-byte artifact, already tested. No detector or general description capability. | Preserve artifact, parameters, reports and scope unchanged. |
| all-MiniLM-L6-v2 | Local text embeddings; Apache-2.0 model card | Approximately 90 MB FP32 weights plus runtime; sentence-transformers absent. Existing Ollama embedding integration is available but no runtime/model inference has been established. | Retain lexical fallback and versioned persisted index; do not label fallback results semantic performance. |

Sources checked on this date:
[YOLO11](https://docs.ultralytics.com/models/yolo11/),
[Ultralytics terms](https://www.ultralytics.com/license),
[SSDLite](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html),
[SmolVLM](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct),
[BLIP](https://huggingface.co/Salesforce/blip-image-captioning-base),
[Fernet](https://cryptography.io/en/latest/fernet/).
Sizes are estimates, not downloaded-byte measurements. No third-party benchmark
speed is a project result. No dependency installation or model download is implied.

## Smallest safe implementation stages

1. Add account-local privacy preferences and fail-closed external-processing gates;
   block obvious secrets/highly sensitive inputs before transcript promotion/API use.
2. Add user-controlled inspection/export, automatic-memory disable, explicit scoped
   erasure, retention and cache/index invalidation. Separate hiding from erasure.
3. Add an explicit encrypted workspace profile using established Fernet, externally
   supplied keys and in-memory SQLite with encrypted snapshots/evidence. Never
   silently convert or open a legacy plaintext workspace under this profile.
4. Version candidate extraction and record exact message references and spans;
   extend deterministic extraction without granting models database authority.
5. Add multi-object visual observations and optional local description processing.
   Do not promote detections/captions into same-object assertions or verified facts.
6. Test focused stages and full regression suite, verify historical hashes, document
   a separate human-reviewed new evaluation protocol and pending model setup.

## Key risks

Encryption does not protect a compromised running process; decrypted data exists
in RAM. A server-held master key is not end-to-end encryption. Account metadata
must be separately described. Key loss can make encrypted data unrecoverable.
Cloud storage durability, backups, deletion from third-party services and legal
compliance cannot be guaranteed by local code. UI browser verification and model
quality evaluation remain separate activities. Do not access existing user data,
rewrite historical metrics, commit, push or run a live browser during this phase.
