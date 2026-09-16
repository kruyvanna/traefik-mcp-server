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

Runs as a Docker container (`docker-compose.yml`) on the `traefik_web`
network — the same network Traefik and `whoami` use — so it's reachable
both:

- **Locally**, via the published port: `http://127.0.0.1:8765/mcp`
- **Externally**, via Traefik: `https://traefik-mcp.lumasystem.com/mcp`
  (self-registered as its own route in `dynamic/traefik-mcp.yml`)

Both paths require `Authorization: Bearer <MCP_AUTH_TOKEN>` — the server
refuses to bind to a non-loopback host without a token configured. The
MCP SDK's own DNS-rebinding protection is explicitly configured via
`MCP_ALLOWED_HOSTS`/`MCP_ALLOWED_ORIGINS` to cover both the container's
internal name and the public domain (it only auto-allows
127.0.0.1/localhost by default, which would otherwise reject every
request that arrives via Traefik with a real Host header).

`restart: unless-stopped` in the compose file means it comes back up
automatically after a reboot, same as the `traefik`/`whoami` containers.

```bash
docker compose up -d --build   # start / rebuild after a code change
docker compose logs -f         # tail logs
docker compose down            # stop
```

Secrets (`MCP_AUTH_TOKEN`, `ACME_EMAIL`) live in a gitignored `.env`
(see `.env.example`) — generate a token with
`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.

For local/manual runs outside Docker, stdio transport still works:
`MCP_TRANSPORT=stdio uv run traefik-mcp` (or omit `MCP_TRANSPORT` — it
defaults to stdio).

## Tools

`list_dynamic_files`, `read_dynamic_file`, `create_or_update_route`,
`delete_route`, `traefik_overview`, `traefik_version`, `list_entrypoints`,
`list_live_routers`, `list_live_services`, `list_live_middlewares`,
`get_live_router`, `cross_check_config`.
