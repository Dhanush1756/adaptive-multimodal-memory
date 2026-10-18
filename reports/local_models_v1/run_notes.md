# Evaluation run provenance

`run.json` is preserved as the initial diagnostic attempt. Its retrieval figures
are **invalid for baseline comparison**: the runner populated generic brand and
deadline facts through the legacy manual colour/project path, which does not
support those fields. Those expected facts were therefore absent.

The runner was corrected to populate identical source facts through the actual
automatic general-attribute path with model calls temporarily disabled, and now
asserts all eight expected states exist. `final_run.json` is the corrected run.
The initial extraction results were unaffected. Neither run represents actual
Ollama inference when its probe says BLOCKED. No frozen benchmark was changed.
