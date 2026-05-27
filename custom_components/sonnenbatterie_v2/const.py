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
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.BUTTON,
]

# --- Operating modes (EM_OperatingMode) -------------------------------------
# Names match the modes offered in the sonnenBatterie dashboard.
# name -> numeric value used by the API
OPERATING_MODES: Final[dict[str, int]] = {
    "self_consumption": 2,
    "automatic_optimization": 11,
    "module_extension": 6,
    "time_of_use": 10,
    "manual": 1,
}
# numeric value (as string, the way the API returns it) -> name
OPERATING_MODES_REVERSE: Final[dict[str, str]] = {
    "1": "manual",
    "2": "self_consumption",
    "4": "testing",
    "6": "module_extension",
    "10": "time_of_use",
    "11": "automatic_optimization",
}

# Configuration keys writable via PUT /api/v2/configurations
CONF_EM_OPERATING_MODE: Final = "EM_OperatingMode"
CONF_EM_USOC: Final = "EM_USOC"
CONF_EM_TOU_SCHEDULE: Final = "EM_ToU_Schedule"

# Service field names
ATTR_POWER: Final = "power"
ATTR_VALUE: Final = "value"
ATTR_MODE: Final = "mode"
ATTR_SCHEDULE: Final = "schedule"
ATTR_ENABLED: Final = "enabled"
