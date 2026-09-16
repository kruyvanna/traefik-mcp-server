import pytest

from traefik_mcp.config import Settings
from traefik_mcp.tools import introspect as introspect_tools

BASE = "http://127.0.0.1:8080"


@pytest.mark.asyncio
async def test_traefik_version(settings: Settings, httpx_mock):
    httpx_mock.add_response(url=f"{BASE}/api/version", json={"Version": "3.3.7"})
    result = await introspect_tools.traefik_version(settings)
    assert result["Version"] == "3.3.7"


@pytest.mark.asyncio
async def test_list_live_routers_filters_by_provider(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/api/http/routers",
        json=[
            {"name": "woodpecker@file", "status": "enabled"},
            {"name": "whoami@docker", "status": "enabled"},
            {"name": "acme-http@internal", "status": "enabled"},
        ],
    )
    result = await introspect_tools.list_live_routers(settings, provider="file")
    assert [r["name"] for r in result] == ["woodpecker@file"]


@pytest.mark.asyncio
async def test_get_live_router_missing_returns_404(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url=f"{BASE}/api/http/routers/nonexistent@file", status_code=404
    )
    result = await introspect_tools.get_live_router(settings, "nonexistent@file")
    assert result["http_status"] == 404
    assert result["router"] is None


@pytest.mark.asyncio
async def test_cross_check_config_reports_drift(settings: Settings, httpx_mock):
    # Live API is missing woodpecker-mcp and has an orphaned extra router.
    httpx_mock.add_response(
        url=f"{BASE}/api/http/routers",
        json=[
            {"name": "woodpecker@file", "status": "enabled"},
            {"name": "whoami-file-test@file", "status": "warning"},
            {"name": "orphaned-route@file", "status": "enabled"},
        ],
    )
    result = await introspect_tools.cross_check_config(settings)

    assert result["in_yaml_not_live"] == ["woodpecker-mcp"]
    assert result["live_not_in_yaml"] == ["orphaned-route"]
    assert result["live_but_not_enabled"] == [
        {"router_name": "whoami-file-test", "status": "warning", "file": "sample-test.yml"}
    ]
    assert result["in_sync"] is False
