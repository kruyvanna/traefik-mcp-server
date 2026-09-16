from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RouteMode(str, Enum):
    CREATE = "create"
    UPDATE = "update"


class RouteSpec(BaseModel):
    router_name: str = Field(..., description="Kebab-case name shared by the router and service")
    domain: str = Field(..., description="Hostname to route, e.g. 'ci.apps2.lumasystem.com'")
    backend_url: str = Field(..., description="Backend URL, e.g. 'http://192.168.17.152:8000'")
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
