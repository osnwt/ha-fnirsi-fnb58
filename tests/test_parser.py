from __future__ import annotations

import struct

from custom_components.fnirsi_fnb58.parser import FNB58Parser


def make_frame(packet_type: int, payload: bytes) -> bytes:
    frame = bytes([0xAA, packet_type, len(payload), *payload])
    checksum = FNB58Parser.crc8_from_xmodem(frame)
    return frame + bytes([checksum])


def test_parses_framed_stream_across_split_notifications() -> None:
    parser = FNB58Parser()

    temp_payload = bytes([0, 0, 0, 0, 1]) + struct.pack("<H", 235)
    dpdn_payload = struct.pack("<HHH", 600, 2100, 0)
    group_payload = struct.pack("<BIIII", 1, 12345, 23456, 789, 4567)
    bus_payload = struct.pack("<HH", 5000, 1234)

    stream = b"".join(
        [
            make_frame(0x05, temp_payload),
            make_frame(0x06, dpdn_payload),
            make_frame(0x08, group_payload),
            make_frame(0x07, bus_payload),
        ]
    )

    split_at = 11
    assert parser.feed_data(stream[:split_at]) == []

    readings = parser.feed_data(stream[split_at:])
    assert len(readings) == 1

    reading = readings[0]
    assert reading["voltage"] == 5.0
    assert reading["current"] == 1.234
    assert reading["power"] == 6.17
    assert reading["temperature"] == 23.5
    assert reading["dp"] == 0.6
    assert reading["dn"] == 2.1
    assert reading["energy_wh"] == 0.12345
    assert reading["capacity_ah"] == 0.23456
    assert reading["record_seconds"] == 789
    assert reading["power_on_seconds"] == 4567
    assert reading["inferred_protocol"] == "framed_fallback"


def test_prefers_precise_type_04_measurement_when_present() -> None:
    parser = FNB58Parser()
    frame = bytes.fromhex(
        "aa0606e30ce30c050069"
        "aa07042d4fd9070a"
        "aa040ccb170300824e00006937060024"
        "aa0507f389010001780144"
    )

    readings = parser.feed_data(frame)
    assert len(readings) == 1

    reading = readings[0]
    assert reading["voltage"] == 20.2699
    assert reading["current"] == 2.0098
    assert reading["power"] == 40.7401
    assert reading["dp"] == 3.299
    assert reading["dn"] == 3.299
    assert reading["temperature"] == 37.6
    assert reading["inferred_protocol"] == "framed_precise"


def test_parses_legacy_fixed_offset_packet() -> None:
    parser = FNB58Parser()
    payload = bytearray(40)
    struct.pack_into("<iii", payload, 21, 51234, 9876, 50602)

    readings = parser.feed_data(bytes(payload))
    assert len(readings) == 1

    reading = readings[0]
    assert reading["voltage"] == 5.1234
    assert reading["current"] == 0.9876
    assert reading["power"] == 5.0602
    assert reading["inferred_protocol"] == "legacy"


def test_ignores_invalid_checksum_frame() -> None:
    parser = FNB58Parser()
    good = make_frame(0x07, struct.pack("<HH", 5000, 1000))
    bad = good[:-1] + bytes([good[-1] ^ 0xFF])

    assert parser.feed_data(bad) == []
    readings = parser.feed_data(good)
    assert len(readings) == 1
