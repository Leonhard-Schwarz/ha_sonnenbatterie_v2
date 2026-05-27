"""Base entity for the sonnenBatterie v2 integration."""
from __future__ import annotations

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SonnenCoordinator


class SonnenEntity(CoordinatorEntity[SonnenCoordinator]):
    """Common base: device info + stable unique_id, name via has_entity_name."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: SonnenCoordinator, description: EntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        # Stable, IP-independent unique id (entry_id never changes for an entry).
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
        # Dynamic entities (e.g. power-meter sensors) localize their name via a
        # shared translation_key plus per-instance placeholders.
        if placeholders := getattr(description, "translation_placeholders", None):
            self._attr_translation_placeholders = placeholders
