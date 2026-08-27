# Request validation refinements

Normalized capability requests use shared non-blank string validation for model
identifiers and user-provided text fields. Leading and trailing whitespace is
stripped; whitespace-only values are rejected before provider execution.

This applies consistently to chat, embeddings, moderation, image generation,
speech, translation, reranking, and video requests. List inputs validate each
individual item as well as the list's non-empty constraint.

Validation is local and deterministic. It does not contact providers, expose
rejected values in API error envelopes, or change provider error mapping.
