"""Command-line interface for openusb-toolkit."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field

import libusb_package
import usb.core
import usb.util

from .windows_names import windows_friendly_names

CLASS_NAMES = {
    0x00: "per-interface",
    0x01: "audio",
    0x02: "cdc-communications",
    0x03: "hid",
    0x05: "physical",
    0x06: "image",
    0x07: "printer",
    0x08: "mass-storage",
    0x09: "hub",
    0x0A: "cdc-data",
    0x0B: "smart-card",
    0x0D: "content-security",
    0x0E: "video",
    0x0F: "personal-healthcare",
    0x10: "audio-video",
    0xDC: "diagnostic",
    0xE0: "wireless",
    0xEF: "misc",
    0xFE: "application-specific",
    0xFF: "vendor-specific",
}

TRANSFER_TYPES = {0: "control", 1: "isochronous", 2: "bulk", 3: "interrupt"}


@dataclass(frozen=True)
class Endpoint:
    address: str
    transfer: str
    direction: str
    max_packet: int


@dataclass(frozen=True)
class Interface:
    configuration: int
    number: int
    alternate_setting: int
    interface_class: str
    endpoints: tuple[Endpoint, ...]


@dataclass(frozen=True)
class UsbDevice:
    bus: int
    address: int
    vid: int
    pid: int
    device_class: str
    manufacturer: str | None
    product: str | None
    serial: str | None
    interfaces: tuple[Interface, ...] = field(default_factory=tuple)
    interface_error: str | None = None

    @property
    def vid_pid(self) -> str:
        return f"{self.vid:04x}:{self.pid:04x}"


def _safe_string(device: usb.core.Device, index: int | None) -> str | None:
    if not index:
        return None
    try:
        return usb.util.get_string(device, index)
    except (usb.core.USBError, NotImplementedError, ValueError):
        return None


def _endpoint(endpoint: usb.core.Endpoint) -> Endpoint:
    return Endpoint(
        address=f"0x{endpoint.bEndpointAddress:02x}",
        transfer=TRANSFER_TYPES.get(endpoint.bmAttributes & 0x03, "unknown"),
        direction="in" if endpoint.bEndpointAddress & 0x80 else "out",
        max_packet=int(endpoint.wMaxPacketSize),
    )


def _describe_interfaces(
    device: usb.core.Device,
) -> tuple[tuple[Interface, ...], str | None]:
    try:
        configurations = device.configurations()
    except (usb.core.USBError, NotImplementedError, ValueError) as error:
        return (), str(error)
    seen: set[tuple[int, int, int]] = set()
    interfaces: list[Interface] = []
    for configuration in configurations:
        for alternate in configuration:
            key = (
                configuration.bConfigurationValue,
                alternate.bInterfaceNumber,
                alternate.bAlternateSetting,
            )
            if key in seen:
                continue
            seen.add(key)
            class_code = int(alternate.bInterfaceClass)
            interfaces.append(
                Interface(
                    configuration=int(configuration.bConfigurationValue),
                    number=int(alternate.bInterfaceNumber),
                    alternate_setting=int(alternate.bAlternateSetting),
                    interface_class=CLASS_NAMES.get(class_code, f"0x{class_code:02x}"),
                    endpoints=tuple(_endpoint(e) for e in alternate),
                )
            )
    return tuple(interfaces), None


def collect_devices(details: bool = False) -> list[UsbDevice]:
    backend = libusb_package.get_libusb1_backend()
    windows_names = windows_friendly_names()
    devices: list[UsbDevice] = []
    for device in usb.core.find(find_all=True, backend=backend):
        try:
            bus = int(device.bus)
            address = int(device.address)
            vid = int(device.idVendor)
            pid = int(device.idProduct)
            class_code = int(device.bDeviceClass)
        except (usb.core.USBError, ValueError):
            continue
        interfaces: tuple[Interface, ...] = ()
        interface_error = None
        if details:
            interfaces, interface_error = _describe_interfaces(device)
        devices.append(
            UsbDevice(
                bus=bus,
                address=address,
                vid=vid,
                pid=pid,
                device_class=CLASS_NAMES.get(class_code, f"0x{class_code:02x}"),
                manufacturer=_safe_string(device, device.iManufacturer),
                product=_safe_string(device, device.iProduct) or windows_names.get((vid, pid)),
                serial=_safe_string(device, device.iSerialNumber),
                interfaces=interfaces,
                interface_error=interface_error,
            )
        )
    return sorted(devices, key=lambda d: (d.bus, d.address))


def _format_table(devices: list[UsbDevice], details: bool) -> str:
    headers = ("BUS", "ADDR", "VID:PID", "CLASS", "MANUFACTURER", "PRODUCT", "SERIAL")
    rows = [
        (
            f"{d.bus:03d}",
            f"{d.address:03d}",
            d.vid_pid,
            d.device_class,
            d.manufacturer or "-",
            d.product or "-",
            d.serial or "-",
        )
        for d in devices
    ]
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(widths[i], len(row[i])) for i in range(len(headers))]
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    lines.extend(
        "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in rows
    )
    if details:
        for device in devices:
            if device.interface_error:
                lines.append(f"  ! {device.vid_pid}: {device.interface_error}")
            for interface in device.interfaces:
                lines.append(
                    f"  - {device.vid_pid} iface {interface.number} alt "
                    f"{interface.alternate_setting} ({interface.interface_class})"
                )
                for endpoint in interface.endpoints:
                    lines.append(
                        f"      {endpoint.address} {endpoint.transfer} "
                        f"{endpoint.direction} max {endpoint.max_packet}"
                    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="usbprobe",
        description="Inspect USB devices connected to this machine.",
    )
    sub = parser.add_subparsers(dest="command")
    list_cmd = sub.add_parser("list", help="List connected USB devices")
    list_cmd.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    list_cmd.add_argument(
        "--details",
        action="store_true",
        help="Include interfaces, alternate settings and endpoints",
    )
    args = parser.parse_args(argv)
    details = getattr(args, "details", False)

    try:
        devices = collect_devices(details=details)
    except usb.core.NoBackendError:
        print(
            "libusb backend not found; install the 'libusb-package' dependency.",
            file=sys.stderr,
        )
        return 1

    if getattr(args, "json", False):
        json.dump(
            [{**asdict(d), "vid_pid": d.vid_pid} for d in devices],
            sys.stdout,
            indent=2,
        )
        print()
    else:
        print(_format_table(devices, details))
        print(f"\n{len(devices)} device(s)")
    return 0
