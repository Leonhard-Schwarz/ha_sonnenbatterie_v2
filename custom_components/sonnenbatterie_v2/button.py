"""Button platform: reset charge/discharge setpoints to 0."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SonnenConfigEntry
from .api import SonnenApiError, SonnenV2Api
from .entity import SonnenEntity


@dataclass(frozen=True, kw_only=True)
class SonnenButtonEntityDescription(ButtonEntityDescription):
    press_fn: Callable[[SonnenV2Api], Awaitable[object]]


async def _reset_all(api: SonnenV2Api) -> None:
    await api.set_setpoint("charge", 0)
    await api.set_setpoint("discharge", 0)


BUTTONS: tuple[SonnenButtonEntityDescription, ...] = (
    SonnenButtonEntityDescription(
        key="reset_all",
        translation_key="reset_all",
        icon="mdi:restore",
        entity_category=EntityCategory.CONFIG,
        press_fn=_reset_all,
    ),
    SonnenButtonEntityDescription(
        key="reset_charge",
        translation_key="reset_charge",
        icon="mdi:battery-off-outline",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda api: api.set_setpoint("charge", 0),
    ),
    SonnenButtonEntityDescription(
        key="reset_discharge",
        translation_key="reset_discharge",
        icon="mdi:battery-off-outline",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda api: api.set_setpoint("discharge", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonnenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(SonnenButton(coordinator, description) for description in BUTTONS)


class SonnenButton(SonnenEntity, ButtonEntity):
    entity_description: SonnenButtonEntityDescription

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.coordinator.api)
        except SonnenApiError as err:
            raise HomeAssistantError(f"Action failed: {err}") from err
        await self.coordinator.async_request_refresh()
