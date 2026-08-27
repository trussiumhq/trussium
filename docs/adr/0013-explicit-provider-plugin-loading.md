# ADR-0013: Explicit Provider Plugin Loading Boundary

**Status:** Accepted

**Date:** 2026-08-27

**Related Documents:**

- [Plugin Development](../PLUGIN_DEVELOPMENT.md)
- [ADR-0008: Community Provider Plugin Boundary](0008-community-provider-plugin-boundary.md)
- [ADR-0010: Explicit Provider Registry](0010-provider-registry.md)

## Decision

Provide `ProviderPluginSpec` and `ProviderPluginLoader` for application-owned,
allowlisted plugin factories. Before registration, the loader validates the
plugin API version, requested permissions, provider protocol, provider metadata
identity, and registry duplicate rules. Loading is deterministic and occurs
only for names explicitly requested by the application.

The loader does not scan packages, install dependencies, import configuration-
supplied names, verify signatures, or sandbox code. Those controls remain
required for any future automatic distribution loader.

## Consequences

Trusted applications get a single compatibility and permission gate while
retaining full control over imported code and granted capabilities. Plugin
packages remain independently versioned and directly importable, and unsafe
loading mechanisms remain excluded from the runtime entry point.
