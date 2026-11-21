<?php

declare(strict_types=1);

require_once __DIR__ . '/PresetOrder.php';

use Radio\Dab\StationCatalogue as DabCatalogue;
use Radio\Fm\StationCache;
use Radio\Internet\StationCatalogue as InternetCatalogue;

/** Read existing library catalogues, exposing stable selections to the GUI. */
final class SavedRadioStations
{
    public static function load(string $directory): array
    {
        $stations = [];
        $errors = [];
        foreach (['fm' => 'stations.json', 'dab' => 'dab-stations.json', 'internet' => 'internet-stations.json'] as $source => $filename) {
            try {
                $path = $directory . '/' . $filename;
                if (is_file($path) && filesize($path) > 2097152) {
                    throw new RuntimeException('Saved catalogue exceeds 2 MiB.');
                }
                $rows = match ($source) {
                    'fm' => (new StationCache($directory))->all(),
                    'dab' => (new DabCatalogue($directory))->all(),
                    'internet' => (new InternetCatalogue($directory))->all(),
                };
                if (count($rows) > 1000) {
                    throw new RuntimeException('At most 1000 saved stations per source are supported.');
                }
                $entries = [];
                foreach ($rows as $station) {
                    // DAB packet/data services are not audio selections.
                    if ($source === 'dab' && $station['audio_components'] === []) { continue; }
                    [$id, $selection, $detail] = match ($source) {
                        'fm' => [
                            'fm/' . $station['frequency_hz'],
                            number_format($station['frequency_hz'] / 1000000, 6, '.', ''),
                            number_format($station['frequency_hz'] / 1000000, 2, '.', '') . ' MHz',
                        ],
                        'dab' => [
                            'dab/' . $station['station_id'],
                            $station['station_id'],
                            $station['channel'] . ' · ' . ($station['ensemble_name'] ?? ''),
                        ],
                        // Preserve the internet UUID wire ID for the first GUI milestone.
                        'internet' => [$station['station_uuid'], $station['station_uuid'], 'Internet'],
                    };
                    if (isset($entries[$id]) || strlen($id) > 512 || strlen($station['name']) > 2000 || strlen($detail) > 2000) {
                        throw new RuntimeException('Duplicate or oversized station entry.');
                    }
                    $entries[$id] = ['id' => $id, 'source' => $source, 'name' => $station['name'],
                        'detail' => $detail, 'selection' => $selection];
                }
                array_push($stations, ...(new PresetOrder($directory))->apply($source, array_values($entries)));
            } catch (Throwable $error) {
                // An unreadable FM/DAB catalogue must not disable another source.
                $errors[$source] = substr($error->getMessage(), 0, 1000);
            }
        }
        return ['stations' => $stations, 'errors' => $errors];
    }
}
