import subprocess
from pathlib import Path

import pytest

from traefik_mcp.config import Settings

DYNAMIC_YML = """http:
  middlewares:
    secure-headers:
      headers:
        stsSeconds: 31536000
        stsIncludeSubdomains: true
        contentTypeNosniff: true
        browserXssFilter: true

tls:
  options:
    default:
      minVersion: VersionTLS12
"""

SAMPLE_TEST_YML = """# Sample router defined entirely via the file provider (no Docker labels).
http:
  routers:
    whoami-file-test:
      rule: "Host(`test-traefik-yml-file.lumasystem.com`)"
      entryPoints:
        - websecure
      service: whoami-file-test
      tls:
        certResolver: myresolver

  services:
    whoami-file-test:
      loadBalancer:
        servers:
          - url: "http://whoami:80"
"""

WOODPECKER_YML = """# Woodpecker CI server, running on host 192.168.17.152 (apps-2).
http:
  routers:
    woodpecker:
      rule: "Host(`ci.apps2.lumasystem.com`)"
      entryPoints:
        - websecure
      service: woodpecker
      tls:
        certResolver: myresolver
      middlewares:
        - secure-headers

    woodpecker-mcp:
      rule: "Host(`woodpecker-mcp.apps2.lumasystem.com`)"
      entryPoints:
        - websecure
      service: woodpecker-mcp
      tls:
        certResolver: myresolver
      middlewares:
        - secure-headers

  services:
    woodpecker:
      loadBalancer:
        servers:
          - url: "http://192.168.17.152:8000"

    woodpecker-mcp:
      loadBalancer:
        servers:
          - url: "http://192.168.17.152:8002"
"""


def _git(repo_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_dir), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "traefik"
    dynamic = repo / "dynamic"
    dynamic.mkdir(parents=True)

    (dynamic / "dynamic.yml").write_text(DYNAMIC_YML)
    (dynamic / "sample-test.yml").write_text(SAMPLE_TEST_YML)
    (dynamic / "woodpecker.yml").write_text(WOODPECKER_YML)

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "Initial fixture commit")

    return repo


@pytest.fixture
def settings(repo_dir: Path) -> Settings:
    return Settings(
        traefik_dynamic_dir=repo_dir / "dynamic",
        traefik_repo_dir=repo_dir,
        traefik_api_base_url="http://127.0.0.1:8080",
        reload_poll_delays_seconds=(),
    )
