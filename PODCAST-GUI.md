# Saved podcast browsing and playback

Run `python3 main.py --radio` and open Podcasts. Tap a saved subscription,
then an episode to play it. Back returns to subscriptions. Previous/Next page
through forty episodes at a time, in the saved feed's publisher order. Browsing
and changing tabs leave existing playback running; tapping an episode uses the
same stop/close/then-start queue as radio stations. A queued episode keeps its
identity even if the browser moves to another page or feed before switching ends.

Only the saved podcasts.json snapshots are browsed. There are no network feed
refreshes, subscription edits, podcast-directory searches or media downloads in
the browsing path. Use radio-cli to subscribe/refresh, then reopen the GUI.
Starting playback streams the episode audio through the existing library.

## Playback and progress

The backend registers Radio\Podcast\PodcastPlaybackSource with explicitly enabled
PodcastProgressOptions. The library loads unfinished progress and resumes with
its default ten-second rewind. It checkpoints during listening and on supported
pause/stop/completion paths, using the same ~/.radio/podcast-progress store as the
CLI. Completed episodes follow the library's existing replay policy. Merely
browsing never creates listening progress or modifies saved feeds. The repository
may create its normal sidecar lock when reading an existing saved catalogue.

Full feed IDs and full episode keys are sent to the library; titles and list row
numbers are never playback identities. SavedPodcasts uses the library repository,
models and EpisodeSelectionResolver. Display labels may be truncated at 128
Unicode characters; IDs and selections are retained in full. Logical Hebrew and
Greek strings pass unchanged to Qt's text engine; no terminal visual-RTL filter
is applied. Feed pages do not expose media URLs to QML.

The active podcast adds Pause/Resume and -15/+15-second buttons. Support comes
from session capabilities; controls are disabled during startup/stopping and
for unsupported radio sessions. Pause buttons wait for reported state before
allowing another toggle. Seeking uses the reported content position or a pending
seek target; rapid requests accumulate, clamp at zero, and ignore old timeline
acknowledgements. Stop clears a pending station/episode switch. Seeks preserve
pause and volume through the library.

Position is a source estimate from decoded media, not an audible speaker clock.
Unknown position is displayed as unavailable. A pending seek shows its requested
target until a matching request revision reports a new position. RSS duration
hints are not treated as verified media duration or used as seek bounds. There is
no invented wall-clock timeline or percentage-complete bar.

Volume retains separate requested and confirmed values. Paused podcast volume
requests may await resume, as defined by the library. Timeline updates occur at
most four times per second and have separate browser notifications so lists are
not rebuilt on every position update.

## Process and storage boundaries

The existing locked library already supports this source; no Composer update is
needed. There is still one owned PHP backend and at most one active playback
session. Catalogue objects are read once by that backend before playback starts;
episode pages use the in-memory snapshot, avoiding catalogue locks during audio
polling. JSON catalogue locking/filesystem I/O can delay backend startup; it does
not run on the Qt event thread. Existing library storage limits apply (16 MiB
podcast catalogue); GUI subscription limit is 1000. Labels/pages bound protocol
size, with the existing one-MiB output queue limit still applying to ready data.
Late page replies are discarded using a monotonically increasing browse request
ID. A malformed podcast catalogue is isolated from FM/DAB/Internet catalogues.

Core workers still own asynchronous media resolution, progress writes, pause,
seek, volume verification and cleanup. Qt's window-exit allowance is increased
to ten seconds to accommodate the podcast session's documented checkpoint cleanup
budget. Normal stop remains incrementally polled. Abruptly killing the PHP child
cannot guarantee cleanup; normal Exit, signals, EOF and heartbeat loss retain the
existing supervised cleanup path. This change does not alter radio-mono.service;
the intermittent sink-service issue recorded in RADIO-PLAYBACK.md remains open.

## Native validation

```bash
php -l backend/SavedPodcasts.php
php -l backend/radio.php
/usr/bin/python3 -m unittest -v \
  test_keyboard_layouts.py test_keyboard_editor.py \
  test_internet_backend.py test_internet_bridge.py \
  test_radio_backend.py test_radio_bridge.py \
  test_podcast_backend.py test_podcast_bridge.py
QT_QUICK_BACKEND=software /usr/bin/python3 main.py \
  --platform offscreen --radio --timeout 3
```

Expected: 46 tests with the required PHP/Composer/PySide6 installation; skipped
PHP tests do not qualify the backend. New tests cover saved repository pages,
Unicode/full keys, missing episodes and invalid controls, snapshot preservation,
corrupt-catalogue isolation, stale browse responses, queue identity across
navigation, pause state, accumulated seek acknowledgement, stable models, and
unsupported radio controls. Fake peers do not validate real media or PipeWire.

## Live acceptance on the Pi

```bash
/usr/bin/python3 preview_wayland.py --radio
```

Select a saved podcast and episode, listen, pause/resume, seek in both directions,
change volume, Stop, and play the same episode again. The second session should
resume near the saved position with a ten-second rewind. Actual decoded audio,
not merely the position label, must resume. Test a paused seek followed by Resume.
Switch podcast -> FM/DAB/Internet and back; Exit during playback. Check that owned
audio tools are gone, while radio-mono.service remains running. After Wayland
acceptance, repeat from SSH with unsaved desktop work closed:

```bash
/usr/bin/python3 test_eglfs.py --rotation 90 --seconds 120 --radio
```

Progress can be inspected using the existing radio-cli podcast progress command.
No new feed fetch should happen simply by opening the Podcasts tab.
