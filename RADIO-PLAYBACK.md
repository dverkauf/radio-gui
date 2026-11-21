# FM, DAB+ and Internet playback

Start `python3 main.py --radio` for the three-source playback screen. The existing
--internet screen remains supported; no flag still opens the display prototype.
--keyboard-test is unchanged. Run as the normal PipeWire user, never as root.

FM, DAB+ and Internet tabs browse the saved station catalogues in ~/.radio.
Browsing a tab does not stop audio. Tapping a station starts it; tapping another
queues it, stops/closes the old library session, then starts the latest chosen
station. No two sessions are acquired concurrently. Stop clears queued choices,
including a pending cross-source switch. Repeated taps on the active station
leave it playing. New sessions use the initial configured volume. Volume target
and confirmed volume remain separate so confirmations do not move the slider.

The backend composes Radio\Playback\PlaybackSourceRegistry with the library's
FmPlaybackSource, DabPlaybackSource and InternetPlaybackSource. PHP still owns
receiver exclusivity, tuning, audio processes, metadata, volume and cleanup.
Python owns Qt and local protocol supervision. This milestone requires no
radio-lib changes or Composer update: it uses the existing locked dependency.

## Saved stations

- FM: stations.json via Radio\Fm\StationCache. IDs include the exact frequency;
  the library receives a numeric MHz selection, avoiding ambiguous saved names.
- DAB+: dab-stations.json via Radio\Dab\StationCatalogue. IDs use the saved block/
  service identity; duplicate display names stay separate. Data-only services
  are omitted. The source supports the audio types handled by the existing
  library; the tab label DAB+ does not promise every saved service is DAB+.
- Internet: internet-stations.json via Radio\Internet\StationCatalogue. Existing
  UUIDs are preserved. No Radio Browser request is needed to browse saved entries.

Rows display frequency or DAB block/ensemble beside the saved name. The GUI does
not scan, rename or save stations yet. Use radio-cli for that, then reopen the
GUI to load a new snapshot. A malformed/oversized catalogue is reported only on
its own tab; the other catalogues remain usable. Limits are 2 MiB and 1000 entries
per catalogue, with the existing 1 MiB protocol-output queue bound still applying.

## Configuration and reception

The existing --config-dir option works for direct/Wayland launches; default is
~/.radio. FM uses existing receiver.device, receiver.ppm and playback gain/de-
emphasis options. DAB uses the existing library configuration/tool paths.
Required tools/sink remain those used by radio-cli: rtl_fm and redsea for FM,
welle-cli for DAB, plus ffmpeg, pw-play, pw-dump and pw-cli for playback/volume.
No desktop or audio configuration is installed or modified.

Station name and broadcast text come from library events; Unicode stays in
logical order and Qt handles bidirectional rendering. FM RadioText is best effort
and depends on RDS reception; good audio does not guarantee decoded RadioText.
DAB text likewise depends on transmission. Missing programme text alone is not
an audio failure.

An operational playback error closes the session before reporting a stopped
state; another station/source may then be tapped. Invalid/unsupported requests
report request_error. A failed cleanup or protocol/process failure remains fatal,
with the error visible; reopen the app to reconnect. Never announce receiver
availability after an unconfirmed cleanup. Ordinary exit, signals, EOF and GUI
heartbeat timeout retain the existing cleanup path.

## Code compatibility

playback_bridge.py and backend/radio.php are now the shared implementation.
internet_bridge.py and backend/internet.php remain tiny compatibility adapters
so the already-tested internet entry points and tests continue to work. Protocol
1 ready messages include a source on each station and optional catalogue_errors;
legacy test peers without a source are treated as internet. New session_error
messages are recoverable only after backend cleanup has succeeded.

## Native checks

```bash
php -l backend/SavedRadioStations.php
php -l backend/radio.php
php -l backend/internet.php
/usr/bin/python3 -m unittest -v \
  test_keyboard_layouts.py test_keyboard_editor.py \
  test_internet_backend.py test_internet_bridge.py \
  test_radio_backend.py test_radio_bridge.py
QT_QUICK_BACKEND=software /usr/bin/python3 main.py \
  --platform offscreen --radio --timeout 3
```

Expected: 34 tests with PHP/Composer/PySide6 installed. A skipped PHP test is not
qualification. Added checks cover ambiguous names, DAB data filtering, per-source
catalogue failures, read-only startup, a deliberately invalid FM gain rejected
before tools/receiver acquisition, tab browsing, cross-source switching, failure
recovery and invalid protocol source rejection. Fake peers do not qualify native
radio hardware or real PipeWire operations.

## Live check on the Pi

```bash
/usr/bin/python3 preview_wayland.py --radio
```

Play a saved FM station, switch to DAB+, then Internet. Try rapid station changes,
Stop during startup and during a source switch, repeat tap, and volume. Exit while
playing. Check for unexpected surviving processes:

```bash
for tool in rtl_fm redsea welle-cli ffmpeg pw-play pw-cli; do
    pgrep -a -u "$USER" -x "$tool"
done
```

Do not run a competing radio-cli playback/scan during this test. The library's
receiver lock should reject competing receiver ownership, not terminate another
owner. After Wayland acceptance, close unsaved desktop work and run from SSH:

```bash
/usr/bin/python3 test_eglfs.py --rotation 90 --seconds 120 --radio
```

The recovery launcher restores the previously active desktop, as before. No
permanent kiosk/autostart service is installed by this change.

## Open audio-service issue

The shared radio-mono.service intermittently exits and hits its restart limit.
Playback subsequently passed under Wayland and EGLFS after service recovery.
The post-EGLFS check showed the service running with NRestarts=2; when those
restarts occurred is unconfirmed. Diagnostic logging was added temporarily.
The cause remains unresolved; no permanent audio-service fix is claimed.
