<?php

declare(strict_types=1);

/** Composition of library discovery/storage APIs; injected HTTP supports offline tests. */
function runDiscoveryJob(string $directory, array $request,
    ?Symfony\Contracts\HttpClient\HttpClientInterface $http = null): array
{
    if (!is_array($request) || !in_array($request['source'] ?? null, ['internet', 'podcast'], true)
        || !in_array($request['action'] ?? null, ['search', 'save'], true)) {
        throw new InvalidArgumentException('Invalid discovery request.');
    }
    $configPath = $directory . '/config.json';
    if (!is_file($configPath) || filesize($configPath) > 1048576) { throw new RuntimeException('Missing or oversized config.json.'); }
    $config = json_decode(file_get_contents($configPath), true, 64, JSON_THROW_ON_ERROR);
    if (!is_array($config)) { throw new RuntimeException('Invalid configuration.'); }
    $source = $request['source'];
    $cancelled = false;
    pcntl_async_signals(true);
    foreach ([SIGINT, SIGTERM, SIGHUP] as $signal) {
        pcntl_signal($signal, static function () use (&$cancelled): void { $cancelled = true; });
    }
    $cancel = static function () use (&$cancelled): bool { return $cancelled; };
    $check = static function () use (&$cancelled): void {
        if ($cancelled) { throw new RuntimeException('Discovery cancelled.'); }
    };
    $client = $source === 'internet'
        ? new Radio\Internet\RadioBrowser(http: $http, servers: $config['internet']['directory_servers'] ?? [])
        : new Radio\Podcast\PodcastIndexDirectory(http: $http);
    if ($request['action'] === 'search') {
        $query = $request['query'] ?? null;
        if (!is_string($query) || trim($query) === '' || strlen($query) > 200
            || preg_match('//u', $query) !== 1 || preg_match('/[\p{Cc}\p{Cf}]/u', $query)) {
            throw new InvalidArgumentException('Enter a search name of at most 200 UTF-8 bytes.');
        }
        $rows = $source === 'internet' ? $client->search(name: $query, limit: 20) : $client->search($query, 20, $cancel);
        $items = [];
        foreach ($rows as $row) {
            $items[] = $source === 'internet'
                ? ['key' => $row['station_uuid'], 'name' => $row['name'],
                   'detail' => implode(' · ', array_filter([$row['country_code'], $row['codec'], $row['language']]))]
                : ['key' => $row->feedUrl, 'name' => $row->title, 'detail' => $row->publisher];
        }
        $check();
        $response = ['type' => 'results', 'items' => $items];
    } else {
        $key = $request['key'] ?? null;
        if (!is_string($key) || $key === '' || strlen($key) > 2048) { throw new InvalidArgumentException('Invalid result selection.'); }
        // Fetch authoritative details again; no arbitrary station data from QML is stored.
        if ($source === 'internet') {
            $station = $client->findByUuid($key);
            $check();
            $saved = (new Radio\Internet\StationCatalogue($directory))->remember($station);
            $name = $saved['name'];
        } else {
            $feed = (new Radio\Podcast\HttpFeedFetcher(http: $http))->fetch($key, $cancel);
            $check();
            $saved = (new Radio\Podcast\JsonSubscriptionRepository($directory))->subscribe($feed);
            $name = $saved->name;
        }
        $response = ['type' => 'saved', 'name' => $name];
    }
    return $response;
}
