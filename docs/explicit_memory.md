# Explicit memory priority

## Behavior

The account chat's **Remember this** toggle applies to the next submitted user
message and then clears. A leading `Remember ...` or `Please remember ...`
instruction also requests importance. This does not endorse an assistant reply.

Explicit selection usefulness is 1.0. Confidence, identity and lifecycle gates
remain active. Recognized statements use the temporal engine; otherwise content
is saved as a verbatim user note with a distinct identity and
`user-requested-note-v1` extraction provenance. Notes are user assertions, not
independent verification. Obvious credential-bearing explicit requests are not
promoted; the original message still exists in the transcript.

Accepted memory persists without automatic expiry. A pin records preference,
not a new retention SLA. Optional semantic retrieval adds 0.05 to priority
ranking without overriding similarity thresholds, ambiguity, time or account
boundaries. Unpinning preserves states. Forgetting continues to exclude the
complete fact chain until restored.

`Show my pinned memories` and `Show my saved notes` are aliases listing visible
pinned current states and notes. Unresolved colour disagreements are withheld.
After human resolution, an explicit importance request on that observation
applies to the accepted state. Original conflicting evidence remains preserved.

## Storage

An additive `CREATE TABLE IF NOT EXISTS memory_priority_events` migration runs
at authenticated store initialization. It does not rewrite existing tables or
records. Events preserve memory ID, fact identity, enabled state, priority,
source message ID, actor and ingestion timestamp. Sidebar-only pins have an
empty source message reference. Event dates and evidence remain unchanged.
Equivalent repeated pins are idempotent. All writes participate in the enclosing
transaction. The Decisions tab shows priority history; Manage memories provides
pin and unpin controls.

## Browser checklist (pending for this change)

Use a new disposable account; do not reset an existing account.

1. Launch `python -m streamlit run app/account_app.py --server.address 127.0.0.1`.
   Register and log in. Capture startup and environment status.
2. Send `My laptop mood is happy.` normally: expect history-only. Enable Remember
   this and resend: expect saved/pinned, usefulness 1.0 and unchanged confidence.
3. Confirm the toggle clears. Enable it for `Bring the handmade folder to the
   Friday review`. Expect a verbatim-note acknowledgment. Ask `Show my saved
   notes`; capture original evidence ID, event and ingestion timestamps.
4. Repeat a recognized pinned fact: expect no duplicate state or priority event.
5. Enter first-car red, blue and black with ordered dates. Current, previous and
   original answers must be black, blue and red with preserved earlier evidence.
6. With Remember this enabled, attach a white image to a red-car statement.
   Inspect non-supporting/association warnings and human verification. For two
   distinct explicit identities, choose red once and white once; capture decision
   IDs, actor, rationale, timestamp, original evidence and priority history.
7. Add a second car. Confirm separate histories; an ambiguous `My car is black`
   request must not bypass identity clarification even when pinned.
8. Forget a pinned fact: listing and direct questions must exclude it. Restore
   and unpin; inspect events and confirm underlying history remains intact.
9. Restart using the same profile and log in. Expect persisted notes, states and
   importance. A second account must see none of the first account's memory.
10. Send valid text plus a corrupt image. Expect a warning with valid text
    retained. Capture screenshots/logs without private data or credentials.

## Executed checks

On 18 October 2026, Windows / CPython 3.14.6 / Streamlit 1.58.0 / pytest 9.0.3:

```powershell
python -B -m pytest -q -x --tb=short --basetemp=.pytest_cache/explicit-memory-full-20261018
```

**304 passed, 0 failed, 0 skipped in 171.38 seconds.** This used a new verified-
absent temporary directory in the normal Windows user-profile context, so all
six native DPAPI tests executed using disposable fixture credentials. Focused
explicit-memory and account AppTest coverage passed 10 tests in 35.45 seconds.

Eight explicit-memory regressions cover usefulness/confidence, persistence,
duplicate pins, unpinning, reversible forgetting, verbatim provenance, sensitive
content, account and entity isolation, temporal answers, conflict abstention,
atomic rollback and both human-resolution choices. Two account AppTest cases
also exercise the real toggle callback and its automatic reset. File upload
payloads in AppTest are injected; this is not browser upload verification.

The 22 recorded canonical hashes (Phase 4-6 annotations, historical benchmark
reports, default configuration and requirements) match the previous integrity
record. The trained classifier's binary SHA-256 also matches. No datasets,
benchmarks, model weights or dependency versions were changed by this feature.

No live-browser checks, live API calls, model downloads, dependency installs or
user-database operations were performed for this change. Public research
records, including original contributor names and machine paths, are preserved.
README navigation is simplified; research provenance is retained rather than
deleted. Git ignores private data, raw images, caches, Windows credentials and
the pre-existing Microsoft directory. The only model-weight exception is the
reviewed 2,557-byte first-party car-colour classifier used by the demo.
