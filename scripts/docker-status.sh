#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -f "${PROJECT_ROOT}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_ROOT}/.env"
  set +a
fi

PORT="${PORT:-5001}"

cd "${PROJECT_ROOT}"
docker compose ps
echo
echo "Health:"
curl -fsS "http://127.0.0.1:${PORT}/api/health"
echo
