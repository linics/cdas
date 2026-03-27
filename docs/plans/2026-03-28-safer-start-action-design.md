## Safer Start Action Design

Goal: keep the Codex "启动服务" action safe for local multi-project development without making restarts fragile.

Behavior:
- Stop only processes previously started by this repository action, using PID files under `.codex/run/`.
- After attempting shutdown, wait briefly for ports `8000` and `5173` to become free.
- If a port is still occupied, fail with a clear message and show the current listener instead of killing unrelated processes.
- Start backend and frontend, record their PIDs, and clean up PID files on exit.

Implementation shape:
- Move the shell logic into `scripts/start_local_services.sh` so it can be tested directly.
- Keep `.codex/environments/environment.toml` as a thin wrapper that invokes the script.
