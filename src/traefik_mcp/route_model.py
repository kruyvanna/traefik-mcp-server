from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RouteMode(str, Enum):
    CREATE = "create"
    UPDATE = "update"


class RouteSpec(BaseModel):
    router_name: str = Field(..., description="Kebab-case name shared by the router and service")
    domain: str = Field(..., description="Hostname to route, e.g. 'ci.apps2.lumasystem.com'")
    backend_url: Optional[str] = Field(
        default=None, description="Backend URL, e.g. 'http://192.168.17.152:8000'"
    )
    backend_urls: list[str] = Field(
        default_factory=list,
        description="Several backends load-balanced by one service (e.g. blue/green ports); "
        "use instead of backend_url",
    )
    health_check_path: Optional[str] = Field(
        default=None,
        description="loadBalancer.healthCheck path, e.g. '/healthz'. Required with several backends, "
        "so only healthy ones get traffic",
    )
    health_check_interval: str = "3s"
    health_check_timeout: str = "2s"
    filename: Optional[str] = Field(
        default=None,
        description="Target dynamic/ file (basename). Defaults to '<router_name>.yml'.",
    )
    middlewares: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    cert_resolver: Optional[str] = None
    comment: Optional[str] = Field(
        default=None, description="Optional leading '# ...' comment for the router block"
    )
    mode: RouteMode = RouteMode.CREATE

    @property
    def all_backend_urls(self) -> list[str]:
        return list(self.backend_urls) if self.backend_urls else ([self.backend_url] if self.backend_url else [])
