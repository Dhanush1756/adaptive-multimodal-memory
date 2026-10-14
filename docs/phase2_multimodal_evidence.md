# Phase 2 multimodal evidence contract

Each stored visual observation is tied to one memory state only through the
ingest operation that produced it.  It is never selected simply because it was
uploaded in the same session.

`VisualEvidence` records the image identifier and optional local path, the
source observation timestamp and session, detector label/bounding box and
confidence, the derived attribute value and confidence, and the image embedding.
It also records `association_status`:

* `verified` - exactly one detected object mapped to the claim entity was used.
* `contextual` - no detector result was available, so the image remains an
  observation submitted with this specific text claim.  It may provide a colour
  observation, but it is labelled as unverified in returned evidence.
* `ambiguous` or `unmatched` - the available detector output could not identify
  one object for the claim.  The image must not support or contradict the state.

The text claim supplies the entity, attribute, value and event time.  A memory
state supplies its status, start time, previous-state link, and state value.
Each text and visual source retains its own timestamp rather than inheriting a
later ingestion or state time.  Existing JSON evidence lacks the new fields and
therefore reads as `contextual`, preserving compatibility without inventing a
verification result.

During ingestion, fusion computes colour agreement only for `verified` and
`contextual` evidence attached to that same record.  An `ambiguous` or
`unmatched` image neither confirms nor conflicts with text.  This distinction is
returned to the UI and grounded answer so a visual claim is never represented as
detector-confirmed when it was not.

For questions, temporal retrieval first selects the applicable state or states.
`ImageRetriever.for_records` then retrieves visual evidence only from those
selected memory IDs.  The answer generator consumes those retrieval hits, keeps
their source timestamps and association status, and does not retrieve images
from another state merely because they share a session or entity.
