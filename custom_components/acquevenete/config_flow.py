"""Config flow for Acquevenete."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AcquaveneteApiError, AcquaveneteAuthError, AcquaveneteClient
from .const import (
    CONF_PAGE,
    CONF_SUPPLY,
    CONF_TOKEN,
    DEFAULT_PAGE,
    DOMAIN,
)


class AcquaveneteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> str | None:
        """Return an error key or None if the credentials work."""
        session = async_get_clientsession(self.hass)
        client = AcquaveneteClient(
            session=session,
            token=data[CONF_TOKEN],
            supply_no=data[CONF_SUPPLY],
            page=data.get(CONF_PAGE, DEFAULT_PAGE),
        )
        try:
            ok = await client.async_validate()
        except AcquaveneteAuthError:
            return "invalid_auth"
        except AcquaveneteApiError:
            return "cannot_connect"
        return None if ok else "no_data"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input[CONF_SUPPLY]}")
            self._abort_if_unique_id_configured()
            error = await self._validate(user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"Acquevenete {user_input[CONF_SUPPLY]}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_TOKEN): str,
                vol.Required(CONF_SUPPLY): str,
                vol.Optional(CONF_PAGE, default=DEFAULT_PAGE): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._reauth_entry
        if user_input is not None:
            new_data = {**entry.data, CONF_TOKEN: user_input[CONF_TOKEN]}
            error = await self._validate(new_data)
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): str}),
            errors=errors,
        )
