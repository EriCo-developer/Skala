"""
Core logic: figure out how many screen pixels correspond to 1 real cm,
then set Fusion's camera.viewExtents so the active viewport renders
model geometry at true physical size.

Fusion API notes this relies on (confirm against your installed
version -- API has been stable on these points for a long time, but
worth a sanity check):
  - adsk.core.Application.get().activeViewport.width / .height give the
    pixel size of the 3D viewport render area (not the whole Fusion
    window, and not the whole screen).
  - Camera.viewExtents (float, cm) is the height, in Fusion's internal
    units (cm), of the vertical extent of the current view volume. It's
    what changes when you scroll-zoom.
  - Fusion's internal length unit is always cm regardless of the
    document's displayed units, so no unit-system lookup is needed.

The Windows DPI double-scaling bug (viewport pixels being logical
while effective-DPI already bakes in OS scaling) is fixed in
dpi_utils.py using MDT_RAW_DPI. The manual calibration path remains as
a safety net for displays with genuinely inaccurate EDID data.
"""

from . import dpi_utils
from . import settings_store


class ScaleResult:
    def __init__(self, view_extents_cm, pixels_per_cm, method,
                 viewport_height_px, diagnostics=None):
        self.view_extents_cm = view_extents_cm
        self.pixels_per_cm = pixels_per_cm
        self.method = method
        self.viewport_height_px = viewport_height_px
        self.diagnostics = diagnostics or {}


def compute_scale(viewport):
    """
    viewport: adsk.core.Viewport (pass app.activeViewport)
    Returns a ScaleResult. Does not modify the camera -- see apply_scale().
    Prefers a stored manual calibration if one exists (global, applies
    across every document); otherwise falls back to raw OS-reported DPI.
    """
    manual_ppcm = settings_store.get_calibration()

    if manual_ppcm is not None:
        return _build_result(viewport, manual_ppcm, "manual calibration override",
                              {})

    return compute_raw_auto_scale(viewport)


def compute_raw_auto_scale(viewport):
    """
    Same as compute_scale(), but always uses a fresh OS DPI reading and
    ignores any stored manual calibration. Used by the calibration
    workflow so each new calibration starts from the current raw
    auto-detected baseline rather than compounding a previous
    correction.
    """
    dpi_result = dpi_utils.get_screen_dpi()
    # Use vertical DPI since viewExtents is a vertical measurement.
    pixels_per_cm = dpi_result.pixels_per_cm_y
    diagnostics = {
        "dpi_x": dpi_result.dpi_x,
        "dpi_y": dpi_result.dpi_y,
        "raw_info": dpi_result.raw_info,
    }
    settings_store.log_last_auto_reading(repr(dpi_result))
    return _build_result(viewport, pixels_per_cm, dpi_result.method, diagnostics)


def _build_result(viewport, pixels_per_cm, method, diagnostics):
    viewport_height_px = viewport.height
    view_extents_cm = viewport_height_px / pixels_per_cm
    return ScaleResult(
        view_extents_cm=view_extents_cm,
        pixels_per_cm=pixels_per_cm,
        method=method,
        viewport_height_px=viewport_height_px,
        diagnostics=diagnostics,
    )


def apply_scale(viewport, scale_result, smooth_transition=False):
    """
    Applies a computed ScaleResult to the given viewport's camera.
    smooth_transition=False for an instant snap (matches the "flash the
    logo for 2s as confirmation" behavior rather than an animated zoom).
    """
    camera = viewport.camera
    camera.viewExtents = scale_result.view_extents_cm
    camera.isSmoothTransition = smooth_transition
    viewport.camera = camera
    viewport.refresh()
