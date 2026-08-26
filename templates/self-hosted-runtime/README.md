# Self-hosted runtime template

This template runs the Trussium runtime as a hardened Docker Compose service.
It does not install the Trussium Operator or Helm chart.

## Start

```bash
cp .env.example .env
docker compose config
docker compose up -d
docker compose ps
```

The runtime listens on `http://127.0.0.1:9000`. The provider-free default is
useful for validating the deployment and health contract. To enable inference,
uncomment one provider configuration in `.env` and supply credentials through
your host or secret-management system.

## Verify and stop

```bash
trussium health --url http://127.0.0.1:9000
trussium capabilities --url http://127.0.0.1:9000
docker compose down
```

Set `TRUSSIUM_IMAGE` in `.env` or the shell to pin a released image instead of
the default `latest` tag. Never commit `.env` or provider credentials.
