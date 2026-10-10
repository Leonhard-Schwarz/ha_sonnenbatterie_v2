"""Shared fixtures."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.sonnenbatterie_v2.const import DOMAIN

from . import ENTRY_DATA, HOST, mock_battery


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components/."""


@pytest.fixture
def battery(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """A battery answering all read endpoints with the recorded responses."""
    mock_battery(aioclient_mock)
    return aioclient_mock


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"sonnenBatterie ({HOST})",
        data=ENTRY_DATA,
        unique_id=HOST,
        entry_id="01SONNENTEST",
    )
    entry.add_to_hass(hass)
    return entry
