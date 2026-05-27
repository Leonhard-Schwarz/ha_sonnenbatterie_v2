"""Sensor platform for the sonnenBatterie v2 integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import SonnenConfigEntry
from .const import OPERATING_MODES_REVERSE
from .coordinator import SonnenCoordinator
from .entity import SonnenEntity


@dataclass(frozen=True, kw_only=True)
class SonnenSensorEntityDescription(SensorEntityDescription):
    """Sensor description with a value extractor against the coordinator data."""

    value_fn: Callable[[dict[str, Any]], StateType]
    # Per-instance placeholders for the localized name (dynamic power-meter sensors).
    translation_placeholders: dict[str, str] | None = None


# --- small helpers ----------------------------------------------------------
def _round(value: Any, ndigits: int = 2) -> StateType:
    return round(value, ndigits) if isinstance(value, (int, float)) else None


def _pos(value: Any) -> StateType:
    """Positive part (>=0), or None if not numeric."""
    if not isinstance(value, (int, float)):
        return None
    return value if value > 0 else 0


def _neg_abs(value: Any) -> StateType:
    """Absolute value of the negative part, or None if not numeric."""
    if not isinstance(value, (int, float)):
        return None
    return abs(value) if value < 0 else 0


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _remaining_wh(d: dict[str, Any]) -> StateType:
    s = d["status"]
    value = s.get("RemainingCapacity_W")
    return value if value is not None else s.get("RemainingCapacity_Wh")


# Names are provided via translations (entity.sensor.<key>.name); see translations/*.json
SENSORS: tuple[SonnenSensorEntityDescription, ...] = (
    # --- status -------------------------------------------------------------
    SonnenSensorEntityDescription(
        key="battery_state",
        translation_key="battery_state",
        icon="mdi:battery-charging-medium",
        device_class=SensorDeviceClass.ENUM,
        options=["standby", "charging", "discharging"],
        value_fn=lambda d: d["derived"].get("battery_state"),
    ),
    SonnenSensorEntityDescription(
        key="consumption",
        translation_key="consumption",
        icon="mdi:home-lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d["status"].get("Consumption_W"),
    ),
    SonnenSensorEntityDescription(
        key="consumption_avg",
        translation_key="consumption_avg",
        icon="mdi:home-lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["status"].get("Consumption_Avg"),
    ),
    SonnenSensorEntityDescription(
        key="production",
        translation_key="production",
        icon="mdi:solar-power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        # _pos clamps small negative PV values at night to 0
        value_fn=lambda d: _pos(d["status"].get("Production_W")),
    ),
    SonnenSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        icon="mdi:transmission-tower",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d["status"].get("GridFeedIn_W"),
    ),
    SonnenSensorEntityDescription(
        key="grid_export",
        translation_key="grid_export",
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _pos(d["status"].get("GridFeedIn_W")),
    ),
    SonnenSensorEntityDescription(
        key="grid_import",
        translation_key="grid_import",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _neg_abs(d["status"].get("GridFeedIn_W")),
    ),
    SonnenSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda d: d["status"].get("Pac_total_W"),
    ),
    SonnenSensorEntityDescription(
        key="battery_charge",
        translation_key="battery_charge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _neg_abs(d["status"].get("Pac_total_W")),
    ),
    SonnenSensorEntityDescription(
        key="battery_discharge",
        translation_key="battery_discharge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _pos(d["status"].get("Pac_total_W")),
    ),
    SonnenSensorEntityDescription(
        key="soc_user",
        translation_key="soc_user",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda d: d["status"].get("USOC"),
    ),
    SonnenSensorEntityDescription(
        key="soc_real",
        translation_key="soc_real",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["status"].get("RSOC"),
    ),
    SonnenSensorEntityDescription(
        key="remaining_capacity",
        translation_key="remaining_capacity",
        icon="mdi:battery-charging",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=_remaining_wh,
    ),
    SonnenSensorEntityDescription(
        key="system_status",
        translation_key="system_status",
        icon="mdi:battery-check-outline",
        value_fn=lambda d: (
            v.lower() if isinstance(v := d["status"].get("SystemStatus"), str) else None
        ),
    ),
    SonnenSensorEntityDescription(
        key="operating_mode",
        translation_key="operating_mode",
        icon="mdi:state-machine",
        device_class=SensorDeviceClass.ENUM,
        options=["manual", "self_consumption", "testing", "module_extension", "time_of_use", "automatic_optimization"],
        value_fn=lambda d: OPERATING_MODES_REVERSE.get(
            str(d["status"].get("OperatingMode"))
        ),
    ),
    SonnenSensorEntityDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _round(d["status"].get("Fac"), 2),
    ),
    SonnenSensorEntityDescription(
        key="voltage_ac",
        translation_key="voltage_ac",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d["status"].get("Uac"), 1),
    ),
    SonnenSensorEntityDescription(
        key="voltage_battery",
        translation_key="voltage_battery",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d["status"].get("Ubat"), 1),
    ),
    SonnenSensorEntityDescription(
        key="backup_buffer",
        translation_key="backup_buffer",
        icon="mdi:battery-lock",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _to_int(d["status"].get("BackupBuffer")),
    ),
    SonnenSensorEntityDescription(
        key="battery_care",
        translation_key="battery_care",
        icon="mdi:wrench-clock",
        device_class=SensorDeviceClass.ENUM,
        options=["active", "inactive"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: "active" if d["status"].get("dischargeNotAllowed") else "inactive",
    ),
    # --- inverter -----------------------------------------------------------
    SonnenSensorEntityDescription(
        key="inverter_temperature",
        translation_key="inverter_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _round(d["inverter"].get("tmax"), 1),
    ),
    SonnenSensorEntityDescription(
        key="pv_power",
        translation_key="pv_power",
        icon="mdi:solar-power-variant",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d["inverter"].get("ppv"), 1),
    ),
    SonnenSensorEntityDescription(
        key="pv_voltage",
        translation_key="pv_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d["inverter"].get("upv"), 1),
    ),
    SonnenSensorEntityDescription(
        key="pv_current",
        translation_key="pv_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d["inverter"].get("ipv"), 2),
    ),
    # --- battery ------------------------------------------------------------
    SonnenSensorEntityDescription(
        key="battery_cycles",
        translation_key="battery_cycles",
        icon="mdi:battery-sync",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d["battery"].get("cyclecount"),
    ),
    SonnenSensorEntityDescription(
        key="cell_temperature_max",
        translation_key="cell_temperature_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d["battery"].get("maximumcelltemperature"), 1),
    ),
    SonnenSensorEntityDescription(
        key="system_dc_voltage",
        translation_key="system_dc_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _round(d["battery"].get("systemdcvoltage"), 2),
    ),
    # --- configurations -----------------------------------------------------
    SonnenSensorEntityDescription(
        key="module_count",
        translation_key="module_count",
        icon="mdi:battery",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: _to_int(d["configurations"].get("IC_BatteryModules")),
    ),
    SonnenSensorEntityDescription(
        key="inverter_max_power",
        translation_key="inverter_max_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _to_int(d["configurations"].get("IC_InverterMaxPower_w")),
    ),
    SonnenSensorEntityDescription(
        key="installed_capacity",
        translation_key="installed_capacity",
        icon="mdi:battery-high",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d["derived"].get("installed_capacity_wh"),
    ),
)


# --- dynamic powermeter sensors ---------------------------------------------
_PM_FIELDS: dict[str, tuple[SensorDeviceClass, str]] = {
    "w_total": (SensorDeviceClass.POWER, UnitOfPower.WATT),
    "w_l1": (SensorDeviceClass.POWER, UnitOfPower.WATT),
    "w_l2": (SensorDeviceClass.POWER, UnitOfPower.WATT),
    "w_l3": (SensorDeviceClass.POWER, UnitOfPower.WATT),
    "a_l1": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    "a_l2": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    "a_l3": (SensorDeviceClass.CURRENT, UnitOfElectricCurrent.AMPERE),
    "v_l1_n": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
    "v_l2_n": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
    "v_l3_n": (SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.VOLT),
}

def _pm_value(d: dict[str, Any], deviceid: Any, channel: Any, field: str) -> Any:
    """Look up a meter value by its (deviceid, channel) identity.

    Matching by identity instead of list position keeps each sensor pinned to
    its meter even if the /powermeter array is reordered between polls.
    """
    for meter in d.get("powermeter", []):
        if meter.get("deviceid") == deviceid and meter.get("channel") == channel:
            return meter.get(field)
    return None


def _powermeter_descriptions(
    coordinator: SonnenCoordinator,
) -> list[SonnenSensorEntityDescription]:
    """Build per-meter sensor descriptions.

    Names are localized via a shared per-field translation_key ("pm_<field>")
    plus a {meter} placeholder; see translations/*.json.
    """
    descriptions: list[SonnenSensorEntityDescription] = []
    meters = coordinator.data.get("powermeter", []) if coordinator.data else []
    for index, meter in enumerate(meters):
        deviceid = meter.get("deviceid")
        channel = meter.get("channel")
        direction = str(meter.get("direction", "meter"))
        # Stable identity for the entity key; fall back to position only if the
        # meter exposes no ids at all.
        key_device = deviceid if deviceid is not None else index
        key_channel = channel if channel is not None else index
        prefix = f"meter_{direction}_{key_device}_{key_channel}".lower()
        placeholders = {"meter": f"{direction.capitalize()} {key_channel}"}

        for field, (device_class, unit) in _PM_FIELDS.items():
            descriptions.append(
                SonnenSensorEntityDescription(
                    key=f"{prefix}_{field}",
                    translation_key=f"pm_{field}",
                    translation_placeholders=placeholders,
                    device_class=device_class,
                    state_class=SensorStateClass.MEASUREMENT,
                    native_unit_of_measurement=unit,
                    suggested_display_precision=2,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    value_fn=lambda d, _id=deviceid, _ch=channel, _f=field: _round(
                        _pm_value(d, _id, _ch, _f)
                    ),
                )
            )
        for field in ("kwh_imported", "kwh_exported"):
            descriptions.append(
                SonnenSensorEntityDescription(
                    key=f"{prefix}_{field}",
                    translation_key=f"pm_{field}",
                    translation_placeholders=placeholders,
                    device_class=SensorDeviceClass.ENERGY,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                    suggested_display_precision=3,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    value_fn=lambda d, _id=deviceid, _ch=channel, _f=field: _pm_value(
                        d, _id, _ch, _f
                    ),
                )
            )
    return descriptions


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonnenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sonnenBatterie sensors."""
    coordinator = entry.runtime_data
    entities: list[SonnenSensor] = [
        SonnenSensor(coordinator, description) for description in SENSORS
    ]
    entities += [
        SonnenSensor(coordinator, description)
        for description in _powermeter_descriptions(coordinator)
    ]
    async_add_entities(entities)


class SonnenSensor(SonnenEntity, SensorEntity):
    """A sonnenBatterie sensor."""

    entity_description: SonnenSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data)
