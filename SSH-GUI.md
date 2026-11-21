# Start and stop the fullscreen GUI from SSH

Run as the same normal user that owns the radio data and PipeWire session:

    cd ~/projects/radio-gui
    ./start_gui
    ./stop_gui

start_gui defaults to EGLFS with 90-degree scene rotation and no timeout. It
returns to the SSH prompt once QML is loaded and the Qt event loop reports ready.
The GUI keeps running after SSH disconnects. Optional arguments:

    ./start_gui --rotation 90 --config-dir /home/dverkauf/.radio

The production Radio screen has no Exit button or Escape/Ctrl+Q quit shortcuts.
Use stop_gui from SSH. Prototype/keyboard test screens remain development tools.
This does not install an auto-start service or change boot configuration.

During development, starting ends the active desktop session; save desktop work
first. Stopping restores that desktop if it was previously active. The GUI and
all radio workers run as the normal user. sudo is used only to stop/restore the
display manager. Restoration is authorized before backgrounding and does not
require the sudo cache to remain valid for the entire session. No sudoers rule
or passwordless access is installed. Keep SSH available for maintenance.

A per-user runtime lock rejects duplicate managed launches. stop_gui validates
UID, /proc start time and exact launcher path/arguments, then uses a pidfd to
signal only that launcher. It never kills arbitrary Python or audio processes.
It waits for GUI shutdown and desktop restoration (up to 85 seconds). If a manual
preview/EGLFS instance is running, close it first: managed scripts do not adopt
or kill an instance they did not start. A readiness timeout requests cleanup.

Logs: ~/.local/state/radio-gui/gui.log, plus gui.previous.log from the preceding
start. Runtime records live under $XDG_RUNTIME_DIR/la-calma-gui. If startup fails,
inspect the log. If desktop restoration fails, the log records the recovery:

    sudo systemctl start display-manager

Validation:

    /usr/bin/python3 -m unittest -v test_gui_control test_eglfs_launcher
    /usr/bin/python3 -X faulthandler -m unittest discover -v
    ./start_gui
    ./start_gui                 # must report already running
    ./stop_gui
    ./stop_gui                  # must report no owned launcher

Also test a fresh SSH connection after closing the original one, playback stop,
scan cancellation on shutdown, no orphaned radio tools and desktop restoration.
The launcher allows 30 seconds for cooperative Qt/backend shutdown before an
emergency TERM/KILL fallback. Timed development checks retain an outer deadline.
No process can guarantee desktop restoration after power loss or a kernel crash.

## VNC development mode

    ./stop_gui
    ./start_gui_vnc
    ./stop_gui

start_gui_vnc uses the existing Wayland desktop, so WayVNC can show the fullscreen
application. It never stops/starts display-manager and does not use sudo. It runs
without timeout, returns to SSH when ready and survives SSH disconnection.
stop_gui recognizes either managed mode. The shared lock prevents two managed
instances: stop the current mode before switching. VNC mode requires a running
Wayland session; if EGLFS has stopped the desktop, use stop_gui to restore it.
It does not start a VNC server or change its authentication/network settings.

Wayland scene rotation defaults to 0 because the desktop already handles the
screen's landscape orientation. EGLFS start_gui retains rotation 90. Override
with --rotation if required. Both modes use the same GUI data and log paths.
