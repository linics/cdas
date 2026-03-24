#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_ENV_FILE="$ROOT_DIR/.env"
BACKEND_ENV_EXAMPLE="$ROOT_DIR/.env.example"
FRONTEND_ENV_LOCAL="$ROOT_DIR/frontend/.env.local"
VENV_DIR="$ROOT_DIR/.venv312"
VENV_PYTHON="$VENV_DIR/bin/python"
STAMP_FILE="$ROOT_DIR/.worktree-env.stamp"

log() {
  printf '[bootstrap] %s\n' "$1"
}

find_existing_worktree_file() {
  local relative_path="$1"
  local worktree_path

  while IFS= read -r worktree_path; do
    [[ -z "$worktree_path" ]] && continue
    [[ "$worktree_path" == "$ROOT_DIR" ]] && continue
    if [[ -f "$worktree_path/$relative_path" ]]; then
      printf '%s\n' "$worktree_path/$relative_path"
      return 0
    fi
  done < <(git -C "$ROOT_DIR" worktree list --porcelain | awk '/^worktree / {print substr($0, 10)}')

  return 1
}

ensure_backend_env() {
  local source_file=""

  if [[ -f "$BACKEND_ENV_FILE" ]]; then
    return
  fi

  source_file="$(find_existing_worktree_file ".env" || true)"
  if [[ -n "$source_file" ]]; then
    cp "$source_file" "$BACKEND_ENV_FILE"
    log "copied .env from existing worktree"
    return
  fi

  if [[ -f "$BACKEND_ENV_EXAMPLE" ]]; then
    cp "$BACKEND_ENV_EXAMPLE" "$BACKEND_ENV_FILE"
    log "created .env from .env.example"
  fi
}

ensure_frontend_env() {
  local source_file=""

  if [[ -f "$FRONTEND_ENV_LOCAL" ]]; then
    return
  fi

  source_file="$(find_existing_worktree_file "frontend/.env.local" || true)"
  if [[ -n "$source_file" ]]; then
    cp "$source_file" "$FRONTEND_ENV_LOCAL"
    log "copied frontend/.env.local from existing worktree"
    return
  fi

  if [[ ! -f "$FRONTEND_ENV_LOCAL" ]]; then
    cat >"$FRONTEND_ENV_LOCAL" <<'EOF'
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_DEV_HOST=127.0.0.1
VITE_DEV_PORT=5173
VITE_DEV_API_TARGET=http://127.0.0.1:8000
EOF
    log "created frontend/.env.local"
  fi
}

ensure_storage_dirs() {
  mkdir -p \
    "$ROOT_DIR/storage" \
    "$ROOT_DIR/storage/documents" \
    "$ROOT_DIR/storage/chroma"
}

ensure_python_env() {
  if ! command -v python3.12 >/dev/null 2>&1; then
    log "python3.12 not found; skipped virtualenv bootstrap"
    return
  fi

  if [[ ! -d "$VENV_DIR" ]]; then
    python3.12 -m venv "$VENV_DIR"
    log "created .venv312"
  else
    python3.12 -m venv --upgrade "$VENV_DIR" >/dev/null 2>&1 || true
  fi

  "$VENV_PYTHON" -m pip install -r "$ROOT_DIR/requirements.txt" >/dev/null
  log "verified backend dependencies"
}

ensure_frontend_deps() {
  if ! command -v npm >/dev/null 2>&1; then
    log "npm not found; skipped frontend dependency install"
    return
  fi

  if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
    (cd "$ROOT_DIR/frontend" && npm install >/dev/null)
    log "installed frontend dependencies"
    return
  fi

  log "frontend dependencies already present"
}

write_stamp() {
  cat >"$STAMP_FILE" <<EOF
bootstrapped_at=$(date '+%Y-%m-%d %H:%M:%S')
root_dir=$ROOT_DIR
EOF
}

main() {
  ensure_backend_env
  ensure_frontend_env
  ensure_storage_dirs
  ensure_python_env
  ensure_frontend_deps
  write_stamp
  log "worktree environment ready"
}

main "$@"
