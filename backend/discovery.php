<?php

declare(strict_types=1);

// One bounded job per owned process. No receiver or playback operations.
ini_set('display_errors', 'stderr');
try {
    require dirname(__DIR__) . '/vendor/autoload.php';
    $directory = $argv[1] ?? '';
    if (!str_starts_with($directory, '/') || !is_dir($directory)) {
        throw new RuntimeException('An existing absolute configuration directory is required.');
    }
    $bytes = stream_get_contents(STDIN, 8193);
    if ($bytes === false || strlen($bytes) > 8192) { throw new InvalidArgumentException('Discovery request is too large.'); }
    $request = json_decode($bytes, true, 16, JSON_THROW_ON_ERROR);
    if (!is_array($request) || !in_array($request['source'] ?? null, ['internet', 'podcast'], true)
        || !in_array($request['action'] ?? null, ['search', 'save'], true)) {
        throw new InvalidArgumentException('Invalid discovery request.');
    }
    require __DIR__ . '/DiscoveryOperations.php';
    $response = runDiscoveryJob($directory, $request);
    echo json_encode($response, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE), "\n";
} catch (Throwable $error) {
    echo json_encode(['type' => 'error', 'message' => substr($error->getMessage(), 0, 1000)], JSON_INVALID_UTF8_SUBSTITUTE), "\n";
    exit(1);
}
