# Routing metrics and trace linkage

Routing decisions now increment `trussium_routing_decisions_total` with bounded capability, provider, and outcome labels. When tracing is active, the current span receives the same routing attributes plus the attempt number. No model payloads, credentials, SDK text, or raw exception messages are recorded.
