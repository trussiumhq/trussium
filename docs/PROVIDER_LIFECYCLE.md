# Provider lifecycle

Providers that own HTTP clients, connection pools, subprocesses, or other
resources can implement `ProviderService` and be composed through
`ProviderLifecycle`. Providers start in registration order, and a partial
startup failure rolls back already-started providers. Successful shutdown runs
in reverse order with the configured per-provider cleanup deadline.

The lifecycle coordinator is application-owned and operates only on providers
explicitly supplied before runtime startup. It does not load packages, perform
health probes, or expose credentials and provider payloads.
