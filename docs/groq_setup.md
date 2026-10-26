# Groq setup and manual demonstration

**26 October privacy change:** server credentials/opt-in are no longer sufficient
for account-content processing. Each account defaults to external processing off.
Enable **Allow external Groq processing for this account** in Privacy & data
controls and save preferences only after accepting the disclosure. See the
[protected-profile setup](research_upgrade_setup.md) and
[current implementation report](research_upgrade_report.md).

Read the [model/cost assessment](groq_assessment.md) and
[implementation and executed results](groq_implementation.md). Initial provider:
Groq, `openai/gpt-oss-20b`. This is an external API, not local inference or a model
trained by this project. Public model availability was checked; this account's
access, free-plan eligibility and live inference have **not** been tested.
Update: the user subsequently supplied a successful live probe log; see
[connection recovery evidence](groq_sqlite_recovery.md). No further live API calls
were made by the coding agent for the remembered-key change below.

## Secure server-side configuration (Windows PowerShell)

Convenience launcher: revoke any key shared in chat, create its replacement in
the Groq console, then run this command from the repository root. Enter the new
key only at the masked local prompt:

```powershell
.\scripts\start_groq.ps1
```

If masked-terminal paste appears to accept just one character, use:

```powershell
.\scripts\start_groq.ps1 -Clipboard
```

Wait for its prompt, copy the replacement key, return to PowerShell and press
Enter **without pasting**. This explicitly reads the clipboard privately and
reports only the number of characters received. Short input is rejected before
any request. The launcher never prints clipboard contents. It leaves the clipboard
unchanged; remove the key from your clipboard/history afterward if applicable.

The launcher finds a project `.venv`, then your Anaconda Python, then `python` on
PATH. No package installation or environment upgrade is automatic. On first setup
it makes one explicit real connection probe and starts Streamlit only on success.
After a successful test, it saves **Windows DPAPI-encrypted** key data at
`%LOCALAPPDATA%\AdaptiveEvidenceGroundedMemory\credentials\groq.dpapi`, outside
the repository. It never saves a plaintext key. Subsequent launches use the
remembered key without a prompt or startup probe; even `-Clipboard` will reuse it.
An existing `GROQ_API_KEY` environment variable takes priority and is not copied
to disk. Regular chat requests still consume provider quota.

It uses the separate Groq demo profile, opens no browser and restores the calling
shell's previous environment when it finishes. Enter at an empty masked prompt
cancels without a request. For another supported interpreter, pass
`-Python 'C:\path\to\python.exe'`. No execution-policy changes are made. If your
machine blocks scripts, use the manual commands below rather than changing
organization policy. Launcher control flow and real DPAPI encryption were tested
with disposable fixture keys and fake API/app processes. Actual user-key reuse and
browser startup still require the user's local launch.

After the next successful one-time setup, launch without entering the key again:

```powershell
.\scripts\start_groq.ps1
```

To rotate a revoked/expired key, remove the saved key, or avoid saving a newly
entered key for this launch:

```powershell
.\scripts\start_groq.ps1 -ReplaceKey -Clipboard
.\scripts\start_groq.ps1 -ForgetKey
.\scripts\start_groq.ps1 -ReplaceKey -NoSaveKey -Clipboard
```

