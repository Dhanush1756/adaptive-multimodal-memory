# Provider assessment — 18 October 2026

This supersedes the conversational-model recommendation in the local-model
assessment. Its hardware observations and executed diagnostic results remain
historical evidence. Inspected `LocalMemoryServices.extract/respond/retrieve`,
`AutomaticMemory.chat`, `SelectionPolicy`, `Conversations` authorization and
the authenticated Streamlit interface before editing. The existing model path
already treats extracted facts as unverified proposals. SQLite and deterministic
validation own acceptance, temporal updates, conflicts and evidence references.

| Candidate | Structured output | Image input | Published USD / million input, output tokens | Decision |
| --- | --- | --- | --- | --- |
| Groq `openai/gpt-oss-20b` | Strict JSON schema | Text only | 0.075, 0.30 on paid plan | Recommended initial candidate; listed in free-plan table |
| Groq `openai/gpt-oss-120b` | Strict JSON schema | Text only | 0.15, 0.60 on paid plan | Comparison only; never automatic fallback |
| OpenAI `gpt-5.4-mini` | Structured outputs | Text and images | 0.75, 4.50 | Current paid comparison only; not configured |

Sources checked: [Groq models](https://console.groq.com/docs/models),
[strict schema support](https://console.groq.com/docs/structured-outputs),
[20B capabilities](https://console.groq.com/docs/model/openai/gpt-oss-20b),
[OpenAI model specification](https://developers.openai.com/api/docs/models/gpt-5.4-mini).
The initially inspected GPT-4.1-mini and GPT-5-mini pages now mark those models
deprecated; they were excluded from the recommended current alternatives.
This is a targeted capability/cost comparison, not a quality benchmark or an
exhaustive ranking of models. Provider aliases and prices can change.

The [Groq free-plan table](https://console.groq.com/docs/rate-limits) currently
lists 20B at 30 requests/minute, 1,000/day, 8,000 tokens/minute and 200,000/day.
Actual limits are organization-specific. Public listing establishes free-plan
availability, not this user's account eligibility or a guarantee of free use.
Confirm Free plan and the model on the console Limits/Billing pages before opt-in.
The app cannot establish billing status from the chat response. Never enable a
paid plan to work around rate limiting. No provider/model fallback is permitted.

Illustrative paid-plan cost: 1,000 input + 500 output tokens = $0.000225 per
20B call, excluding any additional reasoning tokens. A turn can make extraction
and response requests; output budgets include reasoning and are not dollar caps.
Free-tier exhaustion must produce fallback, not an upgrade. No live API/model
inventory calls, credentials inspection, account eligibility check, model quality
evaluation or actual API inference was performed for this assessment.

Embeddings are independent: keep the existing loopback Ollama MiniLM adapter,
versioned account-local SQLite index and lexical baseline. The previous reviewed
diagnostic recorded lexical precision 4/4 and recall 4/9; local embedding inference
was unavailable. No semantic improvement is established. Groq chat is not an
embedding endpoint. No embedding API is enabled and no weights are downloaded.

Smallest changes: isolated standard-library Groq adapter; independent chat and
embedding clients in the existing service; bounded account-instance extraction
cache; advisory selection veto; provider-neutral provenance/status; offline
transport/integration regressions and setup/manual verification documentation.
Existing car classifier, frozen data, database paths and lifecycle remain intact.
