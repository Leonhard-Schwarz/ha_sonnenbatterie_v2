"""Constants for the sonnenBatterie (v2 API) integration."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "sonnenbatterie_v2"
LOGGER = logging.getLogger(__package__)

DEFAULT_NAME: Final = "sonnenBatterie"
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 5

PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]

# --- Operating modes (EM_OperatingMode) -------------------------------------
# API value (a string, the way /status returns it) -> option name in HA.
# Names match the modes offered in the sonnenBatterie dashboard.
OPERATING_MODES: Final[dict[str, str]] = {
    "1": "manual",
    "2": "self_consumption",
    "4": "testing",
    "6": "module_extension",
    "10": "time_of_use",
    "11": "automatic_optimization",
}
# Modes that can be set from HA. "testing" and "module_extension" are
# installer/service modes: they are shown by the sensor but never set.
SELECTABLE_MODES: Final = (
    "self_consumption",
    "automatic_optimization",
    "time_of_use",
    "manual",
)

# Configuration keys writable via PUT /api/v2/configurations
CONF_EM_OPERATING_MODE: Final = "EM_OperatingMode"
CONF_EM_USOC: Final = "EM_USOC"
