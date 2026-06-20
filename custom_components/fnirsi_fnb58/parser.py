from __future__ import annotations

import binascii
import struct
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

TelemetrySample = dict[str, Any]


class FNB58Parser:
    """Parse FNIRSI FNB58 BLE notifications."""

    PACKET_LENGTHS = {
        0x03: 14,
        0x04: 12,
        0x05: 7,
        0x06: 6,
        0x07: 4,
        0x08: 17,
    }

    def __init__(self) -> None:
        self._rx_buffer = bytearray()
        self._latest = {
            "dp": 0.0,
            "dn": 0.0,
            "temperature": 0.0,
            "energy_wh": 0.0,
            "capacity_ah": 0.0,
            "record_seconds": 0,
            "power_on_seconds": 0,
        }
        self._metadata: dict[str, Any] = {}

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    @staticmethod
    def crc8_from_xmodem(data: bytes) -> int:
        """Return the low byte of CRC-16/XMODEM, matching the BLE framing."""
        return binascii.crc_hqx(data, 0) & 0xFF

    def feed_data(self, data: bytes) -> list[TelemetrySample]:
        """Parse BLE notifications from either the new framed or legacy format."""
        framed_readings, had_framed_context = self._parse_framed_measurements(data)
        if framed_readings:
            return framed_readings
        if had_framed_context:
            return []
        return self._parse_legacy_data(data)

    def _parse_framed_packets(self, data: bytes) -> list[tuple[int, bytes]]:
        self._rx_buffer.extend(data)
        packets: list[tuple[int, bytes]] = []
        index = 0

        while index < len(self._rx_buffer):
            if self._rx_buffer[index] != 0xAA:
                index += 1
                continue

            if index + 2 >= len(self._rx_buffer):
                break

            packet_type = self._rx_buffer[index + 1]
            payload_len = self._rx_buffer[index + 2]
            expected_len = self.PACKET_LENGTHS.get(packet_type)

            if expected_len is None or payload_len != expected_len:
                index += 1
                continue

            frame_end = index + 4 + payload_len
            if frame_end > len(self._rx_buffer):
                break

            payload_start = index + 3
            payload_end = payload_start + payload_len
            payload = bytes(self._rx_buffer[payload_start:payload_end])
            checksum = self._rx_buffer[payload_end]
            frame = bytes(self._rx_buffer[index:payload_end])

            if checksum != self.crc8_from_xmodem(frame):
                index += 1
                continue

            packets.append((packet_type, payload))
            index = frame_end

        if index:
            del self._rx_buffer[:index]

        return packets

    def _build_reading(
        self,
        voltage: float,
        current: float,
        power: float | None = None,
        inferred_protocol: str = "unknown",
    ) -> TelemetrySample:
        if power is None:
            power = voltage * current

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "voltage": round(voltage, 5),
            "current": round(current, 5),
            "power": round(power, 5),
            "dp": round(self._latest["dp"], 3),
            "dn": round(self._latest["dn"], 3),
            "temperature": round(self._latest["temperature"], 1),
            "energy_wh": round(self._latest["energy_wh"], 5),
            "capacity_ah": round(self._latest["capacity_ah"], 5),
            "record_seconds": self._latest["record_seconds"],
            "power_on_seconds": self._latest["power_on_seconds"],
            "inferred_protocol": inferred_protocol,
        }

    def _parse_framed_measurements(self, data: bytes) -> tuple[list[TelemetrySample], bool]:
        had_framed_context = bool(self._rx_buffer) or (len(data) > 0 and data[0] == 0xAA)
        packets = self._parse_framed_packets(data)
        if not packets:
            return [], had_framed_context

        primary_measurement: dict[str, float] | None = None
        inferred_protocol = "framed"

        for packet_type, payload in packets:
            if packet_type == 0x03:
                model, fw_raw, serial = struct.unpack_from("<HHL", payload, 0)
                self._metadata.update(
                    {
                        "model": model,
                        "firmware_version": round(fw_raw / 100, 2),
                        "serial": serial,
                        "group_max": payload[12],
                        "group_current": payload[13],
                    }
                )
            elif packet_type == 0x04:
                voltage_raw, current_raw, power_raw = struct.unpack_from("<III", payload, 0)
                primary_measurement = {
                    "voltage": voltage_raw / 10000.0,
                    "current": current_raw / 10000.0,
                    "power": power_raw / 10000.0,
                }
                inferred_protocol = "framed_precise"
            elif packet_type == 0x05:
                sign = 1 if payload[4] > 0 else -1
                self._latest["temperature"] = sign * struct.unpack_from("<H", payload, 5)[0] / 10.0
            elif packet_type == 0x06:
                dp, dn = struct.unpack_from("<HH", payload, 0)
                self._latest["dp"] = dp / 1000.0
                self._latest["dn"] = dn / 1000.0
            elif packet_type == 0x07:
                voltage_raw, current_raw = struct.unpack_from("<HH", payload, 0)
                if primary_measurement is None:
                    voltage = voltage_raw / 1000.0
                    current = current_raw / 1000.0
                    primary_measurement = {
                        "voltage": voltage,
                        "current": current,
                        "power": voltage * current,
                    }
                    inferred_protocol = "framed_fallback"
            elif packet_type == 0x08:
                self._latest["energy_wh"] = struct.unpack_from("<L", payload, 1)[0] / 100000.0
                self._latest["capacity_ah"] = struct.unpack_from("<L", payload, 5)[0] / 100000.0
                self._latest["record_seconds"] = struct.unpack_from("<L", payload, 9)[0]
                self._latest["power_on_seconds"] = struct.unpack_from("<L", payload, 13)[0]

        if not primary_measurement:
            return [], True

        voltage = primary_measurement["voltage"]
        if not (0.0 <= voltage <= 150.0):
            return [], True

        return [
            self._build_reading(
                primary_measurement["voltage"],
                primary_measurement["current"],
                primary_measurement["power"],
                inferred_protocol=inferred_protocol,
            )
        ], True

    def _parse_legacy_data(self, data: bytes) -> list[TelemetrySample]:
        offset = 21
        scale = 10000

        if len(data) < offset + 12:
            return []

        try:
            voltage, current, power = (
                value / scale for value in struct.unpack_from("<iii", data, offset)
            )
        except struct.error:
            return []

        if not (0.0 <= voltage <= 150.0):
            return []

        return [self._build_reading(voltage, current, power, inferred_protocol="legacy")]

    def snapshot(self) -> dict[str, Any]:
        return deepcopy(self._latest)
