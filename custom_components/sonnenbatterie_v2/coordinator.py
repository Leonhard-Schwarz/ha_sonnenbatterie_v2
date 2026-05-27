"""Data update coordinator for the sonnenBatterie v2 integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SonnenApiError,
    SonnenAuthError,
    SonnenConnectionError,
    SonnenV2Api,
)
from .const import DEFAULT_NAME, DOMAIN, LOGGER


class SonnenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the battery and exposes a combined data dict.

    The /status endpoint is mandatory (and needs no token); if it fails the whole
    update fails (UpdateFailed) so entities go unavailable instead of showing
    stale values. The remaining endpoints are best-effort: a single broken or
    transiently-500 endpoint must not blank out everything.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SonnenV2Api,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.api.get_status()
        except SonnenAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SonnenApiError as err:  # incl. connection errors
            raise UpdateFailed(str(err)) from err

        # Best-effort endpoints: gather with return_exceptions so a single 401
        # doesn't leave the sibling requests as orphaned, never-retrieved tasks.
        results = await asyncio.gather(
            self.api.get_latestdata(),
            self.api.get_inverter(),
            self.api.get_powermeter(),
            self.api.get_battery(),
            self.api.get_configurations(),
            return_exceptions=True,
        )
        # If the token was rejected anywhere, trigger reauth exactly once.
        if any(isinstance(r, SonnenAuthError) for r in results):
            raise ConfigEntryAuthFailed("Auth-Token rejected")

        latestdata, inverter, powermeter, battery, configurations = (
            self._optional(r) for r in results
        )

        data: dict[str, Any] = {
            "status": status,
            "latestdata": latestdata or {},
            "inverter": inverter or {},
            "powermeter": powermeter or [],
            "battery": battery or {},
            "configurations": configurations or {},
        }
        data["derived"] = self._derive(data)
        return data

    @staticmethod
    def _optional(result: Any) -> Any:
        """Map a gather result: keep data, drop best-effort API errors, re-raise bugs."""
        if isinstance(result, SonnenApiError):
            LOGGER.debug("Optional endpoint failed, skipping: %s", result)
            return None
        if isinstance(result, BaseException):
            raise result
        return result

    @staticmethod
    def _derive(data: dict[str, Any]) -> dict[str, Any]:
        status = data["status"]
        if status.get("BatteryCharging"):
            state = "charging"
        elif status.get("BatteryDischarging"):
            state = "discharging"
        else:
            state = "standby"

        derived: dict[str, Any] = {"battery_state": state}

        cfg = data["configurations"]
        try:
            modules = int(cfg["IC_BatteryModules"])
            per_module = int(cfg["CM_MarketingModuleCapacity"])
            derived["installed_capacity_wh"] = modules * per_module
        except (KeyError, TypeError, ValueError):
            derived["installed_capacity_wh"] = None

        # State of health = measured full-charge capacity vs. nameplate capacity.
        fcc = data["battery"].get("fullchargecapacitywh")
        installed = derived["installed_capacity_wh"]
        if isinstance(fcc, (int, float)) and installed:
            derived["state_of_health_pct"] = round(fcc / installed * 100, 1)
        else:
            derived["state_of_health_pct"] = None

        return derived

    @property
    def inverter_max_power(self) -> int | None:
        """Max inverter power in W (from configurations), if known."""
        try:
            return int(self.data["configurations"]["IC_InverterMaxPower_w"])
        except (KeyError, TypeError, ValueError):
            return None

    @property
    def device_info(self) -> DeviceInfo:
        cfg = self.data.get("configurations", {}) if self.data else {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer="Sonnen",
            model="sonnenBatterie",
            name=DEFAULT_NAME,
            sw_version=cfg.get("DE_Software"),
            configuration_url=f"http://{self.api.host}",
        )
