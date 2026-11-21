<?php

declare(strict_types=1);
ini_set('display_errors','stderr');
try {
    require dirname(__DIR__).'/vendor/autoload.php';
    require __DIR__.'/SavedRadioStations.php';
    require __DIR__.'/SavedPodcasts.php';
    $directory=$argv[1]??'';
    if (!str_starts_with($directory,'/') || !is_dir($directory)) { throw new RuntimeException('Existing data directory required.'); }
    $bytes=stream_get_contents(STDIN,8193);
    if ($bytes===false || strlen($bytes)>8192) { throw new RuntimeException('Oversized preset request.'); }
    $request=json_decode($bytes,true,16,JSON_THROW_ON_ERROR);
    $source=$request['source']??'';$action=$request['action']??'';
    if (!in_array($source,['fm','dab','internet','podcast'],true) || !in_array($action,['list','delete'],true)) { throw new RuntimeException('Invalid preset request.'); }
    if ($source==='podcast') {
        $podcasts=new SavedPodcasts($directory);
        if ($podcasts->error()!==null) { throw new RuntimeException($podcasts->error()); }
        $rows=$podcasts->summaries();
    } else {
        $catalogue=SavedRadioStations::load($directory);
        if (isset($catalogue['errors'][$source])) { throw new RuntimeException($catalogue['errors'][$source]); }
        $rows=array_values(array_filter($catalogue['stations'],static fn($row):bool=>$row['source']===$source));
    }
    if ($action==='list') {
        $response=['type'=>'presets','items'=>array_map(static fn($row):array=>['key'=>$row['id'],'name'=>$row['name'],'detail'=>$row['detail']??''], $rows)];
    } else {
        $key=$request['key']??null;
        $allowed=array_column($rows,null,'id');
        if (!is_string($key) || !isset($allowed[$key])) { throw new RuntimeException('Preset is no longer available. Reopen Manage presets.'); }
        switch($source) {
            case 'fm': (new Radio\Fm\StationCache($directory))->forget((int)substr($key,3));break;
            case 'dab':
                if (!method_exists(Radio\Dab\StationCatalogue::class,'forget')) { throw new RuntimeException('Update radio-lib before deleting DAB presets.'); }
                (new Radio\Dab\StationCatalogue($directory))->forget(substr($key,4));break;
            case 'internet':
                if (!method_exists(Radio\Internet\StationCatalogue::class,'forget')) { throw new RuntimeException('Update radio-lib before deleting Internet presets.'); }
                (new Radio\Internet\StationCatalogue($directory))->forget($key);break;
            case 'podcast':
                if (($request['remove_progress']??false)===true) {
                    $progress=new Radio\Podcast\JsonProgressRepository($directory);
                    if (!method_exists($progress,'removeFeed')) { throw new RuntimeException('Update radio-lib before removing podcast progress.'); }
                    $progress->removeFeed($key);
                }
                (new Radio\Podcast\JsonSubscriptionRepository($directory))->unsubscribe($key);
                break;
        }
        $response=['type'=>'deleted','key'=>$key,'name'=>$allowed[$key]['name']];
    }
    echo json_encode($response,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_INVALID_UTF8_SUBSTITUTE),"\n";
} catch(Throwable $error) {
    echo json_encode(['type'=>'error','message'=>substr($error->getMessage(),0,1000)],JSON_INVALID_UTF8_SUBSTITUTE),"\n";exit(1);
}
