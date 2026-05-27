"""Number platform: charge/discharge setpoints and battery reserve."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SonnenConfigEntry
from .api import SonnenApiError, SonnenV2Api
from .const import CONF_EM_USOC
from .entity import SonnenEntity

_DEFAULT_MAX_POWER = 5000


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class SonnenNumberEntityDescription(NumberEntityDescription):
    set_fn: Callable[[SonnenV2Api, int], Awaitable[Any]]
    value_fn: Callable[[dict[str, Any]], float | None] | None = None
    dynamic_max_from_inverter: bool = False


NUMBERS: tuple[SonnenNumberEntityDescription, ...] = (
    SonnenNumberEntityDescription(
        key="force_charge",
        translation_key="force_charge",
        icon="mdi:battery-plus-outline",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_step=100,
        mode=NumberMode.SLIDER,
        dynamic_max_from_inverter=True,
        set_fn=lambda api, v: api.set_setpoint("charge", v),
    ),
    SonnenNumberEntityDescription(
        key="force_discharge",
        translation_key="force_discharge",
        icon="mdi:battery-minus-outline",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_step=100,
        mode=NumberMode.SLIDER,
        dynamic_max_from_inverter=True,
        set_fn=lambda api, v: api.set_setpoint("discharge", v),
    ),
    SonnenNumberEntityDescription(
        key="battery_reserve",
        translation_key="battery_reserve",
        icon="mdi:battery-lock",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda d: _to_int(d["status"].get("BackupBuffer")),
        set_fn=lambda api, v: api.set_configuration(CONF_EM_USOC, int(v)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonnenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SonnenNumber(coordinator, description) for description in NUMBERS)


class SonnenNumber(SonnenEntity, RestoreNumber):
    """Charge/discharge setpoints (write-only) and battery reserve (read+write)."""

    entity_description: SonnenNumberEntityDescription

    def __init__(self, coordinator, description: SonnenNumberEntityDescription) -> None:
        super().__init__(coordinator, description)
        self._last_set: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last written value for the write-only setpoints."""
        await super().async_added_to_hass()
        if self.entity_description.value_fn is None:
            last = await self.async_get_last_number_data()
            if last is not None and last.native_value is not None:
                self._last_set = last.native_value

    @property
    def native_max_value(self) -> float:
        if self.entity_description.dynamic_max_from_inverter:
            return self.coordinator.inverter_max_power or _DEFAULT_MAX_POWER
        return self.entity_description.native_max_value

    @property
    def native_value(self) -> float | None:
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.coordinator.data)
        return self._last_set if self._last_set is not None else 0

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.entity_description.set_fn(self.coordinator.api, int(value))
        except SonnenApiError as err:
            raise HomeAssistantError(f"Write failed: {err}") from err
        if self.entity_description.value_fn is None:
            self._last_set = value
        await self.coordinator.async_request_refresh()
