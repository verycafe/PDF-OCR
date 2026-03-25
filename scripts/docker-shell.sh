#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

if [ "$#" -eq 0 ]; then
  set -- app /bin/sh
elif [ "$#" -eq 1 ]; then
  set -- "$1" /bin/sh
fi

docker compose exec "$@"
