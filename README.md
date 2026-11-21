# La Calma Radio GUI

A fullscreen Qt Quick/PySide6 touchscreen application using the PHP radio-lib
for radio playback. No service or autostart is installed.

- `python3 main.py --radio`: saved FM, DAB+, Internet and podcast tabs with
  tap-to-play, switching, volume and metadata. Podcasts add resume, pause and seek. See [radio playback](RADIO-PLAYBACK.md)
  and [podcasts](PODCAST-GUI.md).
- `python3 main.py --internet`: the earlier internet-only playback screen.
- `python3 main.py --keyboard-test`: multilingual EN/DE/ES/Hebrew/Greek input
  experiment. See [keyboard notes](KEYBOARD.md).
- No playback flag: the original display/touch demonstration, with sample
  stations and a UI-only slider; this mode does not start radio/audio processes.

The playback backend uses this checkout's Composer dependencies and the existing
~/.radio configuration/catalogues. Run `composer install` from the committed lock
and `composer check-platform-reqs`. Never run the application as root.

## Display-prototype reference

## First check the target

```bash
python3 main.py --diagnose
```

This uses the standard library; when PySide6 exists it also reads Qt plugin paths.
It does not start a Qt application or acquire display/input devices. Send this
report before choosing installation steps. Required GUI modules are PySide6 QtCore,
QtGui, QtQml, QtQuick and QtQuickControls2 plus QML QtQuick/Controls/Layouts/Window.
A suitable Qt 6 build must include the platform and graphics integration needed
on the target. A PySide6 import or listed EGLFS plugin alone does not prove that
its native dependencies, DRM device permissions, display or touch mapping work.
Do not mix Python bindings and plugins from different Qt installations.

## Desktop test after dependencies are available

From the Pi's own desktop terminal (not an unrelated SSH session), run:

```bash
python3 main.py --windowed --timeout 120
```

Qt chooses the available desktop platform. This tests the UI, not EGLFS. Use Exit,
Escape or Ctrl+Q to close. SIGINT/SIGTERM are also handled. Timeout is an optional
qualification aid, not a permanent application behavior.

## EGLFS qualification

EGLFS needs an appropriate EGL/OpenGL ES and DRM/KMS stack and permission to access
the display/input devices. A desktop compositor may already own the display. Do
not run a second graphics owner or stop your display manager blindly. First use
the diagnostic report to determine the active session and available plugins.

Once the target has an agreed native-console graphics session with no competing
compositor, launch as the normal radio user from that console:

```bash
python3 main.py --platform eglfs --timeout 120
```

Do not launch as root to bypass unexplained permissions. Do not force Qt Quick's
software renderer for EGLFS. Failures need the Qt startup output and diagnostic
report before changing drivers or installing a different stack. A Qt application
can abort during native platform initialization; Python cannot catch every such
failure. A separate SSH connection is useful for recovery. No compositor shutdown,
VT switch, device permission or rotation change is performed by this prototype.

## Acceptance observations

- The landscape scene fits the screen without clipping; unused space is letterboxed.
- Four source buttons change pages; sample selection changes the highlighted tile.
- Touches land on the intended target, including near screen edges.
- The slider tracks a finger and the touch counter changes.
- Podcasts shows logical Hebrew and mixed Hebrew/English in the correct order.
  No FriBidi visual-order conversion is applied; Qt handles text layout.
- Exit, keyboard exit and timed exit release the display normally.
- Confirm whether the platform label says eglfs, wayland or xcb; only eglfs proves
  the intended direct-display launch.

The design canvas is 1280x720, scaled uniformly for the actual display. Font default
is DejaVu Sans with Qt fallback. Wrong rotation/touch mapping must be diagnosed on
the device; no fixed output connector, rotation or touchscreen path is assumed.

## Scope

Python syntax and diagnostic-script execution can be checked without Qt. QML,
rendering, text shaping and touch require native Qt acceptance; no hardware pass
is claimed until the Pi results are supplied. This prototype is not a release or
an existing radio-ui checkout. The playback screens connect through the supervised PHP backend described above.
New source integrations still require the documented native tests and Pi hardware
checks; display-only checks do not qualify radio playback.

## Secondary discovery

Internet and Podcasts include a smaller Find action below the source tabs.
Search uses the multilingual touch keyboard. Save a station or subscribe to a
podcast explicitly, then return to presets to play. Search and subscription
fetches run in an owned PHP worker alongside playback. See DISCOVERY.md.
FM/DAB+ scan screens and remembered DAB+ reception regions are the next stage.
