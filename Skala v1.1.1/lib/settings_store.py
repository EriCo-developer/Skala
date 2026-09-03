"""
Small local JSON cache for per-monitor calibration data, so the add-in
doesn't need to re-detect or re-ask on every use. Stored outside the
add-in folder (in the OS's standard per-user app-data location) so it
survives add-in updates/reinstalls.
"""

import json
import os
import platform


def _settings_dir():
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.path.expanduser("~/.config")
    path = os.path.join(base, "SkalaAddin")
    os.makedirs(path, exist_ok=True)
    return path


def _settings_path():
    return os.path.join(_settings_dir(), "settings.json")


def _load_all():
    path = _settings_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_all(data):
    with open(_settings_path(), "w") as f:
        json.dump(data, f, indent=2)


def get_calibration(monitor_key):
    """Returns a stored manual-calibration override (pixels_per_cm) for
    the given monitor key, or None if the monitor hasn't been
    calibrated manually (i.e. it should use auto-DPI)."""
    data = _load_all()
    entry = data.get(monitor_key)
    if entry and "manual_pixels_per_cm" in entry:
        return entry["manual_pixels_per_cm"]
    return None


def set_calibration(monitor_key, pixels_per_cm):
    data = _load_all()
    data.setdefault(monitor_key, {})["manual_pixels_per_cm"] = pixels_per_cm
    _save_all(data)


def clear_calibration(monitor_key):
    data = _load_all()
    if monitor_key in data:
        data[monitor_key].pop("manual_pixels_per_cm", None)
        _save_all(data)


def log_last_auto_reading(monitor_key, dpi_result_repr):
    """Stores the last auto-detected DPI reading purely for diagnostics
    (shown if the user opens the debug/calibrate panel)."""
    data = _load_all()
    data.setdefault(monitor_key, {})["last_auto_reading"] = dpi_result_repr
    _save_all(data)
