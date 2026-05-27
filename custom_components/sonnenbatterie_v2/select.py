"""Select platform: operating mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SonnenConfigEntry
from .api import SonnenApiError
from .const import CONF_EM_OPERATING_MODE, OPERATING_MODES, OPERATING_MODES_REVERSE
from .entity import SonnenEntity

_OPTIONS = [
    "self_consumption",
    "automatic_optimization",
    "module_extension",
    "time_of_use",
    "manual",
]

_DESCRIPTION = SelectEntityDescription(
    key="operating_mode_select",
    translation_key="operating_mode",
    icon="mdi:solar-power",
    entity_category=EntityCategory.CONFIG,
    options=_OPTIONS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonnenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([SonnenOperatingModeSelect(entry.runtime_data, _DESCRIPTION)])


class SonnenOperatingModeSelect(SonnenEntity, SelectEntity):
    """Read/set the operating mode via PUT /configurations (EM_OperatingMode)."""

    _attr_options = _OPTIONS

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.data["status"].get("OperatingMode")
        name = OPERATING_MODES_REVERSE.get(str(mode))
        return name if name in _OPTIONS else None

    async def async_select_option(self, option: str) -> None:
        try:
            await self.coordinator.api.set_configuration(
                CONF_EM_OPERATING_MODE, OPERATING_MODES[option]
            )
        except SonnenApiError as err:
            raise HomeAssistantError(f"Failed to set operating mode: {err}") from err
        await self.coordinator.async_request_refresh()
