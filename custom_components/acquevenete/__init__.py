"""The Acquevenete integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AcquaveneteClient
from .const import CONF_PAGE, CONF_SUPPLY, CONF_TOKEN, DEFAULT_PAGE, DOMAIN
from .coordinator import AcquaveneteCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Acquevenete from a config entry."""
    session = async_get_clientsession(hass)
    client = AcquaveneteClient(
        session=session,
        token=entry.data[CONF_TOKEN],
        supply_no=entry.data[CONF_SUPPLY],
        page=entry.data.get(CONF_PAGE, DEFAULT_PAGE),
    )

    coordinator = AcquaveneteCoordinator(hass, client, entry.data[CONF_SUPPLY])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
