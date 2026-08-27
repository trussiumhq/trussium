# API versioning policy

Trussium's public HTTP API uses an explicit major version in the path. The
current contract is `/v1`; all customer-facing capability, provider, health,
and discovery endpoints are rooted there.

Within a major version, additive response fields, new endpoints, and new
optional request fields are backward-compatible changes. Removing or renaming
fields, changing their meaning, changing status semantics, or making optional
inputs required requires a new major path (`/v2`) and a migration guide.

The runtime package, container image, Helm chart, and SDKs remain independently
semantically versioned. Their versions do not change the HTTP major version.
Provider and capability metadata versions describe adapter/contract compatibility
and are not substitutes for the HTTP path version.

Trussium does not silently negotiate versions, redirect between API majors, or
infer a version from headers. Clients should pin `/v1` and treat unknown fields
as forward-compatible. A future `/v2` will run as an explicitly reviewed,
parallel contract before `/v1` deprecation is considered.
