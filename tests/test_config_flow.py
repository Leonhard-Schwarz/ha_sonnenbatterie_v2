"""Tests for the config flow (setup, reconfigure, reauth)."""
from __future__ import annotations

from typing import Any

import pytest
from aiohttp import ClientError
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sonnenbatterie_v2.const import DOMAIN

from . import ENTRY_DATA, HOST, mock_battery


async def test_user_flow(hass: HomeAssistant, battery: AiohttpClientMocker) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    # A pasted URL is reduced to the plain host.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ENTRY_DATA, CONF_HOST: f" http://{HOST}/ "}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == HOST


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"status": {"exc": ClientError()}}, "cannot_connect"),
        ({"status": {"status": 404}}, "cannot_connect"),
        ({"configurations": {"status": 401}}, "invalid_auth"),
        ({"configurations": {"status": 403}}, "forbidden"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    overrides: dict[str, Any],
    error: str,
) -> None:
    mock_battery(aioclient_mock, **overrides)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # The form can be submitted again once the battery answers.
    mock_battery(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], ENTRY_DATA)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_new_host(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    new_host = "192.168.178.49"
    mock_battery(aioclient_mock, host=new_host)

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ENTRY_DATA, CONF_HOST: new_host}
    )
    await hass.async_block_till_done()  # let the entry reload finish
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == new_host
    # The unique id follows the host, so the old address is free again.
    assert config_entry.unique_id == new_host


async def test_reconfigure_to_address_of_other_entry(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    other = "192.168.178.50"
    MockConfigEntry(
        domain=DOMAIN, data={**ENTRY_DATA, CONF_HOST: other}, unique_id=other
    ).add_to_hass(hass)

    result = await config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ENTRY_DATA, CONF_HOST: other}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == HOST
    assert config_entry.unique_id == HOST


async def test_reauth(
    hass: HomeAssistant, battery: AiohttpClientMocker, config_entry: MockConfigEntry
) -> None:
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_TOKEN: "new-token"}
    )
    await hass.async_block_till_done()  # let the entry reload finish
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == {**ENTRY_DATA, CONF_TOKEN: "new-token"}
