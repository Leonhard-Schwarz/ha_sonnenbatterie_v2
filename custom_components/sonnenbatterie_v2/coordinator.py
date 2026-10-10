"""Data update coordinator for the sonnenBatterie v2 integration."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SonnenApiError, SonnenAuthError, SonnenV2Api
from .const import DEFAULT_NAME, DOMAIN, LOGGER

type SonnenConfigEntry = ConfigEntry[SonnenCoordinator]

# /configurations is near-static (module count, inverter size, firmware), so it
# is re-read only every few minutes instead of on every poll.
CONFIGURATIONS_MAX_AGE = 600  # seconds


def to_int(value: Any) -> int | None:
    """Parse API values like "3" or 3 to int; None if missing/invalid."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class SonnenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the battery and exposes a combined data dict.

    The /status endpoint is mandatory (and needs no token); if it fails the whole
    update fails (UpdateFailed) so entities go unavailable instead of showing
    stale values. The remaining endpoints are best-effort: a single broken or
    transiently-500 endpoint must not blank out everything.
    """

    config_entry: SonnenConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SonnenConfigEntry,
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
        # Forced charge/discharge setpoints in W. The API can't read them back,
        # so the last written values live here (restored by the number entities).
        self.setpoints: dict[str, int] = {"charge": 0, "discharge": 0}
        self._configurations: dict[str, Any] = {}
        self._configurations_read_at: float | None = None
        self._failing: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            status = await self.api.get_status()
        except SonnenAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SonnenApiError as err:  # incl. connection errors
            raise UpdateFailed(str(err)) from err

        calls: dict[str, Awaitable[Any]] = {
            "inverter": self.api.get_inverter(),
            "powermeter": self.api.get_powermeter(),
            "battery": self.api.get_battery(),
        }
        if (
            self._configurations_read_at is None
            or time.monotonic() - self._configurations_read_at > CONFIGURATIONS_MAX_AGE
        ):
            calls["configurations"] = self.api.get_configurations()

        # return_exceptions so a single 401 doesn't leave the sibling requests
        # as orphaned, never-retrieved tasks.
        results = dict(
            zip(
                calls,
                await asyncio.gather(*calls.values(), return_exceptions=True),
                strict=True,
            )
        )
        # If the token was rejected anywhere, trigger reauth exactly once.
        if any(isinstance(r, SonnenAuthError) for r in results.values()):
            raise ConfigEntryAuthFailed("Auth-Token rejected")

        if "configurations" in results:
            configurations = self._optional("configurations", results["configurations"])
            if configurations is not None:
                self._configurations = configurations
                self._configurations_read_at = time.monotonic()

        data: dict[str, Any] = {
            "status": status,
            "inverter": self._optional("inverter", results["inverter"]) or {},
            "powermeter": self._optional("powermeter", results["powermeter"]) or [],
            "battery": self._optional("battery", results["battery"]) or {},
            "configurations": self._configurations,
        }
        data["derived"] = self._derive(data)
        return data

    def _optional(self, endpoint: str, result: Any) -> Any:
        """Unwrap a best-effort result: data, or None on API errors; re-raise bugs.

        Failures are logged once when they start and once when they end, not on
        every poll.
        """
        if isinstance(result, SonnenApiError):
            if endpoint not in self._failing:
                self._failing.add(endpoint)
                LOGGER.warning(
                    "Reading /%s failed, its sensors stay unknown until it recovers: %s",
                    endpoint,
                    result,
                )
            return None
        if isinstance(result, BaseException):
            raise result
        if endpoint in self._failing:
            self._failing.discard(endpoint)
            LOGGER.info("Reading /%s works again", endpoint)
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
        modules = to_int(cfg.get("IC_BatteryModules"))
        per_module = to_int(cfg.get("CM_MarketingModuleCapacity"))
        installed = modules * per_module if modules and per_module else None
        derived["installed_capacity_wh"] = installed

        # State of health = measured full-charge capacity vs. nameplate capacity.
        fcc = data["battery"].get("fullchargecapacitywh")
        if isinstance(fcc, (int, float)) and installed:
            derived["state_of_health_pct"] = round(fcc / installed * 100, 1)
        else:
            derived["state_of_health_pct"] = None

        return derived

    @property
    def inverter_max_power(self) -> int | None:
        """Max inverter power in W (from configurations), if known."""
        return to_int(self.data["configurations"].get("IC_InverterMaxPower_w"))

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

    # --- writes -------------------------------------------------------------
    async def async_set_configuration(self, key: str, value: int | str) -> None:
        """Write one configuration value, then refresh."""
        await _write(self.api.set_configuration(key, value))
        await self.async_request_refresh()

    async def async_set_setpoint(self, direction: str, watts: int) -> None:
        """Force charging/discharging with `watts`; 0 ends it.

        The battery holds a single setpoint, so forcing one direction ends the
        other one.
        """
        await _write(self.api.set_setpoint(direction, watts))
        if watts:
            self.setpoints = dict.fromkeys(self.setpoints, 0)
        self.setpoints[direction] = watts
        self.async_update_listeners()
        await self.async_request_refresh()


async def _write(call: Awaitable[Any]) -> None:
    """Await a write call and turn API errors into user-facing HA errors."""
    try:
        await call
    except SonnenAuthError as err:
        # A token without write access is valid for reads but gets 401 here.
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="write_denied"
        ) from err
    except SonnenApiError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="write_failed",
            translation_placeholders={"error": str(err)},
        ) from err
