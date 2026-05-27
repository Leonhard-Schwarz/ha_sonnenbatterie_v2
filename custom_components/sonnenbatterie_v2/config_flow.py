"""Config flow for the sonnenBatterie v2 integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SonnenAuthError,
    SonnenConnectionError,
    SonnenForbiddenError,
    SonnenV2Api,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, MIN_SCAN_INTERVAL


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
        }
    )


def _reauth_schema() -> vol.Schema:
    """Reauth only needs a fresh token; the host stays the same."""
    return vol.Schema({vol.Required(CONF_TOKEN): str})


class SonnenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 1

    async def _validate(self, user_input: dict[str, Any]) -> None:
        """Raise SonnenConnectionError / SonnenAuthError on failure."""
        api = SonnenV2Api(
            user_input[CONF_HOST],
            user_input[CONF_TOKEN],
            async_get_clientsession(self.hass),
        )
        await api.get_status()          # reachability (no token required)
        await api.get_configurations()  # validates the Auth-Token

    def _errors_for(self, err: Exception) -> dict[str, str]:
        if isinstance(err, SonnenAuthError):
            return {"base": "invalid_auth"}
        if isinstance(err, SonnenForbiddenError):
            return {"base": "forbidden"}
        if isinstance(err, SonnenConnectionError):
            return {"base": "cannot_connect"}
        LOGGER.exception("Unexpected error validating sonnenBatterie", exc_info=err)
        return {"base": "unknown"}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._validate(user_input)
            except Exception as err:  # noqa: BLE001
                errors = self._errors_for(err)
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
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
            try:
                await self._validate(user_input)
            except Exception as err:  # noqa: BLE001
                errors = self._errors_for(err)
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
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
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._validate({**entry.data, **user_input})
            except Exception as err:  # noqa: BLE001
                errors = self._errors_for(err)
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_reauth_schema(),
            description_placeholders={CONF_HOST: entry.data[CONF_HOST]},
            errors=errors,
        )
