#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$ROOT/scripts/start_local_services.sh"

if [[ ! -f "$TARGET" ]]; then
  echo "missing target script: $TARGET" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$TARGET"

assert_eq() {
  local expected="$1"
  local actual="$2"
  local message="$3"

  if [[ "$expected" != "$actual" ]]; then
    echo "assert_eq failed: $message" >&2
    echo "expected: $expected" >&2
    echo "actual:   $actual" >&2
    exit 1
  fi
}

assert_contains() {
  local needle="$1"
  local haystack="$2"
  local message="$3"

  if [[ "$haystack" != *"$needle"* ]]; then
    echo "assert_contains failed: $message" >&2
    echo "needle: $needle" >&2
    echo "haystack: $haystack" >&2
    exit 1
  fi
}

run_tests() {
  test_stop_tracked_process_waits_and_forces_if_needed
  test_ensure_port_available_reports_listener
  echo "start_local_services tests passed"
}

test_stop_tracked_process_waits_and_forces_if_needed() {
  local temp_dir pid_file
  temp_dir="$(mktemp -d)"
  pid_file="$temp_dir/backend.pid"
  printf '123\n' > "$pid_file"

  KILL_LOG=""
  PORT_SEQUENCE_8000=("123" "123" "")

  pid_is_running() {
    [[ "$1" == "123" ]]
  }

  terminate_pid() {
    KILL_LOG+="TERM:$1;"
  }

  force_terminate_pid() {
    KILL_LOG+="KILL:$1;"
  }

  sleep_for_shutdown() {
    :
  }

  port_listeners() {
    local port="$1"
    if [[ "$port" == "8000" ]]; then
      local value="${PORT_SEQUENCE_8000[0]:-}"
      if ((${#PORT_SEQUENCE_8000[@]} > 0)); then
        PORT_SEQUENCE_8000=("${PORT_SEQUENCE_8000[@]:1}")
      fi
      printf '%s' "$value"
      return
    fi

    printf ''
  }

  stop_tracked_process "$pid_file" 8000

  assert_eq "TERM:123;KILL:123;" "$KILL_LOG" "tracked process should escalate when port stays occupied"
  assert_eq "missing" "$( [[ -f "$pid_file" ]] && echo exists || echo missing )" "pid file should be removed"

  unset -f pid_is_running terminate_pid force_terminate_pid sleep_for_shutdown port_listeners
  rm -rf "$temp_dir"
}

test_ensure_port_available_reports_listener() {
  local output status

  port_listeners() {
    [[ "$1" == "5173" ]] && printf '4321'
  }

  describe_port_listener() {
    printf 'node 4321 LISTEN 127.0.0.1:5173'
  }

  set +e
  output="$(ensure_port_available 5173 2>&1)"
  status=$?
  set -e

  assert_eq "1" "$status" "occupied port should fail"
  assert_contains "端口 5173 已被其他进程占用" "$output" "error should mention occupied port"
  assert_contains "node 4321 LISTEN" "$output" "error should print listener details"

  unset -f port_listeners describe_port_listener
}

run_tests