Replacement is saved only after the connection test succeeds; a failed test
leaves an existing saved key unchanged. Removing it affects neither accounts nor
memory and does not remove a key supplied by your shell. `-NoSaveKey` does not
delete an older saved key. DPAPI is supported only with a working Windows user
profile; save failures never fall back to plaintext. The cache belongs to this
Windows account and should not be copied to another user/computer. Programs
running as the same Windows user can decrypt it. See
[Microsoft's DPAPI conversion documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/convertfrom-securestring).

## Sharing the repository with a friend

GitHub contains the source, not a shared Groq credential. The encrypted credential
is outside the project and `*.dpapi`, `.env` and Streamlit secrets are ignored.
Each friend supplies their own Groq key once, then reuses their own saved key.
They also need the declared Python dependencies installed; cloning alone does
not install Python, packages or excluded trained artifacts. For a fresh Windows
environment, the following are **manual setup commands**, not a clean-install
claim for this change:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\start_groq.ps1 -Clipboard
```

The previously supported exact Python is 3.14.6; `py -3.14` selects the installed
3.14 interpreter, whose patch version should be checked. The launcher prefers
this `.venv` on future runs. Missing optional CV weights retain the existing
fallback; to reproduce the trained car head, obtain the trusted model artifact
and verify the published hash in the training/release documentation. Never load
an untrusted joblib file. Frozen annotations/results remain in the repository.

For friends to use **your** Groq account without supplying keys, host the app and
configure `GROQ_API_KEY`, `AEGM_ALLOW_EXTERNAL_LLM=1`, `AEGM_LLM_PROVIDER=groq` and
`AEGM_CONFIG_PATH=config.groq.yaml` as server environment/secrets, with persistent
account storage. Your quota is then shared. Keep the key on the server and use
the app's account login. No hosted deployment or GitHub push is performed here.

Use the existing supported Python 3.14.6 environment. No additional pip packages
are needed. Do not upgrade Anaconda. From the project root:

```powershell
$projectPython = 'C:\Users\DHANUSH S\anaconda3\python.exe'
$env:AEGM_CONFIG_PATH = (Resolve-Path .\config.groq.yaml).Path
$env:AEGM_LLM_PROVIDER = 'groq'
$env:GROQ_MODEL = 'openai/gpt-oss-20b'
```

Before enabling requests, use the [Groq console](https://console.groq.com/keys)
to create a key and confirm Free plan, model permissions and the Limits page.
Do not enter a key in the browser UI, source code, chat, screenshots or shell
history. Enter it at the masked prompt:

```powershell
$groqSecret = Read-Host 'Groq API key' -AsSecureString
$groqPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($groqSecret)
try {
    $env:GROQ_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($groqPointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($groqPointer)
    $groqSecret.Dispose()
    Remove-Variable groqSecret, groqPointer
}
```

Environment variables are inherited by child processes and accessible to the
local account; they are not encrypted storage. Never print `GROQ_API_KEY` or a
full environment dump. `.env`, `.env.*` and Streamlit `secrets.toml` are already
ignored. This adapter reads the environment directly; it does **not** load `.env`
automatically. A deployment secret manager may inject the environment variable.

The following opt-in authorizes this running app to send content externally.
Only set it after accepting the privacy terms and verifying your plan:

```powershell
$env:AEGM_ALLOW_EXTERNAL_LLM = '1'
```

Optional explicit connection probe — **not executed during implementation**;
it makes one real inference request and consumes quota (may incur charges on a
paid account). It sends only the documented synthetic connection-test prompt:

```powershell
& $projectPython -B -m src.groq_provider --allow-live-request
```

Expected: `PASS: actual Groq inference` with numerical token usage; otherwise a
sanitized error and nonzero exit. The command checks an actual structured reply,
not merely key presence. Do not interpret a successful probe as extraction quality
validation. An authentication/model/schema error requires correcting settings;
the app never changes models/providers or upgrades the plan automatically.

Launch the authenticated application:

```powershell
& $projectPython -B -m streamlit run app/account_app.py --server.address 127.0.0.1
```

`config.groq.yaml` uses a separate `data/processed/groq_demo/authenticated`
account registry and per-user stores. It does not recover accounts from other
profiles. Keep this same profile after restart to reopen these demonstration
accounts. Register a disposable demo account; ordinary Send evaluates useful facts
automatically. The legacy `app/streamlit_app.py` remains deterministic and does
not use this authenticated provider integration. Model ID is server-configurable
through `GROQ_MODEL`; changing it requires app/workspace restart. Another model
must support the strict schema contract and be approved on your plan. The endpoint
is fixed HTTPS Groq to prevent a configuration typo leaking credentials elsewhere.

Stop Streamlit with Ctrl+C before clearing its inherited key. Clear this shell:

```powershell
$env:GROQ_API_KEY = $null
$env:AEGM_ALLOW_EXTERNAL_LLM = $null
```

To return to deterministic mode, restart without the opt-in. To explicitly use
the earlier local conversational adapter, select `config.local.yaml` and
`$env:AEGM_LLM_PROVIDER = 'ollama'`; no automatic switch occurs.

## Data, privacy and cost

Extraction sends the current text and up to 32 visible category/reference pairs
from **this account**. Response generation sends the question, selected memory
IDs/values/event timestamps, authoritative answer and up to four recent user
messages. The whole request is capped at 6,000 content characters and at most
512 completion tokens (including reasoning); oversized contexts fall back rather
than silently dropping essential evidence. No image bytes, passwords from the
login form, API keys, database files or other accounts' histories are supplied.
The transport refuses its configured API key if found inside prompt content.
This is not comprehensive secret/PII redaction: do not submit confidential text.

Conversation content and relevant memory text leave this computer and are subject
to [Groq's policies and data controls](https://console.groq.com/docs/your-data).
The provider describes exceptions for reliability/abuse logs up to 30 days and
offers ZDR controls. Verify your organization settings; do not claim unconditional
zero retention or fully local processing. Removing a local memory does not recall
content already sent to a provider. Existing transcripts/evidence are preserved
locally by the project's reversible-forgetting design.

There can be extraction and response calls in a turn. A bounded 64-entry cache
per authenticated workspace reuses identical extraction inputs/model/context;
date resolution and policy validation run again. Identity-context changes and
restart can cause a new call. This is not durable message-level idempotency or a
provider billing cap. Requests never retry automatically; 429/503 cooldown honors
`Retry-After` seconds or HTTP date; other failures back off 30 seconds. UI stays
responsive without sleeping through backoff. A manually repeated turn after a
timeout may incur another charge; the first request may have completed upstream.
Free quotas are organizational, not per local account.

Embeddings remain separate, optional local Ollama `all-minilm:latest`, using the
existing versioned account SQLite index. Follow only the embedding portion of
[local setup](local_models_setup.md) if you explicitly choose to install it.
There is no automatic download or remote embedding fallback. Without Ollama,
lexical retrieval works. Rebuild the local semantic index using its UI button
after installing/changing the embedding model. The four-colour Open Images car
head remains local and unchanged; this profile references its existing artifact.
Missing weights use the existing local fallback; no general visual recognition
or pretrained multimodal inference is claimed.

## Troubleshooting and pending manual checks

Missing opt-in/key: provider status explains setup and deterministic/lexical mode.
HTTP failures now include their numeric status and a locally authored explanation;
raw response bodies remain hidden. The PowerShell `throw` after a failed probe is
the launcher's intentional stop, not the underlying API error. Use the preceding
`Groq HTTP NNN` line to distinguish authentication, permissions, request/schema,
quota and service problems. A received character count proves input length only,
not that the key is valid. An explicit application User-Agent is sent with requests.
401/403: check the key/permissions privately. 404: check model ID and current model
availability. 429: wait for the cooldown and review console quota; do not enable a
paid fallback. Network/certificate/proxy errors: check access to `api.groq.com`;
the transport does not use environment proxies or disable TLS verification.
Invalid/truncated schema output: keep the deterministic result. The deliberately
small completion budget may be insufficient for a reasoning model or many facts;
actual inference is required before tuning it. UI status exposes method/model
and numerical usage, never raw provider errors or authorization headers.

All browser checks below are **NOT TESTED** in this phase. Use disposable accounts
and keep screenshots free of keys/passwords. A live provider-enabled demo consumes
quota; first validate with opt-in absent, then explicitly authorize provider use.

| Manual action | Expected result and evidence |
| --- | --- |
| Launch, register/login; inspect provider status without key | Clear missing-key/opt-in fallback, no crash. Capture status only. |
| After explicit opt-in and probe, send `Hello` | Conversational output or labelled deterministic fallback; model status shows the actual method. Capture turn/status, no quality claim from one greeting. |
| Send `My first car is red.` dated Oct 1, `I repainted my first car blue.` Oct 10, then black Oct 20 | Current black, previous blue, initial red; history and evidence retained. Ask each and capture Timeline/source IDs and timestamps. Historical answers intentionally remain deterministic. |
| Ask about a second car before and after storing `My second car is white.` | Unknown first, then white; first-car answers remain black. Capture both filtered histories. |
| Submit red text plus a contrasting white image | Local CV/contextual warning or uncertainty according to association confidence; model cannot resolve it. Capture provenance/association and pending conflict. |
| Resolve a linked high-confidence conflict choosing text; repeat separately choosing image | Only explicit human decision resolves it; audit retains actor/time/rationale/old evidence and resulting state. Capture both audits; model cannot click/choose. |
| Send `I have an allergy to peanuts.` | If extraction succeeds, candidate has exact quote, Groq/model alias, verified=false and passes policy; otherwise clearly labelled rules-only/history-only fallback. Inspect selection audit. |
| Repeat unchanged extraction context; inspect turn diagnostics | Cache hit when model/prompt/identity context matches; original event time is resolved per turn. No duplicate verified model evidence. |
| Forget a chain, ask again, then restore via UI | Abstention while hidden; reversible restoration; neither semantic retrieval nor model generation exposes hidden facts. Capture status. |
| Logout/restart same profile and login; log in as another account | Own evidence persists; other account cannot inspect prior history. Capture generic logged-out/new-account views. |
| Submit undecodable image with valid text; disconnect network/missing key | Existing text persists, decoding/provider failure visible and deterministic answers usable. Capture sanitized warning and memory evidence. |
| Inspect answer provenance | Original text/image IDs, source message/session, event and ingestion times retained; generated prose never becomes source evidence. Capture evidence expander. |

Offline regression command (never a live model test):

```powershell
& $projectPython -B -m pytest -q
```
