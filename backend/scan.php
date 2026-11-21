<?php

declare(strict_types=1);
ini_set('display_errors', 'stderr');
try {
    require dirname(__DIR__) . '/vendor/autoload.php';
    require __DIR__ . '/ScanOperations.php';
    // Own process group: emergency cleanup must never signal the GUI's group.
    if (!function_exists('posix_setsid') || ($sessionId = posix_setsid()) === false || $sessionId < 0) { throw new RuntimeException('Cannot isolate scan process group.'); }
    $directory = $argv[1] ?? '';
    if (!str_starts_with($directory, '/') || !is_dir($directory)) { throw new RuntimeException('Existing absolute data directory required.'); }
    $bytes = stream_get_contents(STDIN, 8193);
    if ($bytes === false || strlen($bytes) > 8192) { throw new RuntimeException('Oversized scan request.'); }
    $request = json_decode($bytes, true, 16, JSON_THROW_ON_ERROR);
    if (!is_array($request)) { throw new RuntimeException('Invalid scan request.'); }
    $config = ScanOperations::readJson($directory . '/config.json');
    $cancelled = false;
    pcntl_async_signals(true);
    foreach ([SIGINT, SIGTERM, SIGHUP] as $signal) {
        pcntl_signal($signal, static function () use (&$cancelled): void { $cancelled = true; });
    }
    $cancel = static function () use (&$cancelled): bool { return $cancelled; };
    $emit = static function (array $message): void {
        $bytes = json_encode($message, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE) . "\n";
        if (strlen($bytes) > 262144) { throw new RuntimeException('Scan response exceeded its limit.'); }
        echo $bytes;
        flush();
    };
    $response = ScanOperations::run($directory, $config, $request, $emit, $cancel);
    if ($cancelled) { throw new RuntimeException('Cancelled. Refresh presets before retrying a save.'); }
    $emit($response);
} catch (Throwable $error) {
    echo json_encode(['type'=>'error', 'message'=>substr($error->getMessage(),0,2000)], JSON_INVALID_UTF8_SUBSTITUTE), "\n";
    exit(1);
}
