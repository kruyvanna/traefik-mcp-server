from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    traefik_dynamic_dir: Path = Path("/home/lumadev/apps/traefik/dynamic")
    traefik_repo_dir: Path = Path("/home/lumadev/apps/traefik")
    traefik_api_base_url: str = "http://127.0.0.1:8080"

    protected_files: frozenset[str] = frozenset({"dynamic.yml", "sample-test.yml"})
    api_timeout_seconds: float = 5.0
    reload_poll_attempts: int = 5
    reload_poll_delays_seconds: tuple[float, ...] = (0.3, 0.6, 1.0, 1.5, 2.0)
    require_branch: str = "main"

    default_middlewares: list[str] = Field(default_factory=lambda: ["secure-headers"])
    default_entry_points: list[str] = Field(default_factory=lambda: ["websecure"])
    default_cert_resolver: str = "myresolver"

    mcp_transport: str = "stdio"
    mcp_http_host: str = "127.0.0.1"
    mcp_http_port: int = 8765
    mcp_auth_token: Optional[str] = None
    mcp_allowed_hosts: str = "127.0.0.1:*,localhost:*,[::1]:*"
    mcp_allowed_origins: str = "http://127.0.0.1:*,http://localhost:*,http://[::1]:*"

    @property
    def mcp_allowed_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.mcp_allowed_hosts.split(",") if h.strip()]

    @property
    def mcp_allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.mcp_allowed_origins.split(",") if o.strip()]


def get_settings() -> Settings:
    return Settings()
