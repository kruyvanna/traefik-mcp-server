from pathlib import Path

import yaml

from traefik_mcp import dynamic_files


def test_load_entries_woodpecker(repo_dir: Path):
    dynamic_dir = repo_dir / "dynamic"
    comment, entries = dynamic_files.load_entries(dynamic_dir, "woodpecker.yml")

    assert comment == "Woodpecker CI server, running on host 192.168.17.152 (apps-2)."
    assert {e.router_name for e in entries} == {"woodpecker", "woodpecker-mcp"}

    wp = next(e for e in entries if e.router_name == "woodpecker")
    assert wp.domain == "ci.apps2.lumasystem.com"
    assert wp.backend_url == "http://192.168.17.152:8000"
    assert wp.middlewares == ["secure-headers"]
    assert wp.entry_points == ["websecure"]
    assert wp.cert_resolver == "myresolver"


def test_load_entries_missing_file_returns_empty(repo_dir: Path):
    comment, entries = dynamic_files.load_entries(repo_dir / "dynamic", "nope.yml")
    assert comment is None
    assert entries == []


def test_get_all_router_names(repo_dir: Path):
    names = dynamic_files.get_all_router_names(repo_dir / "dynamic")
    assert names == {
        "woodpecker": "woodpecker.yml",
        "woodpecker-mcp": "woodpecker.yml",
        "whoami-file-test": "sample-test.yml",
    }


def test_get_all_middleware_names(repo_dir: Path):
    names = dynamic_files.get_all_middleware_names(repo_dir / "dynamic")
    assert names == {"secure-headers"}


def test_render_and_reparse_round_trip(repo_dir: Path):
    entries = [
        dynamic_files.RouteEntry(
            router_name="gitea",
            domain="git.lumasystem.com",
            backend_url="http://192.168.17.60:3000",
            middlewares=["secure-headers"],
            entry_points=["websecure"],
            cert_resolver="myresolver",
        )
    ]
    content = dynamic_files.render_file("Gitea, running on host 192.168.17.60.", entries)
    parsed = yaml.safe_load(content)

    router = parsed["http"]["routers"]["gitea"]
    assert router["rule"] == "Host(`git.lumasystem.com`)"
    assert router["entryPoints"] == ["websecure"]
    assert router["service"] == "gitea"
    assert router["tls"]["certResolver"] == "myresolver"
    assert router["middlewares"] == ["secure-headers"]

    service = parsed["http"]["services"]["gitea"]
    assert service["loadBalancer"]["servers"][0]["url"] == "http://192.168.17.60:3000"


def test_write_entries_is_atomic_and_readable_back(repo_dir: Path):
    dynamic_dir = repo_dir / "dynamic"
    entries = [
        dynamic_files.RouteEntry(
            router_name="gitea",
            domain="git.lumasystem.com",
            backend_url="http://192.168.17.60:3000",
            middlewares=[],
            entry_points=["websecure"],
            cert_resolver="myresolver",
        )
    ]
    path = dynamic_files.write_entries(dynamic_dir, "gitea.yml", None, entries)
    assert path.exists()
    # no leftover temp files
    assert not list(dynamic_dir.glob(".*.tmp"))

    comment, reloaded = dynamic_files.load_entries(dynamic_dir, "gitea.yml")
    assert comment is None
    assert reloaded[0].router_name == "gitea"


def test_delete_file(repo_dir: Path):
    dynamic_dir = repo_dir / "dynamic"
    path = dynamic_files.delete_file(dynamic_dir, "sample-test.yml")
    assert not path.exists()


def test_list_files_reports_protected_flag(repo_dir: Path):
    summaries = dynamic_files.list_files(dynamic_dir=repo_dir / "dynamic", protected_files=frozenset({"dynamic.yml", "sample-test.yml"}))
    by_name = {s.name: s for s in summaries}
    assert by_name["dynamic.yml"].protected is True
    assert by_name["woodpecker.yml"].protected is False
    assert set(by_name["woodpecker.yml"].router_names) == {"woodpecker", "woodpecker-mcp"}
