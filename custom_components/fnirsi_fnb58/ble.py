from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import (
    BLE_NOTIFY_SHORT_UUIDS,
    BLE_NOTIFY_UUID,
    BLE_WRITE_SHORT_UUIDS,
    BLE_WRITE_UUID,
    DEFAULT_BACKOFF_INITIAL,
    DEFAULT_BACKOFF_MAX,
    INIT_COMMANDS,
)
from .parser import FNB58Parser, TelemetrySample

_LOGGER = logging.getLogger(__name__)


class FNB58BleClient:
    """Persistent BLE reader for FNIRSI FNB58."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        on_sample: Callable[[TelemetrySample], None],
        on_availability_changed: Callable[[bool], None],
    ) -> None:
        self.hass = hass
        self.address = address
        self._on_sample = on_sample
        self._on_availability_changed = on_availability_changed
        self._parser = FNB58Parser()
        self._task: asyncio.Task[None] | None = None
        self._client: BleakClientWithServiceCache | None = None
        self._stopped = False
        self._available = False

    @property
    def parser(self) -> FNB58Parser:
        return self._parser

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopped = False
        self._task = self.hass.async_create_task(self._run())

    async def stop(self) -> None:
        self._stopped = True
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self._disconnect()
        self._set_available(False)

    async def _run(self) -> None:
        backoff = DEFAULT_BACKOFF_INITIAL

        while not self._stopped:
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass,
                self.address,
                connectable=True,
            )
            if ble_device is None:
                self._set_available(False)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, DEFAULT_BACKOFF_MAX)
                continue

            disconnected_event = asyncio.Event()

            def _handle_disconnect(_: BleakClientWithServiceCache) -> None:
                disconnected_event.set()

            try:
                await self._connect_and_stream(ble_device, disconnected_event, _handle_disconnect)
                backoff = DEFAULT_BACKOFF_INITIAL
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("FNB58 connection loop failed for %s: %s", self.address, err)
                self._set_available(False)
                await self._disconnect()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, DEFAULT_BACKOFF_MAX)

    async def _connect_and_stream(
        self,
        ble_device: BLEDevice,
        disconnected_event: asyncio.Event,
        disconnected_callback: Callable[[BleakClientWithServiceCache], None],
    ) -> None:
        _LOGGER.debug("Connecting to FNB58 %s via HA Bluetooth stack", self.address)
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.address,
            disconnected_callback=disconnected_callback,
            max_attempts=1,
        )
        self._client = client

        notify_char = self._find_characteristic(client, BLE_NOTIFY_SHORT_UUIDS, "notify")
        if notify_char is None:
            notify_char = client.services.get_characteristic(BLE_NOTIFY_UUID)
        if notify_char is None:
            raise BleakError(f"Notify characteristic {BLE_NOTIFY_UUID} not found")

        write_char = self._find_characteristic(
            client,
            BLE_WRITE_SHORT_UUIDS,
            "write-without-response",
        ) or self._find_characteristic(client, BLE_WRITE_SHORT_UUIDS, "write")
        if write_char is None:
            write_char = client.services.get_characteristic(BLE_WRITE_UUID)

        def _notification_handler(_: BleakGATTCharacteristic, data: bytearray) -> None:
            readings = self._parser.feed_data(bytes(data))
            if not readings:
                return
            self._set_available(True)
            for reading in readings:
                self._on_sample(reading)

        await client.start_notify(notify_char, _notification_handler)
        try:
            if write_char is not None:
                for command in INIT_COMMANDS:
                    await client.write_gatt_char(write_char, command, response=False)
                    await asyncio.sleep(0.1)
            self._set_available(True)
            await disconnected_event.wait()
        finally:
            self._set_available(False)
            try:
                await client.stop_notify(notify_char)
            except Exception:  # noqa: BLE001
                pass
            await self._disconnect()

    async def _disconnect(self) -> None:
        client = self._client
        self._client = None
        if client is not None and client.is_connected:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass

    def _find_characteristic(
        self,
        client: BleakClientWithServiceCache,
        short_uuids: tuple[str, ...],
        required_property: str,
    ) -> BleakGATTCharacteristic | None:
        required = required_property.lower()
        for short_uuid in short_uuids:
            prefix = f"0000{short_uuid.lower()}"
            for service in client.services:
                for char in service.characteristics:
                    if not char.uuid.lower().startswith(prefix):
                        continue
                    if required not in {prop.lower() for prop in char.properties}:
                        continue
                    return char
        return None

    def _set_available(self, available: bool) -> None:
        if self._available == available:
            return
        self._available = available
        self._on_availability_changed(available)
