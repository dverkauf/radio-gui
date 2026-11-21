# DAB+ reception locations

Open DAB+ → Scan → Reception locations. Everyday presets remain on the main screen.

Choose New location, enter a name using the multilingual touch keyboard, and select
one or more DAB blocks. Save and select stores the plan and makes it active. Choose
an existing plan to change its blocks, or use Use saved location to activate it.
Existing names stay fixed; create a new plan if you need a different name.

The scan screen shows the selected blocks before Start new scan. Use full Band III
scans all 38 supported blocks when you do not know the local plan. Plans describe
reception areas manually; they do not detect GPS position or download transmitter
coverage. A plan can include blocks with no reception at your present position.

Delete location requires a second confirmation and removes only the named plan.
Saved DAB stations, other presets, subscriptions and listening progress stay intact.
Deleting the active plan selects full Band III. Full Band III itself cannot be deleted.

Named plans live in the existing `dab.locations` configuration, validated by
radio-lib's LocationChannels. Active selection lives in `gui-scan-settings.json`.
Unrelated JSON configuration fields and object/array types are preserved. Every
configuration edit retains one private exact previous version at
`config.json.before-locations`; the next edit replaces that backup.

The editor uses a bounded PHP worker, private atomic file replacements and an
advisory editor lock. A revision rejects stale changes to config or selection;
reopen the editor if another tool changed settings. External writers that ignore
the editor lock should not run concurrently. Configuration and selection are
separate file writes, not a multi-file transaction: an interrupted update can save
a plan without changing the active selection. Reopen to inspect and select it.

Validation on the Pi:

```sh
php -l backend/ReceptionLocations.php
php -l backend/locations.php
/usr/bin/python3 -X faulthandler -m unittest -v test_reception_locations test_location_bridge
/usr/bin/python3 -X faulthandler -m unittest discover -v
```
