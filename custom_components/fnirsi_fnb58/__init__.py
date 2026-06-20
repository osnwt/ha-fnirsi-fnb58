from __future__ import annotations

import voluptuous as vol
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import async_get as async_get_device_registry

from .const import DOMAIN

PLATFORMS = ["sensor"]
SERVICE_RELOAD_CONNECTION = "reload_connection"


async def _async_handle_reload_connection(hass, call: ServiceCall) -> None:
    coordinators = hass.data.get(DOMAIN, {})
    coordinator = None

    entry_id = call.data.get("entry_id")
    if entry_id is not None:
        coordinator = coordinators.get(entry_id)
    else:
        device_id = call.data.get(ATTR_DEVICE_ID)
        if device_id is not None:
            device_registry = async_get_device_registry(hass)
            device = device_registry.async_get(device_id)
            if device is not None:
                for config_entry_id in device.config_entries:
                    coordinator = coordinators.get(config_entry_id)
                    if coordinator is not None:
                        break
        elif len(coordinators) == 1:
            coordinator = next(iter(coordinators.values()))

    if coordinator is None:
        raise vol.Invalid(
            "Unable to resolve FNIRSI FNB58 config entry. Provide entry_id, device_id, or keep only one entry configured."
        )

    await coordinator.async_reload_connection()


async def async_setup(hass, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    if not hass.services.has_service(DOMAIN, SERVICE_RELOAD_CONNECTION):
        hass.services.async_register(
            DOMAIN,
            SERVICE_RELOAD_CONNECTION,
            _async_handle_reload_connection,
            schema=vol.Schema(
                {
                    vol.Optional("entry_id"): cv.string,
                    vol.Optional(ATTR_DEVICE_ID): cv.string,
                }
            ),
        )
    return True


async def async_setup_entry(hass, entry) -> bool:
    from .coordinator import FNB58Coordinator

    coordinator = FNB58Coordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_stop()
        if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, SERVICE_RELOAD_CONNECTION):
            hass.services.async_remove(DOMAIN, SERVICE_RELOAD_CONNECTION)
    return unload_ok
