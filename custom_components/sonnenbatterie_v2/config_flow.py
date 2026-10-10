"""Config flow for the sonnenBatterie v2 integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import SonnenApiError, SonnenAuthError, SonnenForbiddenError, SonnenV2Api
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, MIN_SCAN_INTERVAL

_TOKEN_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(
                CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")
            ): _TOKEN_SELECTOR,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
        }
    )


def _normalize_host(host: str) -> str:
    """Accept "192.168.1.5" as well as pasted URLs like "http://192.168.1.5/"."""
    host = host.strip().removeprefix("http://").removeprefix("https://")
    return host.rstrip("/")


class SonnenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def _async_validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Try to talk to the battery; return form errors (empty on success)."""
        api = SonnenV2Api(
            data[CONF_HOST], data[CONF_TOKEN], async_get_clientsession(self.hass)
        )
        try:
            await api.get_status()  # reachability (no token required)
            await api.get_configurations()  # validates the Auth-Token
        except SonnenAuthError:
            return {"base": "invalid_auth"}
        except SonnenForbiddenError:
            return {"base": "forbidden"}
        except SonnenApiError:  # unreachable, or not a v2 battery at this address
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating sonnenBatterie")
            return {"base": "unknown"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_HOST] = _normalize_host(user_input[CONF_HOST])
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()
            if not (errors := await self._async_validate(user_input)):
                return self.async_create_entry(
                    title=f"sonnenBatterie ({user_input[CONF_HOST]})",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST] = _normalize_host(user_input[CONF_HOST])
            # The host is the entry's unique id: keep it in sync, and don't let
            # this entry take over an address another entry already uses.
            if host != entry.unique_id:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
            if not (errors := await self._async_validate(user_input)):
                return self.async_update_reload_and_abort(
                    entry, unique_id=host, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema({**entry.data, **(user_input or {})}),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Triggered by ConfigEntryAuthFailed when the Auth-Token is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reauth only needs a fresh token; the host stays the same."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not (errors := await self._async_validate({**entry.data, **user_input})):
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): _TOKEN_SELECTOR}),
            description_placeholders={CONF_HOST: entry.data[CONF_HOST]},
            errors=errors,
        )
