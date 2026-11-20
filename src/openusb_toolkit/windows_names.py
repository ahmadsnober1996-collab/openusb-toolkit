"""Windows PnP friendly names for USB devices, read through SetupAPI."""

from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes

_VID_PID = re.compile(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})")

_SPDRP_DEVICEDESC = 0x00
_SPDRP_HARDWAREID = 0x01
_SPDRP_FRIENDLYNAME = 0x0C
_DIGCF_PRESENT = 0x02
_DIGCF_DEVICEINTERFACE = 0x10
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class _SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", _GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


_GUID_DEVINTERFACE_USB_DEVICE = _GUID(
    0xA5DCBF10,
    0x6530,
    0x11D2,
    (ctypes.c_ubyte * 8)(0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED),
)


def _setupapi():
    api = ctypes.WinDLL("setupapi", use_last_error=True)
    api.SetupDiGetClassDevsW.argtypes = [
        ctypes.POINTER(_GUID),
        wintypes.LPCWSTR,
        wintypes.HWND,
        wintypes.DWORD,
    ]
    api.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    api.SetupDiEnumDeviceInfo.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(_SP_DEVINFO_DATA),
    ]
    api.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
    api.SetupDiGetDeviceRegistryPropertyW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_SP_DEVINFO_DATA),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    api.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL
    api.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
    api.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    return api


def _read_property(
    api, handle, info: _SP_DEVINFO_DATA, prop: int
) -> str | None:
    buffer = ctypes.create_unicode_buffer(1024)
    if not api.SetupDiGetDeviceRegistryPropertyW(
        handle,
        ctypes.byref(info),
        prop,
        None,
        ctypes.cast(buffer, ctypes.c_void_p),
        ctypes.sizeof(buffer),
        None,
    ):
        return None
    return buffer.value or None


def windows_friendly_names() -> dict[tuple[int, int], str]:
    """Map (vendor id, product id) to the PnP friendly name on this host."""
    if sys.platform != "win32":
        return {}
    api = _setupapi()
    handle = api.SetupDiGetClassDevsW(
        ctypes.byref(_GUID_DEVINTERFACE_USB_DEVICE),
        None,
        None,
        _DIGCF_PRESENT | _DIGCF_DEVICEINTERFACE,
    )
    if not handle or handle == _INVALID_HANDLE:
        return {}
    names: dict[tuple[int, int], str] = {}
    try:
        info = _SP_DEVINFO_DATA()
        info.cbSize = ctypes.sizeof(_SP_DEVINFO_DATA)
        index = 0
        while api.SetupDiEnumDeviceInfo(handle, index, ctypes.byref(info)):
            index += 1
            hardware_ids = _read_property(api, handle, info, _SPDRP_HARDWAREID) or ""
            match = _VID_PID.search(hardware_ids)
            if not match:
                continue
            key = (int(match.group(1), 16), int(match.group(2), 16))
            name = _read_property(api, handle, info, _SPDRP_FRIENDLYNAME)
            if name is None:
                name = _read_property(api, handle, info, _SPDRP_DEVICEDESC)
            if name and key not in names:
                names[key] = name
    finally:
        api.SetupDiDestroyDeviceInfoList(handle)
    return names
