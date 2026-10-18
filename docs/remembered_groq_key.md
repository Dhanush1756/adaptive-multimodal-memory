# Remembered Groq credentials and repository sharing

The Windows launcher now reuses credentials in this order: an existing process
`GROQ_API_KEY`, then a DPAPI-encrypted saved key, then a one-time private prompt.
A newly entered key is checked with the existing explicit probe and saved only on
success. A configured/saved key starts the app without a prompt, clipboard read or
extra startup inference request. Launching the Groq profile still opts this running
app into sending text/context externally; ordinary requests consume provider quota.

```powershell
# One-time setup; enter the replacement key privately when prompted:
.\scripts\start_groq.ps1 -Clipboard
# Later launches:
.\scripts\start_groq.ps1
# Rotate or remove the remembered key:
.\scripts\start_groq.ps1 -ReplaceKey -Clipboard
.\scripts\start_groq.ps1 -ForgetKey
```

Encrypted data is written to
`%LOCALAPPDATA%\AdaptiveEvidenceGroundedMemory\credentials\groq.dpapi`.
It is outside the repository; `*.dpapi` is also ignored as defense against accidental
copying into Git. Nothing saves plaintext to `.env`, source, logs or browser state.
The [native Windows mechanism](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/convertfrom-securestring)
uses DPAPI without a supplied encryption key. It requires the normal Windows user
profile; it is not a portable secret for friends or a defense against programs
already running as the same Windows user. No other Windows account was exercised
experimentally in this phase.

`scripts/groq_credentials.ps1` isolates encrypted reads and atomic writes. New
ciphertext is prepared in a uniquely created temporary file, then moved/replaced;
only that operation's own temporary file is cleaned up. A failed provider probe
does not overwrite the existing saved key. PowerShell 5.1's null-to-empty-string
coercion required `[NullString]::Value` for atomic replacement's optional backup
path; the replacement test found this issue before completion. Read/decrypt/save
failures expose local messages, never plaintext/ciphertext/provider bodies.
`-NoSaveKey` preserves a session-only option, and `-ForgetKey` removes only the
fixed credential file, not shell credentials, accounts, databases or other files.

No real key was read, saved or replaced by the coding agent. The next successful
one-time setup by the user will populate their own credential cache. There is no
additional API call, installation, browser validation, database migration, model
change, GitHub push or hosted deployment in this change.

## A friend's setup

Cloning the source does not install dependencies or supply Groq access. A friend
needs the declared Python environment/packages and their own key once. The
launcher prefers a project `.venv`, then the user's Anaconda, then Python on PATH;
`-Python` still permits an explicit interpreter. A free-tier account must remain
within its actual provider quota. Excluded car-head weights must be obtained from
a trusted artifact source to reproduce that classifier; missing optional assets
retain the existing deterministic fallback.

To share one Groq credential without asking friends for a key, host the application
and inject the key as a server-side environment/secret. Users then access the hosted
app's account login, sharing the provider quota. Do not distribute the key through
GitHub. Hosting and persistence setup have not been performed. See
[complete setup commands](groq_setup.md#sharing-the-repository-with-a-friend).

## Actual checks

Native DPAPI cannot encrypt under this tool sandbox's impersonated profile, so the
initial focused check failed before a cache could be saved. The first normal-profile
pytest attempt also encountered the sandbox-owned default temp-folder ACL. Tests
were then run in the normal Windows profile with a new verified-empty workspace
test directory. No pre-existing folder was reset or cleaned.

After the atomic replacement fix, **six focused tests passed in 38.97s** on Windows
PowerShell 5.1.26100.9711. They use real native encryption/decryption and disposable
keys/profiles. API probing and app launch are stubbed, and prompt/clipboard functions
are mocked so a repeated prompt or real clipboard access fails the reuse test.
They verify exact encryption round trip, no plaintext fixture key in output/file,
reuse without another API probe, successful replacement, failed replacement retaining
the old ciphertext, removal scoped to the cache, environment priority/configured
model preservation, opt-out from saving and corrupt-cache errors without requests.
The process profile prerequisite is checked independently; unsupported/sandboxed
contexts report explicit skips rather than claiming genuine encryption worked.

Final full suite in the normal Windows profile: **296 passed, 0 failed, 0 skipped
in 166.93s**, using Anaconda Python 3.14.6 / Streamlit 1.58.0 / pytest 9.0.3.
Actual command:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q -x --tb=short --basetemp='.pytest_cache\groq-persistent-full-20261018'
```

That test directory was verified absent before execution. Scoped diff checks,
Python/PowerShell syntax and new-file whitespace checks passed. Frozen data,
historical reports, configuration/requirements and trained classifier retain their
recorded hashes. [Machine-readable result](../reports/groq_v1/remembered_key_tests.json).
