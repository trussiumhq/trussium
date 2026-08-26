# Trussium provider-plugin template

This directory is a copyable starting point for a standalone Python provider
plugin. Copy it into a separate repository, rename the package, replace the
deterministic example transport, and publish it on its own release cycle.

The example implements the public `ChatCapability` contract and returns
provider-neutral JSON and streaming events without making network calls. It is
not dynamically loaded by Trussium. The application owner must explicitly
import and register the capability before composing the sealed registry:

```python
from trussium.capabilities import CapabilityRegistry
from trussium_provider_example import ExampleChatCapability

registry = CapabilityRegistry()
registry.register("chat.completions", ExampleChatCapability())
registry.seal()
```

Replace the example implementation with a real provider transport while
preserving normalized contracts, runtime-owned deadlines, cancellation,
stream cleanup, bounded errors, and privacy-safe logs. Follow the repository's
plugin and provider development guides and ADR-0008 before adding loading or
permissions behavior.

Run the template tests from this directory with `uv run pytest`.
