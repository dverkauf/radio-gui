# Secondary directory discovery

Presets remain the initial Radio screen. A smaller Find stations / Find podcasts
button opens Internet or Podcast discovery below the main source navigation.
Back to Presets returns in one tap. The discovery panel does not switch or stop
current playback. Its volume/transport controls remain on the presets screen.

Enter a name using a physical keyboard or the existing EN/DE/ES/Hebrew/Greek
keyboard; Search or Enter submits it. Queries are limited to 200 UTF-8 bytes.
Twenty results are displayed as logical Unicode plain text. Cancel stops a
search and reaps its owned process. Results are temporary and create no presets.

Save explicitly adds an Internet preset using Radio Browser's authoritative UUID
lookup and the library StationCatalogue. Subscribe fetches the selected RSS URL
using HttpFeedFetcher, then uses JsonSubscriptionRepository. Library locks,
validation and atomic writes are retained. No credentials are requested by the
GUI; podcast discovery uses the library's existing keyless Podcast Index endpoint.
Saved custom Internet names are preserved by the library. Naming conflicts and
invalid/corrupt stores are reported rather than silently replaced.

Saving disables panel navigation/cancellation to avoid an ambiguous interruption
at commit. A 30-second worker deadline still applies, including lock waits. If a
save times out or the app exits during saving, it may already have committed;
return to Presets and Refresh before retrying. Searches never auto-save. This
first stage adds Save/Subscribe, then tap-to-play from presets; it does not yet
preview unsaved streams or allow custom preset names from discovery.

A successful save requests a bounded catalogue refresh from the existing PHP
playback backend. The bridge keeps current session state, volume targets and
metadata. Back and source-tab selection also reload the catalogue. No backend process
restart is required. Podcast pages already being viewed retain their current
snapshot until reopened. Library catalogue locking remains synchronous on reload,
as it is for existing saved-episode paging; a store locked by another application
can delay the playback backend. Network operations are in the separate worker.

Workers use argument arrays and JSON stdin (no shell), capped request/response
sizes, bounded diagnostics and a single owned process per job. PHP stores data
only in the configured shared directory. DNS/network errors remain recoverable;
failed directory discovery does not terminate the separate playback process.

## Validation on the Pi

    php -l backend/discovery.php
    php -l backend/DiscoveryOperations.php
    php -l backend/radio.php
    /usr/bin/python3 -m unittest discover -v
    QT_QUICK_BACKEND=software /usr/bin/python3 main.py --platform offscreen --radio --timeout 3
    /usr/bin/python3 preview_wayland.py --radio --timeout 900

New offline tests use Symfony MockHttpClient for directory normalization, storage
preservation and explicit save behavior; fake owned peers cover cancellation,
worker deadline, malformed output, save acknowledgement and playback state on
catalogue refresh. A native Qt scene test loads the discovery panel and keyboard.
No live network, receiver or audio device is used by automated tests.

Manual acceptance: search Hebrew/Greek/Latin text, cancel/retry, save an Internet
station, subscribe to a podcast, return to presets and play each. Repeat a search
while another station is playing. Check all four sources still work, exit, and
check that no discovery.php or owned playback tools remain.

FM/DAB+ scan discovery is now available on the same secondary navigation level.
See SCANNING.md for receiver cleanup, preview-before-save and remembered DAB+
reception locations. No Internet IP geolocation or automatic preset replacement
is introduced by directory discovery.
