#!/usr/bin/env bash
# Per-boot reconciliation for El Descentralizador's local services.
# Idempotent: safe to run on every environment start.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[start] Ensuring PostgreSQL 16 is running..."
sudo pg_ctlcluster 16 main start || true
for _ in $(seq 1 30); do
  if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
pg_isready -h localhost -p 5432

echo "[start] Ensuring 'app' role and database exist..."
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='app'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE ROLE app LOGIN PASSWORD 'app' SUPERUSER;"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='app'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE app OWNER app;"
fi

echo "[start] Ensuring Redis is running..."
if ! redis-cli ping >/dev/null 2>&1; then
  redis-server --daemonize yes --save '' --appendonly no
  for _ in $(seq 1 15); do
    if redis-cli ping >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi
redis-cli ping

echo "[start] Applying database migrations..."
set -a
# shellcheck disable=SC1091
. ./.env.example
set +a
uv run alembic upgrade head

echo "[start] Environment ready."
