import asyncio
from typing import Any, Optional

import httpx


class TraefikClient:
    def __init__(self, base_url: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _get(self, endpoint: str) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{endpoint}")
            response.raise_for_status()
            return response.json()

    async def _get_optional(self, endpoint: str) -> tuple[Optional[int], Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{endpoint}")
            if response.status_code == 404:
                return 404, None
            response.raise_for_status()
            return response.status_code, response.json()

    async def overview(self) -> dict:
        return await self._get("/api/overview")

    async def version(self) -> dict:
        return await self._get("/api/version")

    async def entrypoints(self) -> list:
        return await self._get("/api/entrypoints")

    async def routers(self) -> list:
        return await self._get("/api/http/routers")

    async def services(self) -> list:
        return await self._get("/api/http/services")

    async def middlewares(self) -> list:
        return await self._get("/api/http/middlewares")

    async def router(self, name: str) -> tuple[Optional[int], Any]:
        """Fetch one router by its provider-qualified name, e.g. 'woodpecker@file'."""
        return await self._get_optional(f"/api/http/routers/{name}")

    async def poll_router_status(
        self, name: str, delays: tuple[float, ...]
    ) -> dict:
        """Poll until the router appears (any status) or the delay budget runs out."""
        last_status_code = None
        last_body = None
        for delay in (0.0, *delays):
            if delay:
                await asyncio.sleep(delay)
            status_code, body = await self.router(name)
            last_status_code, last_body = status_code, body
            if status_code == 200:
                return {"observed": True, "http_status": status_code, "router": body}
        return {"observed": False, "http_status": last_status_code, "router": last_body}

    async def poll_router_absent(self, name: str, delays: tuple[float, ...]) -> dict:
        """Poll until the router returns 404 (deleted) or the delay budget runs out."""
        last_status_code = None
        for delay in (0.0, *delays):
            if delay:
                await asyncio.sleep(delay)
            status_code, _ = await self.router(name)
            last_status_code = status_code
            if status_code == 404:
                return {"removed": True, "http_status": status_code}
        return {"removed": False, "http_status": last_status_code}
