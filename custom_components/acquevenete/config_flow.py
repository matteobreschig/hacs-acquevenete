"""Config flow for Acquevenete (username + password login)."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AcquaveneteApiError, AcquaveneteAuthError, AcquaveneteClient
from .auth import AcquaveneteAuth
from .const import (
    CONF_PAGE,
    CONF_PASSWORD,
    CONF_PRICE,
    CONF_PRICE_ENTITY,
    CONF_SUPPLY,
    CONF_USERNAME,
    DEFAULT_PAGE,
    DOMAIN,
)


class AcquaveneteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AcquaveneteOptionsFlow()

    async def _validate(self, data: dict[str, Any]) -> str | None:
        """Return an error key or None if login + data fetch work."""
        session = async_get_clientsession(self.hass)
        auth = AcquaveneteAuth(session, data[CONF_USERNAME], data[CONF_PASSWORD])
        client = AcquaveneteClient(
            session=session,
            auth=auth,
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
            await self.async_set_unique_id(user_input[CONF_SUPPLY])
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
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
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
            new_data = {**entry.data, **user_input}
            error = await self._validate(new_data)
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )


class AcquaveneteOptionsFlow(OptionsFlow):
    """Water price used to build the cost statistic for the Energy dashboard."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # Drop empty values so "no price" really means no cost statistic.
            data = {k: v for k, v in user_input.items() if v not in (None, "")}
            return self.async_create_entry(data=data)

        options = self.config_entry.options
        price_entity = options.get(CONF_PRICE_ENTITY)
        price = options.get(CONF_PRICE)
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_PRICE_ENTITY,
                    description={"suggested_value": price_entity},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=["input_number", "number", "sensor"]
                    )
                ),
                vol.Optional(
                    CONF_PRICE, description={"suggested_value": price}
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=100,
                        step=0.001,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
