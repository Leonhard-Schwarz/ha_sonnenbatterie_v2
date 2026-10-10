"""Tests for the sonnenBatterie v2 integration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TOKEN
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

HOST = "192.168.178.48"
TOKEN = "secret-token"
ENTRY_DATA = {CONF_HOST: HOST, CONF_TOKEN: TOKEN, CONF_SCAN_INTERVAL: 30}


def api_url(path: str, host: str = HOST) -> str:
    return f"http://{host}/api/v2/{path}"


def load_responses() -> dict[str, Any]:
    """Real API responses of a 3-module sonnenBatterie (firmware 1.40.5)."""
    return json.loads((Path(__file__).parent / "fixtures" / "responses.json").read_text())


def mock_battery(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    **overrides: dict[str, Any],
) -> None:
    """(Re-)register all read endpoints.

    `overrides` replaces an endpoint's mock, e.g. battery={"status": 500}.
    """
    aioclient_mock.clear_requests()
    for endpoint, body in load_responses().items():
        mock = overrides.get(
            endpoint, {"json": body, "headers": {"Content-Type": "application/json"}}
        )
        aioclient_mock.get(api_url(endpoint, host), **mock)
