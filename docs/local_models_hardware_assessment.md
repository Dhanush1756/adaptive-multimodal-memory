# Local-model hardware and compatibility assessment

Inspected before implementation on 18 October 2026. Existing uncommitted work is
preserved. No models or packages were downloaded, and no user database was opened.

| Item | Observed |
| --- | --- |
| OS | Windows 11, build 26300, x64 |
| Supported Python | Existing Anaconda CPython 3.14.6 |
| Logical CPU threads | 16 |
| Processor | AMD Ryzen 7 5700U with Radeon Graphics |
| CUDA | torch reports unavailable, zero CUDA devices; no GPU acceleration validated |
| Physical RAM | 16,473,051,136 bytes (15.34 GiB) |
| Available RAM at audit | 3,772,116,992 bytes (3.51 GiB); fluctuates with other applications |
| Free workspace drive | 127,787,683,840 bytes (119.01 GiB) |
| Dependencies | numpy 2.4.6, Pillow 12.3.0, scikit-learn 1.9.0, Streamlit 1.58.0, torch 2.14.0, torchvision 0.29.0 |
| Missing Python model packages | sentence-transformers, transformers, huggingface-hub |
| Ollama | Not found on PATH/default install path or process list; loopback API unavailable (`URLError`) |

Windows CIM hardware queries were denied by the environment. RAM/disk figures
come from installed psutil and Python disk usage, not an invented laptop model.
GPU acceleration must not be assumed from torch installation alone.

## Selected initial configuration

Use **Ollama**, with CPU-capable local HTTP calls from Python's standard library;
no Python Ollama/Transformers dependency is necessary. There is no established
Windows compatibility blocker: the official runtime supports Windows 10 22H2
and later. Installation and actual inference remain separate from compatibility
by specification. [Official Windows requirements](https://docs.ollama.com/windows).

Because available RAM is constrained, start with **qwen3:0.6b**, Q4_K_M, a
provider-listed 523 MB download. Use a 2048-token context, bounded output and no
thinking. A 1.7b Q4_K_M alternative is provider-listed at 1.4 GB; it is optional
after freeing memory and measuring real usage. These download sizes are not
runtime-memory measurements or quality guarantees. No larger model is selected.
[0.6b model](https://ollama.com/library/qwen3:0.6b),
[1.7b model](https://ollama.com/library/qwen3:1.7b).

Use a separate **all-minilm** embedding model through Ollama (provider-listed
46 MB, 512-token context). This avoids adding sentence-transformers to Python
3.14 without a tested compatibility study. It is a lightweight MiniLM-family
candidate, not a claim of numerical equivalence to the Hugging Face
`all-MiniLM-L6-v2` checkpoint. Its observed digest and dimensions must be recorded
when actually installed. [Model](https://ollama.com/library/all-minilm).

Only loopback endpoints are accepted. No cloud endpoint, API key, automatic
model pull, remote embedding service or automatic external fallback is used.
If unavailable, deterministic extraction/response and lexical retrieval remain
operational with explicit status. No model-performance or successful local
inference claim is justified until the runtime and weights are available and
inference has actually executed.
