# Chat-focused authenticated interface

`app/account_app.py` now presents a single chat conversation with a bottom-pinned
native Streamlit composer. It accepts text and one PNG/JPEG attachment in the
same message. The previous Store/Ask dashboard forms are replaced by the existing
automatic `Conversations.chat` workflow. This is a UI change, not new extraction,
retrieval, model inference or memory policy. The separate legacy demonstration
and backend `remember`/`ask` APIs remain available.

The sidebar contains New chat, a visible conversation list, Settings (including
the observation's event date), Memory & evidence, Manage memories, conversation
details/summaries and login history. Titles derive from the first user message;
no API request generates a title. Evidence and activity expanders sit beneath the
latest answer. Stored user images render with association/support captions, only
when their paths remain inside the authenticated account's evidence directory.

Unresolved disagreements stay visible in the main conversation. Selecting either
value uses the existing authenticated resolution/audit path. Successful resolution
clears the verification panel and displays the persisted human-verification
message. It does not ask an LLM to choose. Corrections use an explicit chat message;
forget/restore controls remain in the sidebar. Logout is processed before chat
selectors and account content render. Closed-connection recovery is preserved.

`app/chat.css` supplies local, theme-compatible spacing, a centered transcript,
rounded user messages/composer, sidebar conversation styling and a welcome state.
Static styling contains no remote assets or interpolated user HTML. Streamlit
theme preferences are not overwritten. Responses remain non-streaming; this change
does not introduce token streaming or enlarge existing language/CV coverage.
Image-only inputs still need the existing engine's explicit entity/colour context
for memory acceptance. Unsupported inputs retain the existing clarification.

## Executed verification

`tests/test_account_ui.py` exercises the real native composer's text serialization
and is parameterized for text-selected (`red`) and image-selected (`white`)
verification. It covers register/login, one composer, no dashboard text area,
cross-conversation current questions, empty New chat, closed-store recovery with
identical memory/evidence records, deadline questions, source image previews,
invalid-image decoding with valid text preserved, visible disagreements, resolution
panel removal and persisted selected value, logout with chat content removed and
login persistence.

AppTest has no upload setter for this multimodal widget. Those upload checks
explicitly inject only the widget's returned payload while retaining the real
widget, Pillow decoding, HSV/fusion path, temporary SQLite and resolution engine.
They use a synthetic solid-white image, not pretrained inference or a real-photo
accuracy evaluation. External/local LLM access is disabled by test fixtures.
No browser automation or manual browser verification was performed.

Focused UI run: **2 passed in 16.01s** before final empty-chat/logout assertions.
Final run on Windows / Anaconda Python 3.14.6, Streamlit 1.58.0, pytest 9.0.3:

```powershell
& 'C:\Users\DHANUSH S\anaconda3\python.exe' -B -m pytest -q -x --tb=short
```

**290 passed, 0 failed, 0 skipped in 136.36s**, including both UI decisions and
the final empty-chat/logout assertions. Syntax, whitespace and scoped diff checks
passed. The six frozen annotation files, 14 historical benchmark reports, default
configuration/requirements and trained classifier match the recorded integrity
manifest. [Machine-readable test result](../reports/groq_v1/chat_ui_tests.json).

Application/model
dependencies, database schema/configuration, car-colour weights and frozen
benchmark artifacts are unchanged. No existing user database was accessed by
the coding agent and no API inference or Git mutation was performed.

## Manual visual checks (pending)

Refresh the running app; if necessary stop it with Ctrl+C and restart:

```powershell
.\scripts\start_groq.ps1 -Clipboard
```

Enter the replacement key privately at the prompt and log in to the same profile.
Check desktop and narrow-window layouts, light/dark theme, welcome screen,
sidebar conversation switching, Enter/Shift+Enter behavior and attachment button.
Send a text/photo pair, inspect image support labels and source timestamps, resolve
both decisions in separate examples, and confirm the panel disappears. Reopen the
same chat after restart. These visual/clipboard/browser interactions remain manual
checks; AppTest results do not establish pixel-level appearance or browser upload
behavior.
