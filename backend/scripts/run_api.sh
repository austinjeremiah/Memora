#!/usr/bin/env bash
# Run the MEMORA API.
#
# Port 8000 is the documented default and matches the frontend's
# DEFAULT_API_BASE_URL. Before this script existed the port was undocumented
# and three different ones had been used across tests and docs -- pick one
# place for it to live and let everything else point here.
#
#   usage: scripts/run_api.sh [PORT]
set -euo pipefail

BACKEND="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8000}"
cd "$BACKEND"

echo "MEMORA API  ->  http://127.0.0.1:$PORT"
echo "store       ->  ${SIBYL_DB_PATH:-$(grep '^SIBYL_DB_PATH=' .env 2>/dev/null | cut -d= -f2- || echo '~/.sibyl-memory/memory.db')}"
echo "docs        ->  http://127.0.0.1:$PORT/docs"
echo

exec "$BACKEND/.venv/bin/uvicorn" memora.main:app \
  --host 127.0.0.1 --port "$PORT" --reload
