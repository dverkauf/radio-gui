<?php

declare(strict_types=1);
ini_set('display_errors','stderr');
try {
    require dirname(__DIR__).'/vendor/autoload.php';
    require __DIR__.'/ScanOperations.php';
    require __DIR__.'/ReceptionLocations.php';
    $directory=$argv[1]??'';
    if (!str_starts_with($directory,'/')||!is_dir($directory)) { throw new RuntimeException('Existing data directory required.'); }
    $bytes=stream_get_contents(STDIN,8193);
    if ($bytes===false||strlen($bytes)>8192) { throw new RuntimeException('Oversized location request.'); }
    $request=json_decode($bytes,true,16,JSON_THROW_ON_ERROR);
    if (!is_array($request)) { throw new RuntimeException('Invalid location request.'); }
    echo json_encode((new ReceptionLocations($directory))->run($request),JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_INVALID_UTF8_SUBSTITUTE),"\n";
} catch(Throwable $error) {
    echo json_encode(['type'=>'error','message'=>substr($error->getMessage(),0,1000)],JSON_INVALID_UTF8_SUBSTITUTE),"\n";exit(1);
}
