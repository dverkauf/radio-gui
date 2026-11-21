<?php

declare(strict_types=1);

use Radio\Dab\LocationChannels;
use Radio\Dab\EnsembleScanner;
use Radio\Dab\EnsembleParser;
use Radio\Dab\StationCatalogue as DabCatalogue;
use Radio\Fm\SpectrumScanner;
use Radio\Fm\SpectrumParser;
use Radio\Fm\CandidateSelector;
use Radio\Fm\RdsCapture;
use Radio\Fm\RdsCaptureOptions;
use Radio\Fm\StationCache;

/** GUI composition only: scanners, parsers and preset stores remain in radio-lib. */
final class ScanOperations
{
    public static function readJson(string $path, int $limit = 1048576): array
    {
        if (!is_file($path) || filesize($path) > $limit) { throw new RuntimeException('Missing or oversized scan data.'); }
        $document = json_decode(file_get_contents($path), true, 64, JSON_THROW_ON_ERROR);
        if (!is_array($document)) { throw new RuntimeException('Invalid scan data.'); }
        return $document;
    }

    public static function writeJson(string $path, array $value): void
    {
        $mask = umask(0077);
        $temporary = $path . '.tmp-' . bin2hex(random_bytes(6));
        try {
            $bytes = json_encode($value, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE);
            if (file_put_contents($temporary, $bytes) !== strlen($bytes) || !rename($temporary, $path)) {
                throw new RuntimeException('Cannot save scan data.');
            }
        } finally {
            if (is_file($temporary)) { unlink($temporary); }
            umask($mask);
        }
    }

    public static function locations(array $config): array
    {
        $result = [];
        foreach (array_keys($config['dab']['locations'] ?? []) as $name) {
            if (!is_string($name) || strlen($name) > 100 || count($result) >= 50) {
                throw new RuntimeException('Invalid or excessive DAB reception locations.');
            }
            if ($name === '__full_band__') { throw new RuntimeException('Reserved DAB location name.'); }
            $result[] = ['name' => $name, 'channels' => (new LocationChannels())->resolve($config, $name)];
        }
        $all = [];
        for ($n = 5; $n <= 13; ++$n) {
            foreach (str_split($n === 13 ? 'ABCDEF' : 'ABCD') as $letter) { $all[] = "$n$letter"; }
        }
        $result[] = ['name' => '__full_band__', 'channels' => $all];
        return $result;
    }

    public static function settings(string $directory, array $config): array
    {
        $locations = self::locations($config);
        $selected = '';
        $path = $directory . '/gui-scan-settings.json';
        if (is_file($path)) {
            $selected = self::readJson($path, 4096)['dab_location'] ?? '';
        }
        // Unknown location never silently uses the first regional plan.
        if (!is_string($selected) || !in_array($selected, array_column($locations, 'name'), true)) {
            $selected = '__full_band__';
        }
        return ['type' => 'settings', 'locations' => $locations, 'location' => $selected];
    }

    public static function fmConfig(array $config): array
    {
        $config['receiver'] = ($config['receiver'] ?? []) + ['device' => '0', 'ppm' => 0];
        $config['tools'] = ($config['tools'] ?? []) + ['rtl_power' => 'rtl_power', 'rtl_fm' => 'rtl_fm', 'redsea' => 'redsea'];
        $config['scan'] = ($config['scan'] ?? []) + ['start_mhz' => 87.5, 'end_mhz' => 108,
            'bin_khz' => 100, 'integration_seconds' => 10, 'gain_db' => 45, 'limit' => 12];
        $config['rds'] = ($config['rds'] ?? []) + ['sample_rate' => 171000, 'gain_db' => 45,
            'capture_seconds' => 30, 'detection_seconds' => 10];
        foreach (['start_mhz' => [87.5,108], 'end_mhz' => [87.5,108], 'bin_khz' => [1,200],
            'integration_seconds' => [1,120], 'gain_db' => [0,50], 'limit' => [1,100]] as $key => [$min,$max]) {
            $v = $config['scan'][$key];
            if ((!is_int($v) && !is_float($v)) || !is_finite((float) $v) || $v < $min || $v > $max) {
                throw new RuntimeException("Invalid scan.$key (GUI integration limit: 120 seconds).");
            }
        }
        if ($config['scan']['start_mhz'] >= $config['scan']['end_mhz']
            || !is_int($config['scan']['integration_seconds']) || !is_int($config['scan']['limit'])) {
            throw new RuntimeException('Invalid FM scan range or integer setting.');
        }
        // Validate executable/device/RDS settings before acquiring hardware.
        RdsCaptureOptions::fromConfig(87500000, $config);
        if (!is_string($config['tools']['rtl_power']) || trim($config['tools']['rtl_power']) === ''
            || str_contains($config['tools']['rtl_power'], "\0")) { throw new RuntimeException('Invalid rtl_power tool.'); }
        return $config;
    }

