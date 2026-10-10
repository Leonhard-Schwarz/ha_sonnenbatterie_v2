"""Tests for the control entities (select, numbers, buttons)."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from . import TOKEN, api_url

CHARGE = "number.sonnenbatterie_force_charge"
DISCHARGE = "number.sonnenbatterie_force_discharge"
MODE = "select.sonnenbatterie_operating_mode"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _writes(mock: AiohttpClientMocker) -> list[tuple[str, str, object]]:
    return [
        (method.upper(), str(url).removeprefix(api_url("")), data)
        for method, url, data, _ in mock.mock_calls
        if method.upper() != "GET"
    ]


def _setpoints(hass: HomeAssistant) -> tuple[float, float]:
    return float(hass.states.get(CHARGE).state), float(hass.states.get(DISCHARGE).state)


async def _set_number(hass: HomeAssistant, entity_id: str, value: float) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": value}, blocking=True
    )


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )


async def test_setpoints_and_reset_buttons(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    for path in ("charge/2000", "discharge/1000", "charge/0", "discharge/0"):
        battery.post(api_url(f"setpoint/{path}"))
    await _setup(hass, config_entry)

    await _set_number(hass, CHARGE, 2000)
    assert _setpoints(hass) == (2000, 0)

    # The battery has one setpoint: forcing discharge ends forced charging.
    await _set_number(hass, DISCHARGE, 1000)
    assert _setpoints(hass) == (0, 1000)

    # Resetting the other direction leaves the active setpoint alone ...
    await _press(hass, "button.sonnenbatterie_reset_forced_charge")
    assert _setpoints(hass) == (0, 1000)
    # ... and the reset buttons update the sliders.
    await _press(hass, "button.sonnenbatterie_reset_charge_discharge")
    assert _setpoints(hass) == (0, 0)

    assert _writes(battery) == [
        ("POST", "setpoint/charge/2000", None),
        ("POST", "setpoint/discharge/1000", None),
        ("POST", "setpoint/charge/0", None),
        ("POST", "setpoint/charge/0", None),
        ("POST", "setpoint/discharge/0", None),
    ]
    assert all(
        headers == {"Auth-Token": TOKEN}
        for method, _, _, headers in battery.mock_calls
        if method == "post"
    )


async def test_setpoint_is_restored(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(CHARGE, "1500"),
                {
                    "native_value": 1500,
                    "native_min_value": 0,
                    "native_max_value": 3000,
                    "native_step": 100,
                    "native_unit_of_measurement": "W",
                },
            )
        ],
    )
    await _setup(hass, config_entry)
    assert _setpoints(hass) == (1500, 0)


async def test_operating_mode(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    battery.put(api_url("configurations"))
    await _setup(hass, config_entry)

    # Installer/service modes can't be selected.
    assert hass.states.get(MODE).attributes["options"] == [
        "self_consumption",
        "automatic_optimization",
        "time_of_use",
        "manual",
    ]
    await hass.services.async_call(
        "select", "select_option", {"entity_id": MODE, "option": "manual"}, blocking=True
    )
    assert _writes(battery) == [("PUT", "configurations", {"EM_OperatingMode": "1"})]


async def test_battery_reserve(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    battery.put(api_url("configurations"))
    await _setup(hass, config_entry)

    await _set_number(hass, "number.sonnenbatterie_battery_reserve", 20)
    assert _writes(battery) == [("PUT", "configurations", {"EM_USOC": "20"})]


async def test_write_without_write_access(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    """A read-only token gets 401 on writes: show a hint, don't start reauth."""
    battery.post(api_url("setpoint/charge/2000"), status=401)
    await _setup(hass, config_entry)

    with pytest.raises(HomeAssistantError) as err:
        await _set_number(hass, CHARGE, 2000)
    assert err.value.translation_key == "write_denied"
    assert _setpoints(hass) == (0, 0)
    assert not hass.config_entries.flow.async_progress()
