"""
Small local JSON cache for calibration data, so the add-in doesn't
need to re-detect or re-ask on every use. Stored outside the add-in
folder (in the OS's standard per-user app-data location) so it
survives add-in updates/reinstalls, and applies globally across every
Fusion document -- calibration is a property of the physical display,
not of any particular file.

Deliberately NOT keyed per-monitor: an earlier version keyed
calibration by a computed monitor identifier (derived from whichever
window happened to be active at the time), but that identifier could
be resolved inconsistently by Windows depending on how Fusion manages
window handles across documents, making a saved calibration
intermittently fail to be found again. A single global value is far
more reliable for the common case (one monitor, or several similar
ones). Trade-off: someone who regularly moves Fusion between two
displays with meaningfully different pixel densities would need to
re-calibrate when switching -- an accepted edge case in exchange for
calibration reliably persisting for everyone else.
"""

import json
import os
import platform

_CALIBRATION_KEY = "manual_pixels_per_cm"
_LAST_AUTO_READING_KEY = "last_auto_reading"


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


def get_calibration():
    """Returns the stored manual-calibration override (pixels_per_cm),
    or None if no calibration has been saved yet (i.e. auto-DPI should
    be used). Applies globally, across every document."""
    data = _load_all()
    return data.get(_CALIBRATION_KEY)


def set_calibration(pixels_per_cm):
    data = _load_all()
    data[_CALIBRATION_KEY] = pixels_per_cm
    _save_all(data)


def clear_calibration():
    data = _load_all()
    data.pop(_CALIBRATION_KEY, None)
    _save_all(data)


def log_last_auto_reading(dpi_result_repr):
    """Stores the last auto-detected DPI reading purely for
    diagnostics."""
    data = _load_all()
    data[_LAST_AUTO_READING_KEY] = dpi_result_repr
    _save_all(data)
