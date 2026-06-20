from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "fnirsi_fnb58"
NAME: Final = "FNIRSI FNB58 USB Tester"

BLE_NOTIFY_UUID: Final = "0000ffe4-0000-1000-8000-00805f9b34fb"
BLE_WRITE_UUID: Final = "0000ffe9-0000-1000-8000-00805f9b34fb"
BLE_NOTIFY_SHORT_UUIDS: Final = ("ffe4", "ffe1")
BLE_WRITE_SHORT_UUIDS: Final = ("ffe9", "ffe1")
INIT_COMMANDS: Final = (
    bytes((0xAA, 0x81, 0x00, 0xF4)),
    bytes((0xAA, 0x82, 0x00, 0xA7)),
)

DEFAULT_BACKOFF_INITIAL: Final = 3
DEFAULT_BACKOFF_MAX: Final = 60
STALE_AFTER: Final = timedelta(seconds=20)
