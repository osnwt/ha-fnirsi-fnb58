from __future__ import annotations

import logging
from datetime import UTC, datetime

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .ble import FNB58BleClient
from .const import DOMAIN, NAME, STALE_AFTER
from .parser import TelemetrySample

_LOGGER = logging.getLogger(__name__)


class FNB58Coordinator(DataUpdateCoordinator[TelemetrySample | None]):
    """Hold latest live telemetry and connection state."""

    def __init__(self, hass, entry) -> None:
        super().__init__(hass, logger=_LOGGER, name=NAME)
        self.config_entry = entry
        self.address: str = entry.unique_id or entry.data["address"]
        self.connected = False
        self.last_seen: datetime | None = None
        self.client = FNB58BleClient(
            hass=hass,
            address=self.address,
            on_sample=self._handle_sample,
            on_availability_changed=self._handle_availability_changed,
        )
        self.data = None
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            connections={(CONNECTION_BLUETOOTH, self.address)},
            name=entry.title or NAME,
            manufacturer="FNIRSI",
            model="FNB58",
        )

    async def async_start(self) -> None:
        await self.client.start()

    async def async_stop(self) -> None:
        await self.client.stop()

    async def async_reload_connection(self) -> None:
        self.connected = False
        await self.client.stop()
        await self.client.start()
        self.async_update_listeners()

    @property
    def protocol(self) -> str | None:
        if self.data is None:
            return None
        return self.data.get("inferred_protocol")

    @property
    def is_available(self) -> bool:
        if not self.connected:
            return False
        if self.last_seen is None:
            return False
        return datetime.now(UTC) - self.last_seen <= STALE_AFTER

    def _handle_sample(self, sample: TelemetrySample) -> None:
        self.connected = True
        self.last_seen = datetime.now(UTC)
        self.async_set_updated_data(sample)

    def _handle_availability_changed(self, available: bool) -> None:
        self.connected = available and self.last_seen is not None
        self.async_update_listeners()

    async def _async_update_data(self) -> TelemetrySample | None:
        return self.data
