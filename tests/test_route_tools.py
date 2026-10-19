import pytest

from traefik_mcp import git_ops
from traefik_mcp.config import Settings
from traefik_mcp.route_model import RouteMode, RouteSpec
from traefik_mcp.tools import routes as route_tools


def make_spec(**overrides) -> RouteSpec:
    defaults = dict(
        router_name="gitea",
        domain="git.lumasystem.com",
        backend_url="http://192.168.17.60:3000",
    )
    defaults.update(overrides)
    return RouteSpec(**defaults)


@pytest.mark.asyncio
async def test_create_route_success(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/gitea@file",
        json={"status": "enabled", "name": "gitea@file"},
    )

    result = await route_tools.create_or_update_route(settings, make_spec())

    assert result["success"] is True
    assert result["committed"] is True
    assert result["traefik_status"] == "enabled"
    assert (settings.traefik_dynamic_dir / "gitea.yml").exists()

    log = git_ops._run(settings.traefik_repo_dir, ["log", "-1", "--pretty=%s"])
    assert "Add configuration for gitea" in log.stdout


@pytest.mark.asyncio
async def test_create_route_rejects_protected_file(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="protected"):
        await route_tools.create_or_update_route(
            settings, make_spec(filename="dynamic.yml")
        )


@pytest.mark.asyncio
async def test_create_route_rejects_duplicate_name(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="already exists"):
        await route_tools.create_or_update_route(settings, make_spec(router_name="woodpecker"))


@pytest.mark.asyncio
async def test_update_route_requires_existing(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="does not exist"):
        await route_tools.create_or_update_route(
            settings, make_spec(mode=RouteMode.UPDATE)
        )


@pytest.mark.asyncio
async def test_create_route_rejects_unknown_middleware(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="Unknown middleware"):
        await route_tools.create_or_update_route(
            settings, make_spec(middlewares=["does-not-exist"])
        )


@pytest.mark.asyncio
async def test_create_route_rejects_dirty_tree(settings: Settings):
    dynamic_yml = settings.traefik_dynamic_dir / "dynamic.yml"
    dynamic_yml.write_text(dynamic_yml.read_text() + "\n# hand edit\n")
    with pytest.raises(git_ops.GitDirtyTreeError):
        await route_tools.create_or_update_route(settings, make_spec())
    # confirm nothing was written on top of the dirty state
    assert not (settings.traefik_dynamic_dir / "gitea.yml").exists()


@pytest.mark.asyncio
async def test_update_route_appends_to_existing_file(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/woodpecker@file",
        json={"status": "enabled"},
    )
    result = await route_tools.create_or_update_route(
        settings,
        make_spec(
            router_name="woodpecker",
            domain="ci.apps2.lumasystem.com",
            backend_url="http://192.168.17.152:9999",
            filename="woodpecker.yml",
            mode=RouteMode.UPDATE,
        ),
    )
    assert result["success"] is True
    from traefik_mcp import dynamic_files

    _, entries = dynamic_files.load_entries(settings.traefik_dynamic_dir, "woodpecker.yml")
    names = {e.router_name for e in entries}
    assert names == {"woodpecker", "woodpecker-mcp"}
    updated = next(e for e in entries if e.router_name == "woodpecker")
    assert updated.backend_url == "http://192.168.17.152:9999"


@pytest.mark.asyncio
async def test_delete_route_removes_one_of_two_entries(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/woodpecker-mcp@file",
        status_code=404,
    )
    result = await route_tools.delete_route(settings, "woodpecker-mcp", "woodpecker.yml")

    assert result["success"] is True
    assert result["traefik_removed"] is True
    assert (settings.traefik_dynamic_dir / "woodpecker.yml").exists()

    from traefik_mcp import dynamic_files

    _, entries = dynamic_files.load_entries(settings.traefik_dynamic_dir, "woodpecker.yml")
    assert {e.router_name for e in entries} == {"woodpecker"}


@pytest.mark.asyncio
async def test_delete_route_removes_last_entry_deletes_file(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/gitea@file",
        json={"status": "enabled"},
    )
    await route_tools.create_or_update_route(settings, make_spec())

    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/gitea@file",
        status_code=404,
    )
    result = await route_tools.delete_route(settings, "gitea", "gitea.yml")

    assert result["success"] is True
    assert not (settings.traefik_dynamic_dir / "gitea.yml").exists()


