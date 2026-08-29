# Provider policies and credential isolation

API-key identity bindings may optionally declare `allowed_providers`. The runtime filters provider selection and fallback attempts to that allow-list; an empty list preserves the existing unrestricted behavior.

Provider credentials remain process-owned `SecretStr` settings and are resolved during bootstrap. Identity bindings cannot supply, override, or observe credentials, and credentials are never included in context, logs, audit events, or exported usage. Hosted credential brokers and centralized policy management remain private integrations.
