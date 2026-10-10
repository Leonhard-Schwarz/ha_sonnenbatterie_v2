"""Button platform: end forced charging/discharging (setpoint 0)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SonnenConfigEntry
from .entity import SonnenEntity


@dataclass(frozen=True, kw_only=True)
class SonnenButtonEntityDescription(ButtonEntityDescription):
    directions: tuple[str, ...]  # setpoints to reset to 0


BUTTONS: tuple[SonnenButtonEntityDescription, ...] = (
    SonnenButtonEntityDescription(
        key="reset_all",
        translation_key="reset_all",
        icon="mdi:restore",
        entity_category=EntityCategory.CONFIG,
        directions=("charge", "discharge"),
    ),
    SonnenButtonEntityDescription(
        key="reset_charge",
        translation_key="reset_charge",
        icon="mdi:battery-off-outline",
        entity_category=EntityCategory.CONFIG,
        directions=("charge",),
    ),
    SonnenButtonEntityDescription(
        key="reset_discharge",
        translation_key="reset_discharge",
        icon="mdi:battery-off-outline",
        entity_category=EntityCategory.CONFIG,
        directions=("discharge",),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonnenConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SonnenButton(coordinator, description) for description in BUTTONS)


class SonnenButton(SonnenEntity, ButtonEntity):
    entity_description: SonnenButtonEntityDescription

    async def async_press(self) -> None:
        for direction in self.entity_description.directions:
            await self.coordinator.async_set_setpoint(direction, 0)
