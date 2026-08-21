# Python SDK

The Python SDK calls an existing Trussium runtime; it does not install or host one.

```python
from trussium.sdk import TrussiumClient

with TrussiumClient("http://127.0.0.1:9000") as client:
    readiness = client.readiness()
```