    public static function preview(string $directory, string $source, array $entries): array
    {
        $job = bin2hex(random_bytes(12));
        $path = $directory . '/scans/gui-' . $job;
        $mask = umask(0077);
        try { if (!mkdir($path, 0700, true)) { throw new RuntimeException('Cannot create scan preview.'); } }
        finally { umask($mask); }
        self::writeJson($path . '/preview.json', ['source' => $source, 'entries' => $entries]);
        return self::items($source, $job, $entries);
    }

    public static function items(string $source, string $job, array $entries): array
    {
        $items = [];
        foreach ($entries as $index => $entry) {
            if ($source === 'fm') {
                $name = number_format($entry['tune_hz'] / 1000000, 1, '.', '') . ' MHz';
                $detail = 'Signal candidate · power ' . number_format($entry['power'], 1, '.', '') . ' · identify before saving';
            } else {
                $name = $entry['channel'] . ' · ' . $entry['ensemble_name'];
                $detail = implode(' · ', array_column($entry['services'], 'name'));
            }
            if ($source === 'fm' && isset($entry['rds_summary'])) {
                $summary = $entry['rds_summary'];
                $identity = $summary['station_identity'] ?? null;
                if ($identity !== null) { $name .= ' · ' . $identity['name']; }
                $pi = $identity['pi'] ?? array_key_first($summary['pi_counts'] ?? []) ?? 'unavailable';
                $radioText = array_key_first($summary['radiotext_counts'] ?? []) ?? 'unavailable';
                $detail = 'PI: ' . $pi . ' · Radio text: ' . $radioText;
            }
            $items[] = ['key' => $job . ':' . $index, 'name' => $name, 'detail' => $detail,
                'can_save' => $source !== 'fm' || isset($entry['identity']),
                'count' => $source === 'fm' ? 1 : count($entry['services'])];
        }
        return $items;
    }

    /** Record identification in the private preview; never change actual presets. */
    public static function recordIdentification(string $directory, string $key, array $summary): array
    {
        self::loadEntry($directory, 'fm', $key);
        preg_match('/^([a-f0-9]{24}):([0-9]{1,2})$/D', $key, $match);
        $path = $directory . '/scans/gui-' . $match[1] . '/preview.json';
        $document = self::readJson($path, 2097152);
        $index = (int) $match[2];
        $entry = &$document['entries'][$index];
        unset($entry['identity']);
        if (is_array($summary['station_identity'] ?? null)) { $entry['identity'] = $summary['station_identity']; }
        $entry['rds_summary'] = $summary;
        self::writeJson($path, $document);
        return self::items('fm', $match[1], $document['entries'])[$index];
    }

    public static function loadEntry(string $directory, string $source, string $key): array
    {
        if (!preg_match('/^([a-f0-9]{24}):([0-9]{1,2})$/D', $key, $match)) { throw new RuntimeException('Invalid scan result.'); }
        $path = $directory . '/scans/gui-' . $match[1] . '/preview.json';
        $document = self::readJson($path, 2097152);
        if (($document['source'] ?? '') !== $source || !isset($document['entries'][(int) $match[2]])) {
            throw new RuntimeException('Scan result is no longer available.');
        }
        return $document['entries'][(int) $match[2]];
    }

