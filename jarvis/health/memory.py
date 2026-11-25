"""How much memory is free on this laptop, in MB (v0.14.0): Laptop B idled at 82% of its 16 GB before Jarvis, and a
speech model that has to page runs slower than he talks. Numbers only; logged when hearing falls behind."""
from __future__ import annotations

import ctypes
import sys


def memory() -> tuple[int, int] | None:
    """(free MB, percent in use), or None when it can't be read."""
    try:
        if sys.platform == "win32":
            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = Status()
            st.dwLength = ctypes.sizeof(Status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):  # type: ignore[attr-defined]
                return None
            return int(st.ullAvailPhys // (1024 * 1024)), int(st.dwMemoryLoad)
        fields = {}
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                name, _, rest = line.partition(":")
                fields[name] = int(rest.split()[0])
        total, free = fields["MemTotal"], fields.get("MemAvailable", fields.get("MemFree", 0))
        return free // 1024, round(100 * (total - free) / max(1, total))
    except Exception:  # noqa: BLE001 - a health number must never raise
        return None
