"""Lightweight async client for the documented sonnenBatterie /api/v2 endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from aiohttp import ClientTimeout

from .const import LOGGER

_TIMEOUT = ClientTimeout(total=15)


class SonnenApiError(Exception):
    """Base error for the sonnenBatterie API."""


class SonnenConnectionError(SonnenApiError):
    """The battery could not be reached."""


class SonnenAuthError(SonnenApiError):
    """The Auth-Token is missing or invalid (HTTP 401)."""


class SonnenForbiddenError(SonnenApiError):
    """The battery refused the action (HTTP 403, e.g. VPP active)."""


class SonnenV2Api:
    """Minimal wrapper around the documented /api/v2 endpoints."""

    def __init__(
        self, host: str, token: str | None, session: aiohttp.ClientSession
    ) -> None:
        self._host = host
        self._base = f"http://{host}/api/v2"
        self._session = session
        self._auth_headers = {"Auth-Token": token} if token else {}

    @property
    def host(self) -> str:
        return self._host

    async def _request(
        self, method: str, path: str, *, auth: bool = True, **kwargs: Any
    ) -> Any:
        url = f"{self._base}{path}"
        headers = self._auth_headers if auth else {}
        try:
            async with self._session.request(
                method, url, headers=headers, timeout=_TIMEOUT, **kwargs
            ) as resp:
                if resp.status == 401:
                    raise SonnenAuthError(f"Unauthorized for {path} (invalid Auth-Token?)")
                if resp.status == 403:
                    raise SonnenForbiddenError(
                        f"Forbidden for {path}: {await _safe_text(resp)}"
                    )
                resp.raise_for_status()
                if resp.content_type == "application/json":
                    return await resp.json()
                return (await resp.text()).strip()
        except (SonnenAuthError, SonnenForbiddenError):
            raise
        except aiohttp.ClientResponseError as err:
            raise SonnenApiError(f"HTTP {err.status} for {path}: {err.message}") from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise SonnenConnectionError(f"Cannot connect to {url}: {err}") from err

    # --- reads --------------------------------------------------------------
    async def get_status(self) -> dict[str, Any]:
        """Main status. This endpoint does NOT require a token."""
        return await self._request("GET", "/status", auth=False)

    async def get_latestdata(self) -> dict[str, Any]:
        return await self._request("GET", "/latestdata")

    async def get_inverter(self) -> dict[str, Any]:
        return await self._request("GET", "/inverter")

    async def get_powermeter(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/powermeter")

    async def get_battery(self) -> dict[str, Any]:
        return await self._request("GET", "/battery")

    async def get_configurations(self) -> dict[str, Any]:
        return await self._request("GET", "/configurations")

    # --- writes -------------------------------------------------------------
    async def set_configuration(self, key: str, value: Any) -> dict[str, Any]:
        """PUT a single configuration value (form-encoded)."""
        return await self._request("PUT", "/configurations", data={key: str(value)})

    async def set_setpoint(self, direction: str, watts: int) -> Any:
        """POST a charge/discharge setpoint in watts. direction: 'charge'|'discharge'."""
        return await self._request("POST", f"/setpoint/{direction}/{int(watts)}")


async def _safe_text(resp: aiohttp.ClientResponse) -> str:
    try:
        return (await resp.text())[:200]
    except Exception:  # noqa: BLE001
        return ""
