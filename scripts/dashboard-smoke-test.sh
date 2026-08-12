#!/bin/sh

set -eu

image="grafana/grafana:12.2.0@sha256:74144189b38447facf737dfd0f3906e42e0776212bf575dc3334c3609183adf7"
container="trussium-grafana-smoke-$$"
repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
response="$(mktemp)"

cleanup() {
    docker rm --force "$container" >/dev/null 2>&1 || true
    rm -f "$response"
}

trap cleanup EXIT INT TERM

docker run \
    --detach \
    --name "$container" \
    --publish 127.0.0.1::3000 \
    --env GF_AUTH_ANONYMOUS_ENABLED=true \
    --env GF_AUTH_ANONYMOUS_ORG_ROLE=Admin \
    --env GF_AUTH_DISABLE_LOGIN_FORM=true \
    --env GF_ANALYTICS_REPORTING_ENABLED=false \
    --env GF_ANALYTICS_CHECK_FOR_UPDATES=false \
    --env GF_SECURITY_DISABLE_INITIAL_ADMIN_CREATION=true \
    --mount "type=bind,source=${repository_root}/deploy/observability/grafana/dashboards,target=/var/lib/grafana/dashboards,readonly" \
    --mount "type=bind,source=${repository_root}/tests/fixtures/grafana/provisioning/dashboards,target=/etc/grafana/provisioning/dashboards,readonly" \
    --mount "type=bind,source=${repository_root}/tests/fixtures/grafana/provisioning/datasources,target=/etc/grafana/provisioning/datasources,readonly" \
    "$image" >/dev/null

port_mapping="$(docker port "$container" 3000/tcp)"
host_port="${port_mapping##*:}"
attempt=0

while [ "$attempt" -lt 60 ]; do
    state="$(docker inspect --format '{{.State.Status}}' "$container")"

    if [ "$state" != "running" ]; then
        docker logs "$container" >&2
        echo "Grafana exited before becoming ready" >&2
        exit 1
    fi

    if curl --fail --silent \
        "http://127.0.0.1:${host_port}/api/health" \
        --output "$response"; then
        break
    fi

    attempt=$((attempt + 1))
    sleep 1
done

if [ "$attempt" -eq 60 ]; then
    docker logs "$container" >&2
    echo "Grafana did not become ready within 60 seconds" >&2
    exit 1
fi

python3 -c \
    'import json,sys; data=json.load(open(sys.argv[1])); assert data["database"] == "ok"' \
    "$response"

for uid in trussium-runtime-overview trussium-runtime-logs trussium-runtime-traces; do
    attempt=0

    while [ "$attempt" -lt 30 ]; do
        if curl --fail --silent \
            "http://127.0.0.1:${host_port}/api/dashboards/uid/${uid}" \
            --output "$response"; then
            break
        fi

        attempt=$((attempt + 1))
        sleep 1
    done

    if [ "$attempt" -eq 30 ]; then
        docker logs "$container" >&2
        echo "Dashboard ${uid} was not provisioned" >&2
        exit 1
    fi

    python3 -c \
        'import json,sys; data=json.load(open(sys.argv[1])); dashboard=data["dashboard"]; expected=sys.argv[2]; assert dashboard["uid"] == expected; assert len(dashboard["panels"]) >= 6' \
        "$response" "$uid"
done

curl --fail --silent --show-error \
    "http://127.0.0.1:${host_port}/api/search?tag=trussium" \
    --output "$response"
python3 -c \
    'import json,sys; data=json.load(open(sys.argv[1])); assert {item["uid"] for item in data} == {"trussium-runtime-overview", "trussium-runtime-logs", "trussium-runtime-traces"}' \
    "$response"

if docker logs "$container" 2>&1 | grep -Eqi \
    'failed to save dashboard|failed to provision|dashboard provisioning error'; then
    docker logs "$container" >&2
    echo "Grafana reported a dashboard provisioning error" >&2
    exit 1
fi

echo "Grafana imported all Trussium runtime dashboards from ${image}"
