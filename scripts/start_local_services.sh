#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$(git rev-parse --show-toplevel)}"
RUN_DIR="${RUN_DIR:-$ROOT/.codex/run}"
BACK_PID_FILE="${BACK_PID_FILE:-$RUN_DIR/backend.pid}"
FRONT_PID_FILE="${FRONT_PID_FILE:-$RUN_DIR/frontend.pid}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

port_listeners() {
  local port="$1"
  lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null || true
}

describe_port_listener() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

pid_is_running() {
  local pid="$1"
  kill -0 "$pid" 2>/dev/null
}

terminate_pid() {
  local pid="$1"
  kill "$pid" 2>/dev/null || true
}

force_terminate_pid() {
  local pid="$1"
  kill -9 "$pid" 2>/dev/null || true
}

sleep_for_shutdown() {
  sleep 1
}

wait_for_port_release() {
  local port="$1"
  local attempts="${2:-3}"
  local remaining="$attempts"

  while (( remaining > 0 )); do
    if [[ -z "$(port_listeners "$port")" ]]; then
      return 0
    fi

    sleep_for_shutdown
    remaining=$((remaining - 1))
  done

  [[ -z "$(port_listeners "$port")" ]]
}

stop_tracked_process() {
  local pid_file="$1"
  local port="$2"
  local pid=""

  if [[ ! -f "$pid_file" ]]; then
    return 0
  fi

  pid="$(cat "$pid_file" 2>/dev/null || true)"
  rm -f "$pid_file"

  if [[ -z "$pid" ]]; then
    return 0
  fi

  if pid_is_running "$pid"; then
    terminate_pid "$pid"
  fi

  if wait_for_port_release "$port" 2; then
    return 0
  fi

  if pid_is_running "$pid"; then
    force_terminate_pid "$pid"
  fi

  wait_for_port_release "$port" 1 || true
}

ensure_port_available() {
  local port="$1"
  local listeners

  listeners="$(port_listeners "$port")"
  if [[ -z "$listeners" ]]; then
    return 0
  fi

  echo "端口 $port 已被其他进程占用，未自动终止该进程。" >&2
  describe_port_listener "$port" >&2
  return 1
}

cleanup_started_processes() {
  rm -f "$BACK_PID_FILE" "$FRONT_PID_FILE"
  [[ -n "${BACK_PID:-}" ]] && kill "$BACK_PID" 2>/dev/null || true
  [[ -n "${FRONT_PID:-}" ]] && kill "$FRONT_PID" 2>/dev/null || true
}

main() {
  mkdir -p "$RUN_DIR"

  stop_tracked_process "$BACK_PID_FILE" "$BACKEND_PORT"
  stop_tracked_process "$FRONT_PID_FILE" "$FRONTEND_PORT"

  ensure_port_available "$BACKEND_PORT"
  ensure_port_available "$FRONTEND_PORT"

  (
    cd "$ROOT" || exit 1
    ./.venv312/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload
  ) &
  BACK_PID=$!
  printf '%s\n' "$BACK_PID" > "$BACK_PID_FILE"

  (
    cd "$ROOT/frontend" || exit 1
    npm run dev:local
  ) &
  FRONT_PID=$!
  printf '%s\n' "$FRONT_PID" > "$FRONT_PID_FILE"

  trap cleanup_started_processes EXIT INT TERM
  wait
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
