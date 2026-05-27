"""Binary sensor platform: battery alarm and warning flags (from /battery)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SonnenConfigEntry
from .entity import SonnenEntity


@dataclass(frozen=True, kw_only=True)
class SonnenBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Binary sensor description with a value extractor against the coordinator data."""

    value_fn: Callable[[dict[str, Any]], bool | None]


def _flag(data: dict[str, Any], key: str) -> bool | None:
    """Map a numeric battery flag to bool, or None if the /battery read is missing."""
    value = data["battery"].get(key)
    return bool(value) if value is not None else None


# Names are provided via translations (entity.binary_sensor.<key>.name).
BINARY_SENSORS: tuple[SonnenBinarySensorEntityDescription, ...] = (
    SonnenBinarySensorEntityDescription(
        key="system_alarm",
        translation_key="system_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _flag(d, "systemalarm"),
    ),
    SonnenBinarySensorEntityDescription(
        key="system_warning",
        translation_key="system_warning",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _flag(d, "systemwarning"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonnenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sonnenBatterie binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SonnenBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class SonnenBinarySensor(SonnenEntity, BinarySensorEntity):
    """A sonnenBatterie binary sensor (battery alarm / warning)."""

    entity_description: SonnenBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
