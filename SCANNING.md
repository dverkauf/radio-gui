# Secondary FM and DAB+ discovery

Presets remain the main screen. Scan stations opens an infrequently used second
screen on FM and DAB+, using the same navigation level as Internet/podcast Find.

## Receiver ownership

Start new scan stops this GUI's active FM/DAB session and waits for its terminal
acknowledgement before launching a scanner. Internet and podcast sessions may
continue. Other processes are protected by the library's receiver.lock; a busy
receiver is reported, not stolen. Closing the panel is disabled while a job owns
resources. Cancel remains available while scanning or identifying an FM result.

The owned PHP worker runs existing synchronous library scanners outside Qt and
outside the playback backend. Progress reports phases and DAB block numbers,
not an invented percentage. Cancellation sends TERM and waits for library cleanup
(up to 8 seconds); it does not immediately announce a free receiver. A stuck
worker has a dedicated process group, allowing emergency group termination
without signalling the GUI. Unexpected cleanup failures still require checking
tools/receiver diagnostics before retrying. Scanning does not auto-resume a
previous RF station; tap its preset when finished.

## FM

Uses the configured scan range, gain, device, PPM and integration, through
SpectrumScanner, SpectrumParser and CandidateSelector. At most 20 frequency
candidates are previewed. Integration is capped at 120 seconds for the GUI;
invalid settings fail before capture. Signal strength alone is not a verified
station identity.

Identify runs a bounded (at most 30-second) RdsCapture at the chosen
frequency. Its automatically updated cache is in a private staging directory,
not the real presets. The confirmed PI/name and received radio text are shown in the preview. A
separate Save preset action then writes the reviewed identity via StationCache. No synthetic PI or unverified name is written. Failure to receive
RDS leaves presets unchanged; improve reception or try another candidate.
Raw spectrum/RDS diagnostics remain under the shared scans directory.

## DAB+ reception location

The dropdown reads existing named block lists in config.json under dab.locations,
using LocationChannels validation. Names can identify a town, region or country;
they are not inferred from IP, GPS, language or timezone. The last chosen name
is stored separately in gui-scan-settings.json; config.json is not rewritten.
Unknown/missing/deleted location defaults to an explicit Full Band III option,
not the first regional list. Its 38 blocks can take approximately 30 minutes;
cancel when appropriate. A known local block list is much faster. This stage
selects existing plans; it does not provide a GUI editor for location plans.

Each block uses EnsembleScanner (up to 45 seconds per block) and EnsembleParser.
Unreceived blocks produce warnings; successful blocks still appear in preview.
Cancellation discards the pending preview and leaves presets unchanged. Selecting
a new location does not erase stations saved at a previous location.

The existing library updates catalogues by whole ensemble block, not individual
service. Each preview row shows block/ensemble and received service names. Save
block, followed by Confirm save block, explicitly replaces that block's saved
services with all services in the snapshot; other blocks are retained. This is
not a hidden replace-all operation or an individual-service selection UI.

No audio audition of unsaved RF candidates is included yet. Preview here means
reviewing received candidates/ensemble service lists before explicit saving.

## Saving and interruptions

Presets refresh after a successful save and on Back. FM identity writes and DAB
catalogue writes use existing library stores. If cancellation/exit happens at a
save boundary, refresh presets before retrying: an atomic save may already have
committed. Scan previews are private opaque-token files, validated before save;
requests cannot choose arbitrary snapshot paths.

## Native validation

    php -l backend/ScanOperations.php
    php -l backend/scan.php
    /usr/bin/python3 -X faulthandler -m unittest -v test_scan_backend test_scan_bridge
    /usr/bin/python3 -X faulthandler -m unittest discover -v
    QT_QUICK_BACKEND=software /usr/bin/python3 main.py --platform offscreen --radio --timeout 3

Automated checks use fake executables, mock protocol peers and temporary data:
FM spectrum without auto-save; cancellation with an ignoring child and released
receiver lock; DAB preview/save through the real parser/store; invalid snapshot
keys; local channel plans, deduplication and remembered selection; RF playback
stop acknowledgement; Internet playback preservation; cancellation completion.
The copied DAB fixture contains sample broadcast data from radio-lib's tests.
No automated test opens an SDR or contacts the network.

Manual: retain the working direct USB arrangement until replacement-hub testing.
Try cancel first, then a complete FM scan; identify a new candidate, review RDS info, then Save preset, return
to presets and play. Try a configured DAB location, cancel/retry, inspect block
services and confirm an explicit block save. Return and play. Check rtl_power,
rtl_fm, redsea, welle-cli, ffmpeg, pw-play and pw-cli are absent after exit.
Keep the current mono-service restart counter with the test report.

## Edit reception plans

DAB+ scanning offers a secondary Reception locations screen for named block plans,
selection and confirmed deletion. See [RECEPTION-LOCATIONS.md](RECEPTION-LOCATIONS.md).
The selected blocks are shown before scanning; full Band III remains available.
