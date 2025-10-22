#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./test_pipeline.sh [MODE]
# MODE:
#   pipeline (default) - uses master pipeline mode
#   routing            - uses routing mode (only runs single dispatch test)

MODE=${1:-pipeline}
TASK_ID=${TASK_ID:-"TEST-$(date +%s)"}
API_URL=${API_URL:-"http://localhost:8000"}

run_task() {
  local payload="$1"
  local label="$2"
  echo ">>> Sending task $label ..."
  curl -s -X POST "${API_URL}/task" \
    -H 'Content-Type: application/json' \
    -d "$payload" | tee "/tmp/pipeline_${label}.json"
  echo # newline
}

if [[ "$MODE" == "pipeline" ]]; then
  echo "=== Pipeline mode: baseline (workers A/B/C) ==="
  docker compose up --build -d master-agent llm-gateway redis worker-a worker-b worker-c
  sleep 5
  run_task "{\"task_id\":\"${TASK_ID}-ABC\",\"objective\":\"安排週末在台北吃什麼\",\"context\":{}}" "abc"

  echo "=== Pipeline mode: with worker-d (finalizer) ==="
  docker compose up --build -d worker-d
  sleep 5
  run_task "{\"task_id\":\"${TASK_ID}-ABCD\",\"objective\":\"安排週末在台北吃什麼\",\"context\":{}}" "abcd"

  echo "=== Cleaning up ==="
  docker compose down
elif [[ "$MODE" == "routing" ]]; then
  echo "=== Routing mode test ==="
  export MASTER_MODE=routing
  docker compose up --build -d master-agent llm-gateway redis worker-a worker-b worker-c worker-d
  sleep 5
  curl -s -X POST "${API_URL}/dispatch" \
    -H 'Content-Type: application/json' \
    -d "{\"task_id\":\"${TASK_ID}-dispatch\",\"sub_id\":\"${TASK_ID}-S1\",\"command\":\"analyze\",\"data\":{\"objective\":\"routing test\"},\"context\":{},\"priority\":\"normal\"}" | tee "/tmp/routing_dispatch.json"
  docker compose down
else
  echo "Unknown MODE: $MODE"
  exit 1
fi

echo "Results stored under /tmp/pipeline_*.json (and routing_dispatch.json if routing mode)."
