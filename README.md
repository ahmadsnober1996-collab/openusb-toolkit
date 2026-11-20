# openusb-toolkit

Open-source USB device inspection toolkit written in Python.

`usbprobe` enumerates USB devices on the current machine and prints their bus
address, vendor/product IDs, class, manufacturer, product and serial strings
(when readable). It is the foundation layer for device-specific workflows built
on top of libusb.

## Requirements

- Python 3.10+
- Windows, Linux or macOS
- libusb is bundled through the `libusb-package` dependency (no system install)

## Install

```sh
python -m venv .venv
.venv/Scripts/activate    # Windows; use .venv/bin/activate on Linux/macOS
pip install -e .
```

## Usage

```sh
usbprobe list
usbprobe list --details
usbprobe list --json
```

Sample output:

```
BUS  ADDR  VID:PID    CLASS     MANUFACTURER  PRODUCT                                 SERIAL
---  ----  ---------  --------  ------------  --------------------------------------  ------
001  001   0cf3:e500  wireless  -             Qualcomm Atheros QCA9377 Bluetooth 4.1  -
001  002   174f:241a  misc      -             USB Composite Device                    -
```

With `--details`, each device is followed by its interfaces, alternate settings
and endpoints:

```
  - 0cf3:e500 iface 0 alt 0 (wireless)
      0x81 interrupt in max 16
      0x82 bulk in max 64
      0x02 bulk out max 64
```

Notes:
- On Windows, missing manufacturer/product/serial strings are filled from the
  system's PnP friendly name (SetupAPI, no driver required).
- Enumeration and descriptor reads are read-only. No device is opened, reset
  or written to.

## Roadmap

- [x] Enumerate devices with descriptors
- [x] Windows PnP friendly names without drivers
- [x] Show interfaces, endpoints and transfer types per device
- [ ] Read a device's configuration descriptor as standalone JSON
- [ ] Device-specific protocol modules (built only against public documentation)

## Legal

Use this tool only with devices you own or are authorized to inspect. Respect
vendor licenses and local law when probing hardware.

## License

MIT — see [LICENSE](LICENSE).
