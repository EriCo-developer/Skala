import os
import traceback

import adsk.core
import adsk.fusion

from .lib import scale_engine

app = None
ui = None

CMD_ID = "SkalaCmd"
CMD_NAME = "Skala"
CMD_DESCRIPTION = "Scales the viewport so that 1 cm of model geometry is displayed as 1 cm on screen."
NAV_TOOLBAR_ID = "NavToolbar"  # bottom-center viewport toolbar (Orbit, Pan, Zoom, Fit, etc.)

_handlers = []  # keep references alive -- Fusion drops handlers otherwise


def run(context):
    global app, ui
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        cmd_defs = ui.commandDefinitions
        existing = cmd_defs.itemById(CMD_ID)
        if existing:
            existing.deleteMe()

        resource_folder = os.path.join(os.path.dirname(__file__), "resources", CMD_ID)
        cmd_def = cmd_defs.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESCRIPTION, resource_folder
        )

        on_created = CommandCreatedHandler()
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        nav_toolbar = ui.toolbars.itemById(NAV_TOOLBAR_ID)
        if nav_toolbar and not nav_toolbar.controls.itemById(CMD_ID):
            nav_toolbar.controls.addCommand(cmd_def)

    except Exception:
        if ui:
            ui.messageBox(f"Skala failed to load:\n{traceback.format_exc()}")


def stop(context):
    try:
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        nav_toolbar = ui.toolbars.itemById(NAV_TOOLBAR_ID)
        if nav_toolbar:
            control = nav_toolbar.controls.itemById(CMD_ID)
            if control:
                control.deleteMe()

    except Exception:
        if ui:
            ui.messageBox(f"Skala failed to stop cleanly:\n{traceback.format_exc()}")


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