    public static function run(string $directory, array $config, array $request, callable $emit, callable $cancel): array
    {
        $source = $request['source'] ?? '';
        $action = $request['action'] ?? '';
        if (!in_array($source, ['fm','dab'], true) || !in_array($action, ['settings','scan','identify','save'], true)) {
            throw new RuntimeException('Invalid scan request.');
        }
        if ($action === 'settings') { return self::settings($directory, $config); }
        if ($action === 'save' || $action === 'identify') {
            $entry = self::loadEntry($directory, $source, $request['key'] ?? '');
            if ($source === 'dab') {
                if ($action !== 'save') { throw new RuntimeException('Identification applies only to FM.'); }
                if ($cancel()) { throw new RuntimeException('Cancelled.'); }
                // The library catalogue replaces a whole block. Make this explicit in the GUI.
                (new DabCatalogue($directory))->update($entry);
                return ['type' => 'saved', 'name' => $entry['channel'] . ' · ' . $entry['ensemble_name']];
            }
            if ($action === 'save') {
                $identity = $entry['identity'] ?? null;
                if (!is_array($identity)) { throw new RuntimeException('Identify this candidate before saving.'); }
                if ($cancel()) { throw new RuntimeException('Save cancelled.'); }
                (new StationCache($directory))->remember($entry['tune_hz'], $identity['pi'], $identity['name']);
                return ['type' => 'saved', 'name' => $identity['name']];
            }
            $config = self::fmConfig($config);
            $temporary = $directory . '/scans/fm-identify-' . bin2hex(random_bytes(12));
            $mask = umask(0077);
            try { if (!mkdir($temporary, 0700, true)) { throw new RuntimeException('Cannot create identification directory.'); } }
            finally { umask($mask); }
            $lock = fopen($directory . '/receiver.lock', 'c');
            if ($lock === false || !flock($lock, LOCK_EX | LOCK_NB)) {
                if (is_resource($lock)) { fclose($lock); }
                throw new RuntimeException('Receiver busy. Stop FM/DAB playback or other scans first.');
            }
            $capture = null;
            try {
                $hz = $entry['tune_hz'];
                // RDS auto-updates only this private staging cache, never real presets.
                $config['rds']['capture_seconds'] = min(30, $config['rds']['capture_seconds']);
                $config['rds']['detection_seconds'] = min(10, $config['rds']['detection_seconds'], $config['rds']['capture_seconds']);
                $capture = new RdsCapture();
                $result = $capture->capture(RdsCaptureOptions::fromConfig($hz, $config), $temporary, $cancel, null, $lock);
                $identity = $result->summary['station_identity'];
                if ($cancel() || $result->isCancelled()) { throw new RuntimeException('Identification cancelled; presets unchanged.'); }
                $item = self::recordIdentification($directory, $request['key'], $result->summary);
                return ['type' => 'identified', 'key' => $request['key'], 'item' => $item,
                    'message' => $identity === null ? 'No confirmed RDS name yet. Identification can be retried; no preset saved.'
                        : 'RDS received. Review the station information, then choose Save preset.'];
            } finally {
                // RdsCapture retains owned children until close confirms cleanup.
                try { $capture?->close(); }
                finally { flock($lock, LOCK_UN); fclose($lock); }
            }
        }
        if ($source === 'fm') {
            $config = self::fmConfig($config);
            $emit(['type'=>'progress', 'message'=>'Scanning FM spectrum…']);
            $csv = (new SpectrumScanner())->scan($config, $directory);
            if ($cancel()) { throw new RuntimeException('Scan cancelled; presets unchanged.'); }
            $bins = array_values(array_filter((new SpectrumParser())->parse($csv), static fn($bin): bool =>
                $bin['frequency_hz'] >= $config['scan']['start_mhz'] * 1000000
                && $bin['frequency_hz'] <= $config['scan']['end_mhz'] * 1000000));
            $entries = (new CandidateSelector())->select($bins, min(20, $config['scan']['limit']));
        } else {
            $settings = self::settings($directory, $config);
            $name = $request['location'] ?? '';
            $plans = array_column($settings['locations'], 'channels', 'name');
            if (!is_string($name) || !isset($plans[$name])) { throw new RuntimeException('Choose a reception location.'); }
            self::writeJson($directory . '/gui-scan-settings.json', ['dab_location'=>$name]);
            $entries = []; $problems = [];
            foreach ($plans[$name] as $index => $block) {
                if ($cancel()) { throw new RuntimeException('Scan cancelled; presets unchanged.'); }
                $emit(['type'=>'progress', 'message'=>sprintf('DAB+ %s · block %d of %d (up to 45 seconds per block)', $block, $index+1, count($plans[$name]))]);
                try {
                    $raw = (new EnsembleScanner())->scan($config, $directory, $block);
                    $entries[] = (new EnsembleParser())->parse($raw, $block);
                } catch (Radio\Dab\ScanCancelledException $error) { throw $error; }
                catch (Throwable $error) {
                    if (str_contains($error->getMessage(), 'receiver') || str_contains($error->getMessage(), 'owns')) { throw $error; }
                    $problems[] = $block . ': ' . $error->getMessage();
                }
            }
            if ($cancel()) { throw new RuntimeException('Scan cancelled; presets unchanged.'); }
            $warning = implode("\n", $problems);
        }
        return ['type'=>'results', 'items'=>self::preview($directory, $source, $entries),
            'warning'=>substr($warning ?? '', 0, 4000)];
    }
}
