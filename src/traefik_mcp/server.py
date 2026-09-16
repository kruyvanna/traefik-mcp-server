from typing import Optional

from mcp.server.mcpserver import MCPServer

from .config import get_settings
from .route_model import RouteMode, RouteSpec
from .tools import files as files_tools
from .tools import introspect as introspect_tools
from .tools import routes as route_tools

settings = get_settings()

app = MCPServer(
    "traefik-mcp",
    instructions=(
        "Manages this host's Traefik file-provider dynamic config "
        f"at {settings.traefik_dynamic_dir}. Only handles routes for external/remote "
        "backends (one YAML file per logical remote host, possibly holding several "
        "router+service pairs) — it does not touch Docker-label-based routing. "
        f"'{'`, `'.join(sorted(settings.protected_files))}' are shared/fixture files and "
        "are read-only through this server. Every successful write is committed to git "
        "(never pushed) in the Traefik repo."
    ),
)


@app.tool()
def list_dynamic_files() -> dict:
    """List every file in the Traefik dynamic config directory, with protected flag,
    contained router names, size and modified time."""
    return files_tools.list_dynamic_files(settings)


@app.tool()
def read_dynamic_file(filename: str) -> dict:
    """Read one dynamic config file's raw YAML text and parsed structure. Works on
    protected files too (read-only is always safe)."""
    return files_tools.read_dynamic_file(settings, filename)


@app.tool()
async def create_or_update_route(
    router_name: str,
    domain: str,
    backend_url: str,
    mode: str = "create",
    filename: Optional[str] = None,
    middlewares: Optional[list[str]] = None,
    entry_points: Optional[list[str]] = None,
    cert_resolver: Optional[str] = None,
    comment: Optional[str] = None,
) -> dict:
    """Create or update a Traefik route (a router+service pair) in dynamic/.

    router_name must be kebab-case and is shared by the router and service.
    domain is the Host() rule target, e.g. 'ci.apps2.lumasystem.com'.
    backend_url is where traffic is forwarded, e.g. 'http://192.168.17.152:8000'.
    filename defaults to '<router_name>.yml'; pass an existing file's name to add
    another router+service pair alongside others for the same logical remote host
    (see woodpecker.yml for this pattern).
    middlewares/entry_points/cert_resolver default to this deployment's conventions
    (['secure-headers'], ['websecure'], 'myresolver') if omitted.
    mode='create' fails if router_name already exists anywhere; mode='update' fails
    if it does not already exist in the given filename.
    Refuses to touch protected files (dynamic.yml, sample-test.yml) or to write if
    the Traefik git repo has unrelated uncommitted changes. On success, commits the
    change and polls the live Traefik API to confirm the router came up.
    """
    spec = RouteSpec(
        router_name=router_name,
        domain=domain,
        backend_url=backend_url,
        filename=filename,
        middlewares=middlewares or [],
        entry_points=entry_points or [],
        cert_resolver=cert_resolver,
        comment=comment,
        mode=RouteMode(mode),
    )
    return await route_tools.create_or_update_route(settings, spec)


@app.tool()
async def delete_route(router_name: str, filename: str) -> dict:
    """Delete one router+service pair from a dynamic/ file. If other routes remain
    in that file they are preserved; if it was the last one, the file is removed
    entirely. Refuses protected files. Commits the change and polls the live API
    to confirm the router is gone."""
    return await route_tools.delete_route(settings, router_name, filename)


@app.tool()
async def traefik_overview() -> dict:
    """Live Traefik overview: router/service/middleware counts from the API."""
    return await introspect_tools.traefik_overview(settings)


@app.tool()
async def traefik_version() -> dict:
    """Live Traefik version info (also serves as a health check)."""
    return await introspect_tools.traefik_version(settings)


@app.tool()
async def list_entrypoints() -> list:
    """List configured Traefik entrypoints (e.g. web, websecure)."""
    return await introspect_tools.list_entrypoints(settings)


@app.tool()
async def list_live_routers(provider: Optional[str] = None) -> list:
    """List live HTTP routers from the Traefik API. Optionally filter by provider
    ('file', 'docker', or 'internal')."""
    return await introspect_tools.list_live_routers(settings, provider)


@app.tool()
async def list_live_services() -> list:
    """List live HTTP services from the Traefik API."""
    return await introspect_tools.list_live_services(settings)


@app.tool()
async def list_live_middlewares() -> list:
    """List live HTTP middlewares from the Traefik API."""
    return await introspect_tools.list_live_middlewares(settings)


@app.tool()
async def get_live_router(name: str) -> dict:
    """Get one live router's full resolved state by its provider-qualified name,
    e.g. 'woodpecker@file'."""
    return await introspect_tools.get_live_router(settings, name)


@app.tool()
async def cross_check_config() -> dict:
    """Diff the dynamic/ YAML inventory against the live 'file' provider routers
    to surface drift: routes in YAML but not live, live routes not in YAML, or
    routes that loaded with a non-'enabled' status."""
    return await introspect_tools.cross_check_config(settings)


def main() -> None:
    if settings.mcp_transport == "streamable-http":
        app.run(
            transport="streamable-http",
            host=settings.mcp_http_host,
            port=settings.mcp_http_port,
        )
    else:
        app.run(transport="stdio")


if __name__ == "__main__":
    main()
