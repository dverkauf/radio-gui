# Logo power menu

Tap the La Calma logo on the main screen:

- **Standby** stops playback, waits for receiver release, and switches off the
  Touch Display 2 backlight. The Pi keeps running. Touch the panel (or click the
  black VNC window) to wake it. Audio stays stopped until a preset is tapped.
- **Shut down Pi** opens a separate confirmation. Confirm shutdown performs a
  normal systemd power-off, after playback cleanup. Touch cannot power the Pi
  on after this; use its physical power button. The current project does not
  install GUI autostart on boot, so use start_gui/start_gui_vnc again after boot.
- **Cancel** leaves the radio running. Cancel in the confirmation returns to the
  power choices.

The standby overlay consumes the complete wake touch/mouse gesture and keeps a
short release guard so that it cannot also activate a preset. Multi-touch and
keyboard wake events are handled. Scanning/saving must finish before either power
action. Cleanup failure is shown rather than claiming the receiver was released.

## One-time installation

As the normal radio user, from this checkout:

```sh
./setup_power_controls
```

This asks for sudo once. It installs a **root-owned snapshot** of power_helper.py
at `/usr/local/libexec/la-calma-power-helper.py` and a validated sudoers rule at
`/etc/sudoers.d/la-calma-radio-power`. The rule permits only these three exact
commands for that user:

```text
/usr/bin/python3 -I /usr/local/libexec/la-calma-power-helper.py standby
/usr/bin/python3 -I /usr/local/libexec/la-calma-power-helper.py wake
/usr/bin/python3 -I /usr/local/libexec/la-calma-power-helper.py poweroff
```

The GUI invokes them using sudo -n. It never prompts for passwords on the panel,
never runs the checkout or GUI as root, and has no general passwordless sudo.
Re-run setup after updating the helper to update its installed snapshot. The
setup does not change radio-mono, display-manager, VNC, or boot configuration.
Do not run the installer from an untrusted or modified checkout.

The helper selects one sysfs backlight; if several exist, exactly one must expose
an unambiguous DSI display_name. Otherwise it refuses rather than guessing. It
sets brightness to zero without disabling the touch controller or suspending the
Pi. Prior nonzero brightness is kept in root-private runtime state under
`/run/la-calma-radio-power` and restored on wake. A later desktop brightness change
is retained if the display is already lit. A missing/failed helper gives an error.

## Recovery and removal

If the backlight remains off, from SSH:

```sh
cd ~/projects/radio-gui
./wake_display
```

Normal stop_gui restores a standby display. A subsequent native GUI start also
attempts restoration after a crash. Neither can guarantee restoration after a
kernel crash or power loss. No reboot is necessary for standby recovery.

To uninstall, first wake the display and stop the GUI, then remove only the two
installed files:

```sh
./wake_display
./stop_gui
sudo rm /etc/sudoers.d/la-calma-radio-power \
  /usr/local/libexec/la-calma-power-helper.py
```

## Validation

```sh
/usr/bin/python3 -X faulthandler -m unittest -v \
  test_power_helper test_power_bridge test_power_qml
/usr/bin/python3 -X faulthandler -m unittest discover -v
```

All automated tests use fake backlight files or fake helper processes. Offscreen
mode disables real power commands, including startup recovery. Tests never shut
the host down. Native Qt tests isolate QML in child processes and check both the
shutdown confirmation and that the first wake click cannot reach a station.

On the physical Pi, test Cancel, Standby, touch wake, previous brightness recovery,
and that audio stays stopped. Repeat in VNC and EGLFS modes. Verify scan/save
blocking, clean stop_gui from standby, and wake_display recovery. Test actual
shutdown separately when ready for SSH and VNC to disconnect; then power it back
on with the Pi button. Full system shutdown affects all Pi sessions, not only the
radio GUI. The helper uses normal systemd poweroff, without --force or --no-sync.
