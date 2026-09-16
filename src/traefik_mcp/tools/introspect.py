from .. import dynamic_files
from ..config import Settings
from ..traefik_client import TraefikClient


def _client(settings: Settings) -> TraefikClient:
    return TraefikClient(settings.traefik_api_base_url, settings.api_timeout_seconds)


async def traefik_overview(settings: Settings) -> dict:
    return await _client(settings).overview()


async def traefik_version(settings: Settings) -> dict:
    return await _client(settings).version()


async def list_entrypoints(settings: Settings) -> list:
    return await _client(settings).entrypoints()


async def list_live_routers(settings: Settings, provider: str | None = None) -> list:
    routers = await _client(settings).routers()
    if provider:
        routers = [r for r in routers if r.get("name", "").endswith(f"@{provider}")]
    return routers


async def list_live_services(settings: Settings) -> list:
    return await _client(settings).services()


async def list_live_middlewares(settings: Settings) -> list:
    return await _client(settings).middlewares()


async def get_live_router(settings: Settings, name: str) -> dict:
    status_code, body = await _client(settings).router(name)
    return {"http_status": status_code, "router": body}


async def cross_check_config(settings: Settings) -> dict:
    """Diff the YAML inventory in dynamic/ against the live 'file' provider routers."""
    router_to_file = dynamic_files.get_all_router_names(settings.traefik_dynamic_dir)
    yaml_names = set(router_to_file.keys())

    live_routers = await _client(settings).routers()
    live_file_routers = {
        r["name"].removesuffix("@file"): r for r in live_routers if r.get("name", "").endswith("@file")
    }
    live_names = set(live_file_routers.keys())

    missing_live = sorted(yaml_names - live_names)
    orphaned_live = sorted(live_names - yaml_names)
    warnings = sorted(
        name
        for name in yaml_names & live_names
        if live_file_routers[name].get("status") != "enabled"
    )

    return {
        "in_yaml_not_live": missing_live,
        "live_not_in_yaml": orphaned_live,
        "live_but_not_enabled": [
            {"router_name": n, "status": live_file_routers[n].get("status"), "file": router_to_file[n]}
            for n in warnings
        ],
        "in_sync": not missing_live and not orphaned_live and not warnings,
    }
