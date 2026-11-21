<?php

declare(strict_types=1);

use Radio\Internet\InternetPlaybackSource;
use Radio\Fm\FmPlaybackSource;
use Radio\Dab\DabPlaybackSource;
use Radio\Playback\PlaybackSourceRegistry;
use Radio\Playback\PlaybackOptions;
use Radio\Playback\PlaybackVolumeControl;
use Radio\Podcast\PodcastPlaybackSource;
use Radio\Podcast\PodcastProgressOptions;

// Dedicated child process. stdout is reserved for protocol messages.
ini_set('display_errors', 'stderr');
$session = null;
$output = '';
$input = '';
$quit = false;
$lastState = null;
$lastVolume = null;
$lastTimelineAt = 0.0;
$seekRequest = 0;
$lastContact = microtime(true);
$exit = 0;
$emit = static function (array $message) use (&$output): void {
    $line = json_encode($message, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE) . "\n";
    if (strlen($line) + strlen($output) > 1048576) {
        throw new RuntimeException('GUI output queue exceeded its limit.');
    }
    $output .= $line;
};
try {
    $autoload = dirname(__DIR__) . '/vendor/autoload.php';
    if (!is_file($autoload)) {
        throw new RuntimeException('Run composer install in radio-gui first.');
    }
    require $autoload;
    require __DIR__ . '/SavedRadioStations.php';
    require __DIR__ . '/SavedPodcasts.php';
    $directory = $argv[1] ?? '';
    if (!str_starts_with($directory, '/') || !is_dir($directory)) {
        throw new RuntimeException('An existing absolute configuration directory is required.');
    }
    $path = $directory . '/config.json';
    if (!is_file($path) || filesize($path) > 1048576) {
        throw new RuntimeException('Missing or oversized config.json.');
    }
    $bytes = file_get_contents($path);
    if ($bytes === false) {
        throw new RuntimeException('Cannot read config.json.');
    }
    $document = json_decode($bytes, false, 64, JSON_THROW_ON_ERROR);
    if (!$document instanceof stdClass) {
        throw new RuntimeException('config.json must contain an object.');
    }
    $config = json_decode($bytes, true, 64, JSON_THROW_ON_ERROR);
    $options = PlaybackOptions::fromConfig($config);
    $registry = new PlaybackSourceRegistry([
        new FmPlaybackSource($config, $directory, $autoload),
        new DabPlaybackSource($config, $directory, $autoload),
        new InternetPlaybackSource($config, $directory, $autoload),
        new PodcastPlaybackSource($config, $directory, $autoload, new PodcastProgressOptions(enabled: true)),
    ]);
    $saved = SavedRadioStations::load($directory);
    $allowed = array_column($saved['stations'], null, 'id');
    $podcasts = new SavedPodcasts($directory);
    if ($podcasts->error() !== null) { $saved['errors']['podcast'] = $podcasts->error(); }
    $emit(['type' => 'ready', 'protocol' => 1, 'stations' => array_map(
        static function (array $s): array { unset($s['selection']); return $s; },
        $saved['stations']
    ), 'subscriptions' => $podcasts->summaries(), 'catalogue_errors' => (object) $saved['errors'], 'volume' => $options->volume]);
    $recover = static function (Throwable $error) use (&$session, $emit): void {
        // A cleanup failure remains fatal; never announce receiver availability first.
        $session?->close();
        $session = null;
        $emit(['type' => 'session_error', 'message' => $error->getMessage()]);
        $emit(['type' => 'state', 'state' => 'stopped', 'volume_control' => false]);
    };
    pcntl_async_signals(true);
    foreach ([SIGINT, SIGTERM, SIGHUP] as $signal) {
        pcntl_signal($signal, static function () use (&$quit): void { $quit = true; });
    }
    stream_set_blocking(STDIN, false);
    stream_set_blocking(STDOUT, false);
    while (!$quit) {
        $read = [STDIN];
        $write = $output === '' ? [] : [STDOUT];
        $except = [];
        // Signals may interrupt select; the flag is checked at the loop boundary.
        $selected = @stream_select($read, $write, $except, 0, 20000);
        if ($selected === false) {
            if ($quit) { break; }
            continue;
        }
        if ($write !== []) {
            $written = fwrite(STDOUT, $output);
            if ($written === false) { throw new RuntimeException('GUI connection closed.'); }
            $output = substr($output, $written);
        }
        if ($read !== []) {
            $chunk = fread(STDIN, 8192);
            if ($chunk === false || ($chunk === '' && feof(STDIN))) { break; }
            $input .= $chunk;
            if (strlen($input) > 65536) { throw new RuntimeException('GUI input queue exceeded its limit.'); }
        }
        for ($count = 0; $count < 32 && ($newline = strpos($input, "\n")) !== false; ++$count) {
            $line = substr($input, 0, $newline);
            $input = substr($input, $newline + 1);
            if (strlen($line) > 4096) { throw new RuntimeException('GUI request is too large.'); }
            $request = json_decode($line, true, 16, JSON_THROW_ON_ERROR);
            if (!is_array($request) || !is_string($request['command'] ?? null)) {
                throw new RuntimeException('Invalid GUI request.');
            }
            $lastContact = microtime(true);
            try {
                switch ($request['command']) {
                    case 'ping': break;
                    case 'reload':
                        $newSaved = SavedRadioStations::load($directory);
                        $newPodcasts = new SavedPodcasts($directory);
                        if ($newPodcasts->error() !== null) { $newSaved['errors']['podcast'] = $newPodcasts->error(); }
                        $allowed = array_column($newSaved['stations'], null, 'id');
                        $podcasts = $newPodcasts;
                        $emit(['type' => 'catalogue', 'protocol' => 1, 'stations' => array_map(
                            static function (array $s): array { unset($s['selection']); return $s; },
                            $newSaved['stations']
                        ), 'subscriptions' => $podcasts->summaries(), 'catalogue_errors' => (object) $newSaved['errors']]);
                        break;
                    case 'quit': $quit = true; break;
                    case 'episodes':
                        $feed = $request['feed'] ?? null;
                        $page = $request['page'] ?? null;
                        $requestId = $request['request_id'] ?? null;
                        if (!is_string($feed) || !is_int($page) || !is_int($requestId) || $requestId < 1) {
                            throw new InvalidArgumentException('Invalid episode page request.');
                        }
                        $emit(['type' => 'episodes', 'request_id' => $requestId] + $podcasts->page($feed, $page));
                        break;
                    case 'play':
                        if ($session !== null) { throw new LogicException('Stop current playback first.'); }
                        $id = $request['id'] ?? null;
                        if (!is_string($id)) { throw new InvalidArgumentException('Choose a saved selection.'); }
                        $entry = str_starts_with($id, 'podcast/')
                            ? $podcasts->selection($id)
                            : ($allowed[$id] ?? throw new InvalidArgumentException('Choose a saved radio station.'));
                        $session = $registry->get($entry['source'])->start($entry['selection'], $options);
                        $lastTimelineAt = 0.0;
                        $seekRequest = 0;
                        $lastState = null;
                        $lastVolume = null;
                        break;
                    case 'stop': $session?->requestStop(); break;
                    case 'pause':
                    case 'resume':
                        if ($session === null || !$session->capabilities()->canPause) {
                            throw new LogicException('Pause/resume is unavailable.');
                        }
                        $request['command'] === 'pause' ? $session->pause() : $session->resume();
                        break;
                    case 'seek':
                        if ($session === null || !$session->capabilities()->canSeek) {
                            throw new LogicException('Seeking is unavailable.');
                        }
                        $seconds = $request['seconds'] ?? null;
                        $sequence = $request['request_id'] ?? null;
                        if ((!is_int($seconds) && !is_float($seconds)) || !is_finite((float) $seconds)
                            || $seconds < 0 || !is_int($sequence) || $sequence < 1) {
                            throw new InvalidArgumentException('Invalid seek position.');
                        }
                        $session->seek((float) $seconds);
                        $seekRequest = $sequence;
                        $lastTimelineAt = 0.0;
                        break;
                    case 'volume':
                        if (!$session instanceof PlaybackVolumeControl) {
                            throw new LogicException('Volume is unavailable.');
                        }
                        $volume = $request['value'] ?? null;
                        if ((!is_int($volume) && !is_float($volume)) || !is_finite((float) $volume) || $volume < 0 || $volume > 1) {
                            throw new InvalidArgumentException('Volume must be between zero and one.');
                        }
                        $session->setVolume((float) $volume);
                        break;
                    default: throw new InvalidArgumentException('Unknown GUI command.');
                }
            } catch (LogicException $error) {
                $emit(['type' => 'request_error', 'message' => $error->getMessage(),
                    'command' => $request['command'], 'request_id' => $request['request_id'] ?? null]);
            } catch (Throwable $error) {
                if ($request['command'] === 'reload') {
                    $emit(['type' => 'request_error', 'command' => 'reload', 'message' => $error->getMessage()]);
                } else {
                    $recover($error);
                }
            }
        }
        if ($quit) { break; }
        if (microtime(true) - $lastContact > 15) {
            throw new RuntimeException('GUI heartbeat expired.');
        }
        if ($session !== null) {
            try {
                foreach ($session->poll() as $event) {
                    $emit(['type' => 'metadata', 'kind' => $event->type, 'text' => $event->text,
                        'source' => $event->source, 'identifier' => $event->identifier]);
                }
                $state = $session->state();
                $volumeControl = $session instanceof PlaybackVolumeControl;
                $confirmedVolume = $volumeControl ? $session->volume() : null;
                if ($state->isTerminal()) {
                    $session->close();
                    $session = null;
                    $volumeControl = false;
                }
                if ($lastState !== $state->value) {
                    $lastState = $state->value;
                    $emit(['type' => 'state', 'state' => $lastState, 'volume_control' => $volumeControl]);
                }
                if ($session !== null && microtime(true) - $lastTimelineAt >= 0.25) {
                    $caps = $session->capabilities();
                    $emit(['type' => 'timeline', 'can_pause' => $caps->canPause, 'can_seek' => $caps->canSeek,
                        'position' => $caps->reportsPosition ? $session->positionSeconds() : null,
                        'duration' => $caps->reportsDuration ? $session->durationSeconds() : null,
                        'seek_request' => $seekRequest]);
                    $lastTimelineAt = microtime(true);
                }
                if ($confirmedVolume !== null && $lastVolume !== $confirmedVolume) {
                    $lastVolume = $confirmedVolume;
                    $emit(['type' => 'volume', 'value' => $lastVolume]);
                }
            } catch (Throwable $error) {
                if ($request['command'] === 'reload') {
                    $emit(['type' => 'request_error', 'command' => 'reload', 'message' => $error->getMessage()]);
                } else {
                    $recover($error);
                }
            }
        }
    }
} catch (Throwable $error) {
    $exit = 1;
    // Write errors to stderr too, including when the protocol peer has disappeared.
    fwrite(STDERR, $error->getMessage() . "\n");
    try { $emit(['type' => 'error', 'message' => $error->getMessage()]); } catch (Throwable) {}
} finally {
    try { $session?->close(); } catch (Throwable $error) {
        $exit = 1;
        fwrite(STDERR, 'Cleanup failed: ' . $error->getMessage() . "\n");
        try { $emit(['type' => 'error', 'message' => 'Playback cleanup failed. See backend diagnostics.']); } catch (Throwable) {}
    }
    // Bound final protocol flushing when the peer is no longer reading.
    stream_set_blocking(STDOUT, false);
    $deadline = microtime(true) + 0.25;
    while ($output !== '' && microtime(true) < $deadline) {
        $read = []; $write = [STDOUT]; $except = [];
        if (@stream_select($read, $write, $except, 0, 20000) > 0) {
            $written = @fwrite(STDOUT, $output);
            if ($written === false) { break; }
            $output = substr($output, $written);
        }
    }
}
exit($exit);
