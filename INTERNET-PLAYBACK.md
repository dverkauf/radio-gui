# First real playback milestone

Run `python3 main.py --internet` to open the saved internet-station screen.
The original display demo and `--keyboard-test` remain available. This screen
uses native Qt text direction and the existing La Calma asset. No FriBidi
transformation is applied. Search, station editing, FM, DAB and podcasts are
not part of this first screen.

## Install on the Pi

From the radio-gui checkout, run `composer install`, then commit the generated
composer.lock after validation. GitHub access to the radio-lib repository is
required; use your existing Composer credentials, never commit auth.json.
This milestone requests library commit 306913e. Composer records the resolved
full revision and transitive dependencies in composer.lock. Future installations
use that lock. PHP 8.4+, JSON, DOM, pcntl and the library's platform requirements
must pass `composer check-platform-reqs`. Qt dependencies are unchanged.

Audio requires ffmpeg, pw-play, pw-dump and pw-cli in the same user's session.
The existing ~/.radio/config.json provides playback.target, volume and tool
paths. The target sink must already exist. Configuration is read, not rewritten.
The GUI owns a separate Composer installation; radio-cli and a sibling source
checkout are not required. The shared internet-stations.json catalogue is read
through Radio\Internet\StationCatalogue. No station URL can be entered through
this GUI milestone: only saved UUIDs from the startup snapshot are accepted.
Close/reopen to refresh saved stations or recover from a fatal backend failure.

`--config-dir /absolute/path` overrides ~/.radio for direct/Wayland launches.
Do not run GUI or backend with sudo. The EGLFS helper uses sudo only to stop
and restore the desktop, preserving its previous behavior.

## Native checks (no audio or network requested)

```bash
php -l backend/internet.php
/usr/bin/python3 -m unittest -v \
  test_keyboard_layouts.py test_keyboard_editor.py \
  test_internet_backend.py test_internet_bridge.py
QT_QUICK_BACKEND=software /usr/bin/python3 main.py \
  --platform offscreen --internet --timeout 3
```

The six PHP tests require installed Composer dependencies; skipped tests are
not a pass. The four Qt bridge tests use a fake child process and exercise
fragmented Unicode responses, acknowledged volume, invalid protocol, peer
failure and EOF cleanup. They do not qualify actual audio or PipeWire behavior.
Existing 11 keyboard tests should remain green. QML scene loading and real
playback still require the target's native Qt/PHP environment.

## Live check

```bash
/usr/bin/python3 preview_wayland.py --internet
```

Tap a saved station to start it immediately; no separate Play action is needed.
Tap another station to switch after the current session stops. Repeated taps on
the playing station do not restart it; rapid taps keep only the latest choice.
Stop cancels any pending switch. Wait for sound and metadata. Adjust volume,
tap Stop during playback and also during startup; play again. Exit while
playing and check that ffmpeg, pw-play and pw-cli were reaped. Metadata depends
on the station supplying it; an empty metadata line alone is not an audio error.
Each new session begins at the configured initial volume. The slider reports
confirmed stream gain, not hardware mixer volume. Rapid changes may coalesce.

After Wayland acceptance, from SSH with unsaved desktop work closed:

```bash
/usr/bin/python3 test_eglfs.py --rotation 90 --seconds 120 --internet
```

The helper restores the desktop on normal exit/timeout. The default Qt UI
remains display-only unless --internet is supplied.

## Local protocol and ownership

One QProcess runs backend/internet.php; newline-delimited UTF-8 JSON travels on
its private stdin/stdout pipes, diagnostics on stderr. There is no server,
listening socket, shell command evaluation or parsing of radio-cli output.
A ready event announces protocol 1, station UUID/name pairs and initial volume.
Commands are ping, play (id), stop, volume (0..1), quit. Replies are ready,
state, metadata, volume, request_error or fatal error. Core sessions perform
selection, playlist resolution, decoding, metadata, volume verification and
cleanup. Qt drives display and forwards user actions only.

PHP polls every ~20 ms plus library poll time. Shutdown, stdin EOF, ordinary
signals and a 15-second missing GUI heartbeat all pass through finally/close.
The Qt exit path allows eight seconds for PHP cleanup; an exceeded budget is
reported. Abruptly killing the PHP backend itself cannot run finally and is not
covered by the ordinary-disconnect guarantee. Do not kill the child as a
substitute for checking normal cleanup.

Queues are bounded (64 KiB input backlog, 4 KiB commands, 1 MiB output backlog,
8 KiB GUI stderr tail). The GUI supports a startup catalogue up to 2 MiB and
1000 stations. Playback diagnostic retention follows the library's policy;
this is not a total disk quota. The existing EGLFS timeout wrapper remains
an outer recovery guard and is not a playback supervisor.
