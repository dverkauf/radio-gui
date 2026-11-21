<?php

declare(strict_types=1);

use Radio\Internet\InternetPlaybackSource;
use Radio\Internet\StationCatalogue;
use Radio\Playback\PlaybackOptions;
use Radio\Playback\PlaybackVolumeControl;

// Dedicated child process. stdout is reserved for protocol messages.
ini_set('display_errors', 'stderr');
$session = null;
$output = '';
$input = '';
$quit = false;
$lastState = null;
$lastVolume = null;
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
    $catalogue = new StationCatalogue($directory);
    $source = new InternetPlaybackSource($config, $directory, $autoload);
    $cataloguePath = $directory . '/internet-stations.json';
    if (is_file($cataloguePath) && filesize($cataloguePath) > 2097152) {
        throw new RuntimeException('Saved station catalogue exceeds 2 MiB.');
    }
    $stations = $catalogue->all();
    if (count($stations) > 1000) {
        throw new RuntimeException('This GUI milestone supports at most 1000 saved stations.');
    }
    $allowed = array_column($stations, null, 'station_uuid');
    $emit(['type' => 'ready', 'protocol' => 1, 'stations' => array_map(
        static fn(array $s): array => ['id' => $s['station_uuid'], 'name' => $s['name']],
        $stations
    ), 'volume' => $options->volume]);
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
                    case 'quit': $quit = true; break;
                    case 'play':
                        if ($session !== null) { throw new LogicException('Stop current playback first.'); }
                        $id = $request['id'] ?? null;
                        if (!is_string($id) || !isset($allowed[$id])) {
                            throw new InvalidArgumentException('Choose a saved internet station.');
                        }
                        $session = $source->start($id, $options);
                        $lastState = null;
                        $lastVolume = null;
                        break;
                    case 'stop': $session?->requestStop(); break;
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
                $emit(['type' => 'request_error', 'message' => $error->getMessage()]);
            }
        }
        if ($quit) { break; }
        if (microtime(true) - $lastContact > 15) {
            throw new RuntimeException('GUI heartbeat expired.');
        }
        if ($session !== null) {
            foreach ($session->poll() as $event) {
                $emit(['type' => 'metadata', 'kind' => $event->type, 'text' => $event->text]);
            }
            $state = $session->state();
            if ($lastState !== $state->value) {
                $lastState = $state->value;
                $emit(['type' => 'state', 'state' => $lastState,
                    'volume_control' => $session instanceof PlaybackVolumeControl]);
            }
            if ($session instanceof PlaybackVolumeControl && $lastVolume !== $session->volume()) {
                $lastVolume = $session->volume();
                $emit(['type' => 'volume', 'value' => $lastVolume]);
            }
            if ($state->isTerminal()) {
                $session->close();
                $session = null;
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
