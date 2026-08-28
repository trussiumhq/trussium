# Chat provider fallback

Non-streaming chat requests use the configured provider router when registered providers advertise `chat.completions`. Providers are attempted in explicit priority order (or registry order), and the next provider is used only for transient rate-limit, timeout, connection, or upstream failures.

If no provider candidates are registered, the existing capability execution path remains unchanged. Streaming requests remain single-provider because replaying a partially emitted stream could duplicate client-visible events.
