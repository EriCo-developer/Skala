import os
import traceback

import adsk.core
import adsk.fusion

from .lib import scale_engine, calibration

app = None
ui = None

CMD_ID = "SkalaCmd"
CMD_NAME = "Skala"
CMD_DESCRIPTION = "Scales the viewport so that 1 cm of model geometry is displayed as 1 cm on screen."

CALIBRATE_CMD_ID = "SkalaCalibrateCmd"
CALIBRATE_CMD_NAME = "Calibrate Skala"
CALIBRATE_CMD_DESCRIPTION = (
    "One-time calibration for displays where automatic scaling is off. "
    "Draws a reference line for you to measure with a ruler."
)
MEASURED_INPUT_ID = "measuredLength"

ADDINS_PANEL_ID = "SolidScriptsAddinsPanel"  # the standard "ADD-INS" panel under Tools/Utilities
NAV_TOOLBAR_ID = "NavToolbar"  # bottom-center viewport toolbar (Orbit, Pan, Zoom, Fit, etc.)

_handlers = []  # keep references alive -- Fusion drops handlers otherwise
_calibration_state = {}  # per-command-invocation scratch data (graphics group, raw ppcm)


def run(context):
    global app, ui
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        _register_command(
            CMD_ID, CMD_NAME, CMD_DESCRIPTION, "SkalaCmd",
            CommandCreatedHandler, target="nav_toolbar",
        )
        _register_command(
            CALIBRATE_CMD_ID, CALIBRATE_CMD_NAME, CALIBRATE_CMD_DESCRIPTION,
            "SkalaCalibrateCmd", CalibrateCommandCreatedHandler, target="addins_panel",
        )

    except Exception:
        if ui:
            ui.messageBox(f"Skala failed to load:\n{traceback.format_exc()}")


def _register_command(cmd_id, name, description, resource_subfolder, created_handler_cls, target):
    cmd_defs = ui.commandDefinitions
    existing = cmd_defs.itemById(cmd_id)
    if existing:
        existing.deleteMe()

    resource_folder = os.path.join(os.path.dirname(__file__), "resources", resource_subfolder)
    cmd_def = cmd_defs.addButtonDefinition(cmd_id, name, description, resource_folder)

    on_created = created_handler_cls()
    cmd_def.commandCreated.add(on_created)
    _handlers.append(on_created)

    if target == "nav_toolbar":
        container = ui.toolbars.itemById(NAV_TOOLBAR_ID)
    else:  # "addins_panel"
        workspace = ui.workspaces.itemById("FusionSolidEnvironment")
        container = workspace.toolbarPanels.itemById(ADDINS_PANEL_ID) if workspace else None

    if container and not container.controls.itemById(cmd_id):
        container.controls.addCommand(cmd_def)


def stop(context):
    try:
        nav_toolbar = ui.toolbars.itemById(NAV_TOOLBAR_ID)
        workspace = ui.workspaces.itemById("FusionSolidEnvironment")
        addins_panel = workspace.toolbarPanels.itemById(ADDINS_PANEL_ID) if workspace else None

        for cmd_id, container in ((CMD_ID, nav_toolbar), (CALIBRATE_CMD_ID, addins_panel)):
            cmd_def = ui.commandDefinitions.itemById(cmd_id)
            if cmd_def:
                cmd_def.deleteMe()
            if container:
                control = container.controls.itemById(cmd_id)
                if control:
                    control.deleteMe()

    except Exception:
        if ui:
            ui.messageBox(f"Skala failed to stop cleanly:\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# Main "Skala" scale command
# ---------------------------------------------------------------------------

class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            on_execute = CommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)
        except Exception:
            if ui:
                ui.messageBox(f"Command creation failed:\n{traceback.format_exc()}")


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            viewport = app.activeViewport
            result = scale_engine.compute_scale(viewport)
            scale_engine.apply_scale(viewport, result, smooth_transition=False)
        except Exception:
            if ui:
                ui.messageBox(f"Skala failed:\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
# "Calibrate Skala" command -- separate, optional, never shown unless the
# user explicitly clicks it. Draws a real 10cm reference line and asks the
# user to measure it, then stores a per-monitor correction factor.
# ---------------------------------------------------------------------------

class CalibrateCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                ui.messageBox("Open or create a design document first, then run Calibrate Skala again.")
                return

            cmd = args.command
            viewport = app.activeViewport

            calibration.set_orthographic_front_view(viewport)
            raw_result = scale_engine.compute_raw_auto_scale(viewport)
            scale_engine.apply_scale(viewport, raw_result, smooth_transition=False)
            graphics_group = calibration.draw_reference_line(design)

            _calibration_state["graphics_group"] = graphics_group
            _calibration_state["raw_result"] = raw_result

            inputs = cmd.commandInputs
            inputs.addTextBoxCommandInput(
                "instructions", "",
                "A red 10 cm reference line has been drawn in the viewport.\n"
                "Hold a ruler up to your screen and measure its actual length, "
                "then enter that measurement below.",
                4, True,
            )
            inputs.addValueInput(
                MEASURED_INPUT_ID, "Measured length", "cm",
                adsk.core.ValueInput.createByReal(REFERENCE_LENGTH_CM_DEFAULT),
            )

            on_execute = CalibrateExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_destroy = CalibrateDestroyHandler()
            cmd.destroy.add(on_destroy)
            _handlers.append(on_destroy)

        except Exception:
            if ui:
                ui.messageBox(f"Calibrate Skala failed to open:\n{traceback.format_exc()}")


REFERENCE_LENGTH_CM_DEFAULT = calibration.REFERENCE_LENGTH_CM


class CalibrateExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            inputs = args.command.commandInputs
            measured_input = inputs.itemById(MEASURED_INPUT_ID)
            measured_cm = measured_input.value

            raw_result = _calibration_state.get("raw_result")
            if not raw_result:
                return

            corrected_ppcm = calibration.compute_corrected_pixels_per_cm(
                raw_result.pixels_per_cm, measured_cm
            )
            calibration.save_calibration(corrected_ppcm)

            viewport = app.activeViewport
            new_result = scale_engine.compute_scale(viewport)
            scale_engine.apply_scale(viewport, new_result, smooth_transition=False)

            ui.messageBox("Calibration saved. Skala will use this correction across all documents from now on.")

        except Exception:
            if ui:
                ui.messageBox(f"Calibration failed:\n{traceback.format_exc()}")


class CalibrateDestroyHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            group = _calibration_state.pop("graphics_group", None)
            if group and group.isValid:
                group.deleteMe()
            _calibration_state.pop("raw_result", None)
        except Exception:
            pass
