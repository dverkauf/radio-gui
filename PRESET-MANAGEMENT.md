# Identification, saving and preset management

FM scan results now have separate Identify and Save preset buttons. Identify
captures RDS into the private scan preview (up to 30 seconds), displaying station
name, PI and radio text when received. It does not modify the actual preset
catalogue. Save preset becomes available only after a confirmed name/PI is
recorded; it persists that reviewed identity without fetching RDS again. Retry
Identify if reception is insufficient. A new scan creates a new review snapshot.

The manual Refresh presets button is replaced by Manage presets. Catalogue
refresh happens after a save/delete, on source-tab selection and when returning
from discovery, scanning or management. Normal preset taps still start playback.

Manage presets lists only the chosen source's saved entries. Delete is followed
by a second confirmation on the same row, with the station name visible and an
explicit Cancel. DAB removes only the selected service, retaining other services
and block metadata. Internet uses its UUID and FM uses exact Hz. No receiver or
network connection is needed for deletion. Stop GUI playback before removal;
the screen provides a Stop playback button. Also stop other CLI playback before
removing podcast progress, to avoid new checkpoints being written afterwards.

Podcasts show Unsubscribe. Listening progress is kept by default. A separate,
unchecked option explicitly removes stored progress for the selected podcast.
The shared library removes only that feed's checkpoint files using per-episode
locks. This is not a multi-file transaction: an error can leave partial progress
removal; another writer can create new checkpoints. If a worker times out during
a delete, reopen management to inspect the saved state before retrying.

The new radio-lib catalogue forget methods and JsonProgressRepository.removeFeed
must be installed before the corresponding delete options work. No package
layout or playback API is otherwise changed. Existing malformed catalogues are
reported rather than overwritten. Missing preset identities are safe no-ops in
the library API; the GUI rejects stale selections and asks to reopen management.

Validation: PHP lint, radio-lib PresetRemovalTest/full suite, GUI full unittest
suite and offscreen startup. Native tests use temporary catalogues/fake workers;
manual tests must verify Identify leaves presets unchanged until Save, review of
RDS info, source-specific delete confirmation/cancel, retained DAB neighbours and
unsubscribe with retained/removed progress.

## Preset ordering

Use Move up and Move down under Manage presets (or Manage subscriptions). The
order is remembered independently for FM, DAB+, Internet and podcast subscriptions,
and is applied on startup and catalogue refresh. Episode chronology is unchanged.
The moved row is outlined and kept visible. End-of-list moves are disabled.

Ordering works during playback and refreshes the main list after acknowledgement;
it does not stop or restart the current session or change volume. Deleting still
requires playback to stop and a separate confirmation.

Preferences use stable preset IDs in `~/.radio/gui-preset-order.json`, separate
from library catalogues. Duplicate station names can be ordered independently.
New presets follow existing ordered entries. Deleted IDs are ignored; a later
move prunes absent IDs for that source. Re-adding exactly the same ID can restore
its old position until such pruning. CLI catalogue ordering is unchanged.

Writes use a private atomic replacement and a nonblocking advisory lock. Stale
list revisions are rejected: reopen Manage presets if another editor changed the
list. A malformed preference file is preserved; listening falls back to catalogue
order, while management reports the error instead of overwriting it. External
catalogue writers should not run concurrently with management operations.

Native checks: `test_preset_order.py` covers preference integrity and startup/reload
integration. `test_preset_order_bridge.py` covers acknowledged updates and playback
preservation. Run the full suite before committing.
