# Skala 🍌

**Skala** scales the active Fusion 360 viewport so that 1 cm of model geometry is displayed as 1 cm on your physical screen — useful for sanity-checking part sizes, ergonomics, or fit at a glance, without measuring on screen or exporting to another tool.

One click. No manual DPI or zoom guessing.

---

## Install

1. Download this repository (**Code → Download ZIP**) and unzip it.

2. Copy the `Skala` folder into your Fusion Add-Ins directory:

   | OS | Path |
   |---|---|
   | Windows | `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\` |
   | Mac | `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/` |

3. In Fusion: **Utilities tab → Add-Ins → Scripts and Add-Ins → Add-Ins tab → green "+" → select the `Skala` folder.**

4. Select it in the list and click **Run** (check "Run on Startup" if you want it always available).

5. Click the banana icon in the **navigation toolbar** — bottom-center of the viewport, next to Orbit / Pan / Zoom / Fit.

## If the scale looks off

**Calibrate Skala** lives in **Utilities tab → Add-Ins panel** (separate from the main scale button, so it stays out of the way until you need it).

Clicking it draws a real 10 cm reference line in the viewport and asks you to measure it with a physical ruler. Enter what you measured, and Skala stores a correction for that display — no need to know your DPI or Windows scaling percentage yourself. Re-run it any time if you change monitors or the scale drifts.


## Optional: set a keyboard shortcut

Fusion doesn't let add-ins register a shortcut automatically, but you can bind one yourself in a few seconds:

**Tools tab → Configure → Keyboard Shortcuts → search "Skala" → assign a key.**

## How it works

Skala reads your display's DPI directly from the OS (no external dependencies — just Python's built-in `ctypes`, no PySide/Qt) and uses it to set Fusion's camera `viewExtents` so that on-screen pixels map 1:1 to real-world centimeters.

## License

[MIT](LICENSE) — free to use, modify, and share.