@pytest.mark.asyncio
async def test_delete_route_rejects_protected_file(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="protected"):
        await route_tools.delete_route(settings, "does-not-matter", "dynamic.yml")


@pytest.mark.asyncio
async def test_delete_route_rejects_unknown_router(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="not found"):
        await route_tools.delete_route(settings, "nonexistent", "woodpecker.yml")


BLUE_GREEN = ["http://192.168.17.152:3056", "http://192.168.17.152:3057"]


@pytest.mark.asyncio
async def test_create_route_with_several_backends_and_health_check(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/gitea@file",
        json={"status": "enabled"},
    )
    result = await route_tools.create_or_update_route(
        settings, make_spec(backend_url=None, backend_urls=BLUE_GREEN, health_check_path="/healthz")
    )
    assert result["success"] is True

    import yaml

    data = yaml.safe_load((settings.traefik_dynamic_dir / "gitea.yml").read_text())
    load_balancer = data["http"]["services"]["gitea"]["loadBalancer"]
    assert [s["url"] for s in load_balancer["servers"]] == BLUE_GREEN
    assert load_balancer["healthCheck"] == {"path": "/healthz", "interval": "3s", "timeout": "2s"}


@pytest.mark.asyncio
async def test_updating_a_sibling_route_keeps_several_backends(settings: Settings, httpx_mock):
    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/gitea@file",
        json={"status": "enabled"},
    )
    await route_tools.create_or_update_route(
        settings,
        make_spec(
            backend_url=None,
            backend_urls=BLUE_GREEN,
            health_check_path="/healthz",
            filename="woodpecker.yml",
        ),
    )
    httpx_mock.add_response(
        url="http://127.0.0.1:8080/api/http/routers/woodpecker@file",
        json={"status": "enabled"},
    )
    await route_tools.create_or_update_route(
        settings,
        make_spec(
            router_name="woodpecker",
            domain="ci.apps2.lumasystem.com",
            backend_url="http://192.168.17.152:9999",
            filename="woodpecker.yml",
            mode=RouteMode.UPDATE,
        ),
    )

    from traefik_mcp import dynamic_files

    _, entries = dynamic_files.load_entries(settings.traefik_dynamic_dir, "woodpecker.yml")
    gitea = next(e for e in entries if e.router_name == "gitea")
    assert gitea.backend_urls == BLUE_GREEN
    assert gitea.health_check == dynamic_files.HealthCheck(path="/healthz", interval="3s", timeout="2s")
    woodpecker = next(e for e in entries if e.router_name == "woodpecker")
    assert woodpecker.backend_urls == ["http://192.168.17.152:9999"]
    assert woodpecker.health_check is None


@pytest.mark.asyncio
async def test_several_backends_require_health_check(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="health_check_path"):
        await route_tools.create_or_update_route(
            settings, make_spec(backend_url=None, backend_urls=BLUE_GREEN)
        )


@pytest.mark.asyncio
async def test_backend_url_and_backend_urls_are_exclusive(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="not both"):
        await route_tools.create_or_update_route(
            settings, make_spec(backend_urls=BLUE_GREEN, health_check_path="/healthz")
        )


@pytest.mark.asyncio
async def test_route_needs_a_backend(settings: Settings):
    with pytest.raises(route_tools.RouteToolError, match="needs backend_url"):
        await route_tools.create_or_update_route(settings, make_spec(backend_url=None))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        dict(health_check_path="healthz"),
        dict(health_check_path="/healthz", health_check_interval="soon"),
        dict(backend_urls=[BLUE_GREEN[0], "http://localhost:3057"], health_check_path="/healthz"),
        dict(backend_urls=[BLUE_GREEN[0], BLUE_GREEN[0]], health_check_path="/healthz"),
    ],
)
async def test_several_backends_rejects_bad_input(settings: Settings, overrides):
    spec = dict(backend_url=None, backend_urls=BLUE_GREEN)
    spec.update(overrides)
    with pytest.raises(route_tools.RouteToolError):
        await route_tools.create_or_update_route(settings, make_spec(**spec))
