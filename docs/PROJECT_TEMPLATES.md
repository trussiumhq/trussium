# Project Templates

The repository includes a copyable [`self-hosted-runtime`](../templates/self-hosted-runtime/)
template for a private Docker Compose deployment. It uses the published
Trussium runtime image, listens on port `9000`, and starts provider-free so the
health and capability contracts can be verified before credentials are added.

```bash
cp -R templates/self-hosted-runtime my-trussium-runtime
cd my-trussium-runtime
cp .env.example .env
docker compose config
docker compose up -d
```

The template is a runtime deployment starter. It does not install or configure
the separate Trussium Operator or the independently versioned Helm chart.
