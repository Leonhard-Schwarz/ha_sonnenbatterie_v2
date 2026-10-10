"""Tests for setup, polling and the entities' data."""
from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sonnenbatterie_v2.diagnostics import (
    async_get_config_entry_diagnostics,
)

from . import api_url, mock_battery

_METER_FIELDS = [
    "w_total", "w_l1", "w_l2", "w_l3", "a_l1", "a_l2", "a_l3",
    "v_l1_n", "v_l2_n", "v_l3_n", "kwh_imported", "kwh_exported",
]  # fmt: skip
_METER_KEYS = {
    f"{meter}_{field}"
    for meter in ("meter_production_0_1", "meter_consumption_1_2")
    for field in _METER_FIELDS
}
# Entity keys (unique id = "<entry_id>_<key>") of an existing installation.
# Changing any of them would orphan entities and break dashboards on update.
EXISTING_KEYS = {
    "system_alarm", "system_warning",
    "reset_all", "reset_charge", "reset_discharge",
    "force_charge", "force_discharge", "battery_reserve",
    "operating_mode_select",
    "battery_state", "consumption", "consumption_avg", "production",
    "grid_power", "grid_export", "grid_import",
    "battery_power", "battery_charge", "battery_discharge",
    "soc_user", "soc_real", "remaining_capacity", "system_status",
    "operating_mode", "frequency", "voltage_ac", "voltage_battery",
    "backup_buffer", "battery_care", "inverter_temperature",
    "pv_power", "pv_voltage", "pv_current", "battery_cycles",
    "cell_temperature_max", "cell_temperature_min", "system_dc_voltage",
    "battery_current", "cell_voltage_max", "cell_voltage_min",
    "module_count", "inverter_max_power", "installed_capacity",
    "full_charge_capacity", "state_of_health",
} | _METER_KEYS  # fmt: skip


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int = 31) -> None:
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    # Scheduled refreshes run as background tasks.
    await hass.async_block_till_done(wait_background_tasks=True)


def _entity_keys(hass: HomeAssistant, entry: MockConfigEntry) -> set[str]:
    return {
        e.unique_id.removeprefix(f"{entry.entry_id}_")
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }


def _state(hass: HomeAssistant, entity_id: str) -> str:
    return hass.states.get(entity_id).state


async def test_setup_and_unload(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert _entity_keys(hass, config_entry) == EXISTING_KEYS

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_values(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)

    assert _state(hass, "sensor.sonnenbatterie_consumption") == "336"
    assert _state(hass, "sensor.sonnenbatterie_production") == "645"
    assert _state(hass, "sensor.sonnenbatterie_battery_charge_discharge") == "-271"
    assert _state(hass, "sensor.sonnenbatterie_remaining_capacity") == "1289"
    assert _state(hass, "sensor.sonnenbatterie_state") == "charging"
    assert _state(hass, "sensor.sonnenbatterie_operating_mode") == "self_consumption"
    assert _state(hass, "sensor.sonnenbatterie_battery_care") == "inactive"
    # 5734.605 Wh measured / (3 modules * 2000 Wh)
    assert _state(hass, "sensor.sonnenbatterie_state_of_health") == "95.6"
    assert _state(hass, "binary_sensor.sonnenbatterie_system_alarm") == "off"
    assert _state(hass, "select.sonnenbatterie_operating_mode") == "self_consumption"
    assert float(_state(hass, "number.sonnenbatterie_battery_reserve")) == 0
    charge = hass.states.get("number.sonnenbatterie_force_charge")
    assert float(charge.state) == 0
    assert charge.attributes["max"] == 3000  # IC_InverterMaxPower_w


async def test_status_unreachable_retries_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_battery(aioclient_mock, status={"exc": ClientError()})
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_rejected_token_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_battery(aioclient_mock, battery={"status": 401})
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_failing_endpoint_is_logged_once(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    mock_battery(aioclient_mock, battery={"status": 500})
    await _setup(hass, config_entry)

    # The other endpoints keep working; only /battery's sensors are unknown.
    assert config_entry.state is ConfigEntryState.LOADED
    assert _state(hass, "sensor.sonnenbatterie_consumption") == "336"
    assert _state(hass, "binary_sensor.sonnenbatterie_system_alarm") == STATE_UNKNOWN

    await _poll(hass, freezer)
    assert caplog.text.count("Reading /battery failed") == 1

    mock_battery(aioclient_mock)
    await _poll(hass, freezer)
    assert "Reading /battery works again" in caplog.text
    assert _state(hass, "binary_sensor.sonnenbatterie_system_alarm") == "off"


async def test_meters_are_added_when_they_appear(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    mock_battery(aioclient_mock, powermeter={"status": 500})
    await _setup(hass, config_entry)
    assert _entity_keys(hass, config_entry) == EXISTING_KEYS - _METER_KEYS

    mock_battery(aioclient_mock)
    await _poll(hass, freezer)
    assert _entity_keys(hass, config_entry) == EXISTING_KEYS


async def test_configurations_are_read_rarely(
    hass: HomeAssistant,
    battery: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    def reads() -> int:
        return sum(str(url) == api_url("configurations") for _, url, _, _ in battery.mock_calls)

    await _setup(hass, config_entry)
    assert reads() == 1
    await _poll(hass, freezer)
    assert reads() == 1
    await _poll(hass, freezer, seconds=600)
    assert reads() == 2


async def test_diagnostics_redact_token(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    await _setup(hass, config_entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["config"]["token"] == "**REDACTED**"
    assert diagnostics["data"]["status"]["Consumption_W"] == 336
