"""
DPI detection for Windows and macOS using ctypes only.

Deliberately avoids PySide/PyQt: Fusion 360 already has its own embedded
Qt build loaded in-process, and importing a second, separately-compiled
Qt binding (PySide2/6) into the same process risks DLL/symbol collisions
and breaks across Fusion's monthly updates. ctypes calls straight to the
OS have no such dependency and ship with every Python install.

NOTE: this is the one part of the add-in that needs on-machine
verification. The open question is whether Fusion's Viewport.width /
Viewport.height are reported in *physical* pixels or *logical* pixels
(i.e. already divided by the OS display-scaling factor). This module
returns 'effective DPI' (which already bakes in OS scaling on Windows),
plus raw diagnostic fields, so we can check the numbers against a real
on-screen ruler and adjust scale_engine.py's formula if needed.
"""

import ctypes
import platform


class DpiResult:
    def __init__(self, dpi_x, dpi_y, method, raw_info=None):
        self.dpi_x = dpi_x
        self.dpi_y = dpi_y
        self.method = method
        self.raw_info = raw_info or {}

    @property
    def pixels_per_cm_x(self):
        return self.dpi_x / 2.54

    @property
    def pixels_per_cm_y(self):
        return self.dpi_y / 2.54

    def __repr__(self):
        return (f"DpiResult(dpi_x={self.dpi_x:.2f}, dpi_y={self.dpi_y:.2f}, "
                f"method='{self.method}')")


def _get_dpi_windows():
    """
    Per-monitor effective DPI on Windows, via shcore.GetDpiForMonitor.
    Falls back to system DPI (GetDeviceCaps) on older Windows without
    per-monitor DPI awareness (pre-8.1), or if shcore isn't available.
    """
    user32 = ctypes.windll.user32
    try:
        shcore = ctypes.windll.shcore
        # MDT_EFFECTIVE_DPI = 0 -- includes the OS display-scaling factor
        MDT_EFFECTIVE_DPI = 0
        MONITOR_DEFAULTTONEAREST = 2

        hwnd = user32.GetActiveWindow()
        if not hwnd:
            hwnd = user32.GetForegroundWindow()

        hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)

        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        result = shcore.GetDpiForMonitor(
            hmonitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
        )
        if result == 0:  # S_OK
            return DpiResult(
                float(dpi_x.value), float(dpi_y.value),
                method="shcore.GetDpiForMonitor (effective, per-monitor)",
                raw_info={"hwnd": hwnd, "hmonitor": hmonitor},
            )
    except (AttributeError, OSError):
        pass  # shcore not available -- fall through to legacy path

    # Legacy fallback: system-wide DPI only, no per-monitor awareness.
    LOGPIXELSX = 88
    LOGPIXELSY = 90
    hdc = user32.GetDC(0)
    gdi32 = ctypes.windll.gdi32
    dpi_x = gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
    dpi_y = gdi32.GetDeviceCaps(hdc, LOGPIXELSY)
    user32.ReleaseDC(0, hdc)
    return DpiResult(
        float(dpi_x), float(dpi_y),
        method="gdi32.GetDeviceCaps (system-wide, legacy fallback)",
    )


def _get_dpi_mac():
    """
    Physical PPI on macOS via CoreGraphics: CGDisplayScreenSize (mm) vs
    CGDisplayPixelsWide/High (pixel dimensions of the display).

    Caveat to verify on-machine: on Retina displays, CGDisplayPixelsWide
    /High have historically reported logical ("points") resolution
    rather than full backing-store pixel resolution in some macOS
    versions/configs. If numbers look off by ~2x on a Retina display,
    that's the likely cause and we'd switch to reading the backing
    scale factor as well.
    """
    cg = ctypes.CDLL(
        "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
    )

    class CGSize(ctypes.Structure):
        _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]

    cg.CGMainDisplayID.restype = ctypes.c_uint32
    cg.CGDisplayScreenSize.restype = CGSize
    cg.CGDisplayScreenSize.argtypes = [ctypes.c_uint32]
    cg.CGDisplayPixelsWide.restype = ctypes.c_size_t
    cg.CGDisplayPixelsWide.argtypes = [ctypes.c_uint32]
    cg.CGDisplayPixelsHigh.restype = ctypes.c_size_t
    cg.CGDisplayPixelsHigh.argtypes = [ctypes.c_uint32]

    display_id = cg.CGMainDisplayID()
    size_mm = cg.CGDisplayScreenSize(display_id)
    px_wide = cg.CGDisplayPixelsWide(display_id)
    px_high = cg.CGDisplayPixelsHigh(display_id)

    if size_mm.width <= 0 or size_mm.height <= 0:
        raise RuntimeError("CGDisplayScreenSize returned invalid size; "
                            "monitor may not report EDID correctly.")

    dpi_x = px_wide / (size_mm.width / 25.4)
    dpi_y = px_high / (size_mm.height / 25.4)

    return DpiResult(
        dpi_x, dpi_y,
        method="CoreGraphics CGDisplayScreenSize / CGDisplayPixelsWide-High",
        raw_info={
            "display_id": display_id,
            "screen_mm": (size_mm.width, size_mm.height),
            "pixel_dims": (px_wide, px_high),
        },
    )


def get_monitor_key():
    """
    Best-effort stable-ish identifier for the current monitor, used to
    key cached calibration data. Not perfectly stable across reboots or
    cable/port changes, but good enough to avoid re-detecting on every
    single use within a session and across most normal usage.
    """
    system = platform.system()
    try:
        if system == "Windows":
            user32 = ctypes.windll.user32

            class MONITORINFOEX(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", ctypes.c_long * 4),
                    ("rcWork", ctypes.c_long * 4),
                    ("dwFlags", ctypes.c_ulong),
                    ("szDevice", ctypes.c_wchar * 32),
                ]

            hwnd = user32.GetActiveWindow() or user32.GetForegroundWindow()
            MONITOR_DEFAULTTONEAREST = 2
            hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            info = MONITORINFOEX()
            info.cbSize = ctypes.sizeof(MONITORINFOEX)
            user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
            return f"win:{info.szDevice}"
        elif system == "Darwin":
            cg = ctypes.CDLL(
                "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
            )
            cg.CGMainDisplayID.restype = ctypes.c_uint32
            return f"mac:{cg.CGMainDisplayID()}"
    except (AttributeError, OSError):
        pass
    return "unknown-monitor"


def get_screen_dpi():
    """
    Returns a DpiResult for the current display. Raises RuntimeError on
    unsupported platforms so callers can fall back to manual calibration.
    """
    system = platform.system()
    if system == "Windows":
        return _get_dpi_windows()
    elif system == "Darwin":
        return _get_dpi_mac()
    else:
        raise RuntimeError(f"Unsupported platform for auto-DPI: {system}")
