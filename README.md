# traefik-mcp

A small MCP server for managing this host's Traefik file-provider dynamic
config (`/traefik/dynamic/*.yml`).

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

Already registered with Claude Code at user scope (`claude mcp list`).

## Tools

`list_dynamic_files`, `read_dynamic_file`, `create_or_update_route`,
`delete_route`, `traefik_overview`, `traefik_version`, `list_entrypoints`,
`list_live_routers`, `list_live_services`, `list_live_middlewares`,
`get_live_router`, `cross_check_config`.
