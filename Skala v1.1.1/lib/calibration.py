"""
One-time (or as-needed) manual calibration, for displays where the
OS-reported DPI doesn't match reality closely enough (bad/missing EDID
data, unusual scaling setups, etc).

Design choice: rather than asking the user to type in DPI/scaling
values they likely don't know off-hand, this draws an actual reference
line of a known length directly in the Fusion viewport -- using the
same native rendering pipeline that Skala's normal scaling controls,
not a separate HTML/CSS overlay -- and asks the user to measure it
with a real ruler. That sidesteps needing to know *why* a display is
misreporting; it just corrects for the end result.

The reference line is drawn with CustomGraphicsGroup, which is
session-only and never gets saved into the user's document.
"""

import adsk.core
import adsk.fusion

from . import scale_engine, settings_store

REFERENCE_LENGTH_CM = 10.0


def set_orthographic_front_view(viewport):
    """Puts the camera in a clean, undistorted state so the reference
    line renders at its true model-space length (no perspective
    foreshortening, no odd rotation)."""
    camera = viewport.camera
    camera.cameraType = adsk.core.CameraTypes.OrthographicCameraType
    camera.viewOrientation = adsk.core.ViewOrientations.FrontViewOrientation
    camera.target = adsk.core.Point3D.create(0, 0, 0)
    camera.eye = adsk.core.Point3D.create(0, 0, 100)
    camera.upVector = adsk.core.Vector3D.create(0, 1, 0)
    camera.isSmoothTransition = False
    viewport.camera = camera


def draw_reference_line(design):
    """
    Draws a REFERENCE_LENGTH_CM-long horizontal line centered on the
    origin, in a temporary CustomGraphicsGroup. Returns the group so
    the caller can delete it later (on command execute or cancel).
    """
    root = design.rootComponent
    group = root.customGraphicsGroups.add()

    half = REFERENCE_LENGTH_CM / 2.0
    coords = adsk.fusion.CustomGraphicsCoordinates.create(
        [-half, 0, 0, half, 0, 0]
    )
    lines = group.addLines(coords, [0, 1], False)
    lines.weight = 3
    lines.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
        adsk.core.Color.create(220, 40, 40, 255)
    )
    return group


def compute_corrected_pixels_per_cm(raw_pixels_per_cm, measured_length_cm):
    """
    raw_pixels_per_cm: the pixels-per-cm value that was used to render
        the reference line (i.e. what auto-DPI currently believes).
    measured_length_cm: what the user actually measured with a ruler.

    If the line rendered too big, the display's real pixel density is
    lower than assumed, and vice versa -- hence the inverse ratio.
    """
    if measured_length_cm <= 0:
        raise ValueError("Measured length must be greater than zero.")
    return raw_pixels_per_cm * (REFERENCE_LENGTH_CM / measured_length_cm)


def save_calibration(monitor_key, corrected_pixels_per_cm):
    settings_store.set_calibration(monitor_key, corrected_pixels_per_cm)
