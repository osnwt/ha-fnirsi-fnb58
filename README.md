# FNIRSI FNB58 USB Tester for Home Assistant

Custom Home Assistant integration for live BLE telemetry from the FNIRSI FNB58 USB Tester.

This integration is intentionally narrow in scope. It connects to the device through the Home Assistant Bluetooth stack, keeps a live BLE session open, and exposes current measurements as sensors. It does not implement device control, session history, export, or charting.

## Features

- Standard Home Assistant custom integration layout
- Works with Home Assistant Bluetooth and ESPHome BLE Proxy
- Persistent BLE connection for continuous live telemetry
- Automatic reconnect with bounded backoff
- Manual BLE reconnect service for development and recovery
- Parser support for newer framed firmware notifications
- Basic parser tests

## Exposed Sensors

- Voltage
- Current
- Power
- D+
- D-
- Temperature
- Energy (`Wh`)
- Capacity (`Ah`)
- Record time (`s`)
- Power-on time (`s`)

## Scope

The integration is designed for one task only: read current live values from the FNIRSI FNB58 over BLE.

Out of scope:

- Trigger or control commands beyond the required stream initialization
- Device configuration
- Session recording or history download
- Graphing or export
- Direct BLE scanning outside the Home Assistant Bluetooth stack

## Requirements

- Home Assistant with the built-in `Bluetooth` integration enabled
- A connectable Bluetooth path to the device
- For the intended deployment model: one or more ESPHome BLE Proxy nodes

Important behavior:

- The integration does not perform its own BLE scan.
- The device must first be discovered by the Home Assistant Bluetooth stack.
- In BLE Proxy setups this means the proxy must detect the device advertisement before the integration can connect.
- Some environments may require active scanning on the ESPHome side for the device to appear reliably.

## Installation

### Install with HACS

1. Open `HACS -> Integrations`.
2. Open the top-right menu and choose `Custom repositories`.
3. Add this repository URL:

```text
https://github.com/osnwt/ha-fnirsi-fnb58
```

4. Select repository type `Integration`.
5. Find `FNIRSI FNB58 USB Tester` in HACS and install it.
6. Restart Home Assistant.
7. Make sure the built-in `Bluetooth` integration is enabled.
8. Make sure your FNIRSI FNB58 is visible through Home Assistant Bluetooth or ESPHome BLE Proxy.
9. Add `FNIRSI FNB58 USB Tester` from `Settings -> Devices & Services`.
10. If the device is not listed, enter its BLE MAC address manually in the config flow.

### Manual Installation

1. Copy `custom_components/fnirsi_fnb58` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Make sure the built-in `Bluetooth` integration is enabled.
4. Make sure your FNIRSI FNB58 is visible through Home Assistant Bluetooth or ESPHome BLE Proxy.
5. Add `FNIRSI FNB58 USB Tester` from `Settings -> Devices & Services`.
6. If the device is not listed, enter its BLE MAC address manually in the config flow.

## How It Works

Once the device is available through the Home Assistant Bluetooth stack, the integration:

1. Resolves a connectable BLE device by address.
2. Connects through Home Assistant Bluetooth APIs.
3. Locates the notify and write characteristics.
4. Sends the known initialization commands:

```text
aa 81 00 f4
aa 82 00 a7
```

5. Subscribes to notifications from:

```text
0000ffe4-0000-1000-8000-00805f9b34fb
```

6. Uses a write characteristic matching:

```text
0000ffe9-0000-1000-8000-00805f9b34fb
```

7. Keeps the BLE connection open while the device remains available.
8. Marks entities unavailable on disconnect and retries with backoff.

## Protocol Notes

The parser supports the newer framed notification format used by recent firmware:

```text
0xAA, type, len, payload..., crc_lowbyte_of_xmodem
```

Currently handled frame types:

- `0x04`: precise `voltage`, `current`, `power` as `uint32 little-endian / 10000`
- `0x05`: temperature
- `0x06`: D+ and D-
- `0x07`: fallback `voltage` and `current` as `uint16 little-endian / 1000`
- `0x08`: energy, capacity, record runtime, power-on runtime

Measurement priority:

- Prefer `0x04` when available
- Use `0x07` only as fallback

Legacy fixed-offset packets are also parsed as a fallback path.

## Development

### Reload BLE Connection

For development or recovery, the integration exposes a service that restarts the BLE task without restarting the entire Home Assistant instance:

```yaml
action: fnirsi_fnb58.reload_connection
data:
  device_id: YOUR_DEVICE_ID
```

You may also pass `entry_id`. If only one FNIRSI FNB58 config entry exists, both parameters can be omitted.

This service:

- stops the current BLE client task
- reconnects to the device
- resends init commands
- resubscribes to notifications

It does not hot-reload Python code. Code changes still require a full Home Assistant restart.

### Logging

Useful debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.fnirsi_fnb58: debug
    homeassistant.components.bluetooth: debug
    bleak_retry_connector: debug
```

### Local Checks

Parser coverage lives in `tests/test_parser.py`.

Useful local check:

```bash
python3 -m compileall custom_components tests
```

## Limitations

- Auto-discovery currently relies on Bluetooth names that begin with `FNB58` or `FNIRSI`.
- Manual BLE address entry is available if discovery naming does not match.
- The integration assumes a stable enough notification stream for live telemetry.
- `energy_wh` and `capacity_ah` are exposed exactly as reported by the device protocol.
- The project currently has no config options UI.
- Branding behavior in the Home Assistant integrations list depends on the Home Assistant build and its handling of local custom integration brand assets.

## Project Layout

```text
custom_components/fnirsi_fnb58/
  __init__.py
  manifest.json
  config_flow.py
  ble.py
  parser.py
  coordinator.py
  sensor.py
  services.yaml
  brand/
  translations/

tests/
  test_parser.py
```
