"""Select platform: operating mode."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_EM_OPERATING_MODE, OPERATING_MODES, SELECTABLE_MODES
from .coordinator import SonnenConfigEntry
from .entity import SonnenEntity

# option name -> API value
_MODE_VALUES = {name: value for value, name in OPERATING_MODES.items()}

_DESCRIPTION = SelectEntityDescription(
    key="operating_mode_select",
    translation_key="operating_mode",
    icon="mdi:solar-power",
    entity_category=EntityCategory.CONFIG,
    options=list(SELECTABLE_MODES),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonnenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SonnenOperatingModeSelect(entry.runtime_data, _DESCRIPTION)])


class SonnenOperatingModeSelect(SonnenEntity, SelectEntity):
    """Read/set the operating mode via PUT /configurations (EM_OperatingMode)."""

    @property
    def current_option(self) -> str | None:
        mode = OPERATING_MODES.get(str(self.coordinator.data["status"].get("OperatingMode")))
        return mode if mode in SELECTABLE_MODES else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_configuration(
            CONF_EM_OPERATING_MODE, _MODE_VALUES[option]
        )
