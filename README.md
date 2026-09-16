# traefik-mcp

A small MCP server for managing this host's Traefik file-provider dynamic
config (`/home/lumadev/apps/traefik/dynamic/*.yml`).

## Scope

Manages routes for external/remote backends only — one YAML file per
logical remote host, which may hold several router+service pairs (see
`woodpecker.yml` for the pattern). Does **not** touch Docker-label-based
routing on containers running on this host.

`dynamic.yml` (shared middlewares/TLS options) and `sample-test.yml` (the
file-provider smoke test) are protected: read-only through this server,
never written or deleted.

## Safety rails

- Refuses to write anything if the Traefik git repo has unrelated
  uncommitted changes (never bundles unrelated edits into an automated
  commit).
- Never runs `git push`.
- Writes are atomic (temp file + rename) so Traefik's file watcher never
  sees a half-written file.
- After every write/delete, polls the live Traefik API
  (`http://127.0.0.1:8080`) to confirm the change actually took effect.

## Setup

```bash
uv sync
cp .env.example .env   # adjust paths if needed
uv run pytest
```

## Running

Runs as a systemd `--user` service over streamable-HTTP on
`127.0.0.1:8765`, so it survives reboots without needing a login session
(`loginctl enable-linger lumadev` is set). Registered with Claude Code at
user scope as an HTTP server (`claude mcp list`).

```bash
systemctl --user status traefik-mcp   # check it's running
systemctl --user restart traefik-mcp  # after a code change
journalctl --user -u traefik-mcp -f   # tail logs
```

The unit file lives at `traefik-mcp.service` in this repo and is
symlinked into `~/.config/systemd/user/`.

For local/manual runs outside systemd, stdio transport still works:
`MCP_TRANSPORT=stdio uv run traefik-mcp` (or omit `MCP_TRANSPORT` — it
defaults to stdio).

## Tools

`list_dynamic_files`, `read_dynamic_file`, `create_or_update_route`,
`delete_route`, `traefik_overview`, `traefik_version`, `list_entrypoints`,
`list_live_routers`, `list_live_services`, `list_live_middlewares`,
`get_live_router`, `cross_check_config`.
