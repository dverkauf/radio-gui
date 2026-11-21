<?php

declare(strict_types=1);

/** Config editing only; DAB block validation remains in radio-lib. */
final class ReceptionLocations
{
    private const FULL = '__full_band__';
    public function __construct(private readonly string $directory) {}

    private function bytes(string $path, int $limit, bool $optional = false): string
    {
        if ($optional && !file_exists($path) && !is_link($path)) { return ''; }
        if (is_link($path) || !is_file($path) || filesize($path) > $limit) { throw new RuntimeException('Missing, linked or oversized location settings.'); }
        $bytes = file_get_contents($path);
        if ($bytes === false) { throw new RuntimeException('Cannot read location settings.'); }
        return $bytes;
    }

    private function object(string $bytes): stdClass
    {
        if ($bytes === '') { return new stdClass(); }
        $value = json_decode($bytes, false, 64, JSON_THROW_ON_ERROR);
        if (!($value instanceof stdClass)) { throw new RuntimeException('Settings must contain a JSON object.'); }
        return $value;
    }

    private function atomic(string $path, string $bytes): void
    {
        $temporary = $path . '.tmp-' . bin2hex(random_bytes(6));
        $mask = umask(0077);
        try {
            $file = fopen($temporary, 'xb');
            if ($file === false) { throw new RuntimeException('Cannot create settings temporary file.'); }
            try { if (fwrite($file, $bytes) !== strlen($bytes) || !fflush($file)) { throw new RuntimeException('Cannot write settings.'); } }
            finally { fclose($file); }
            if (!rename($temporary, $path)) { throw new RuntimeException('Cannot replace location settings.'); }
        } finally {
            if (is_file($temporary)) { unlink($temporary); }
            umask($mask);
        }
    }

    private function snapshot(): array
    {
        $config = $this->bytes($this->directory . '/config.json', 1048576);
        $settings = $this->bytes($this->directory . '/gui-scan-settings.json', 4096, true);
        $document = $this->object($config);
        $preferences = $this->object($settings);
        if (isset($document->dab) && !($document->dab instanceof stdClass)) { throw new RuntimeException('dab settings must be an object.'); }
        if (isset($document->dab->locations) && !($document->dab->locations instanceof stdClass)) { throw new RuntimeException('dab.locations must be an object.'); }
        $array = json_decode($config, true, 64, JSON_THROW_ON_ERROR);
        $plans = ScanOperations::locations($array);
        $selected = $preferences->dab_location ?? self::FULL;
        if (!is_string($selected) || !in_array($selected, array_column($plans, 'name'), true)) { $selected = self::FULL; }
        return [$config, $settings, $document, $preferences, $plans, $selected];
    }

    private function response(array $state, string $message): array
    {
        [$config, $settings, , , $plans, $selected] = $state;
        $items = [];
        foreach ($plans as $plan) {
            if ($plan['name'] === self::FULL) { continue; }
            $items[] = ['key'=>$plan['name'], 'name'=>$plan['name'], 'channels'=>$plan['channels'], 'detail'=>implode(', ', $plan['channels'])];
        }
        return ['type'=>'locations','items'=>$items,'selected'=>$selected,
            'revision'=>hash('sha256',$config . "\0" . $settings), 'message'=>$message];
    }

    public function run(array $request): array
    {
        $action = $request['action'] ?? '';
        if (!in_array($action,['list','save','delete','select'],true)) { throw new RuntimeException('Invalid reception location action.'); }
        // Reads create no files. Mutations use a separate stable configuration lock.
        if ($action === 'list') { return $this->response($this->snapshot(), 'Select a saved location to edit, or choose New location.'); }
        $mask = umask(0077);
        try { $lock = fopen($this->directory . '/config.json.locations.lock','c'); }
        finally { umask($mask); }
        if ($lock === false) { throw new RuntimeException('Cannot open location settings lock.'); }
        try {
            if (!flock($lock,LOCK_EX|LOCK_NB)) { throw new RuntimeException('Location settings are busy; try again.'); }
            $state = $this->snapshot();
            [$bytes,$settings,$document,$preferences,$plans,$selected] = $state;
            $revision = $this->response($state, '')['revision'];
            if (($request['revision']??'') !== $revision) { throw new RuntimeException('Settings changed elsewhere. Reopen Reception locations before editing.'); }
            $name = $request['name'] ?? '';
            if (!is_string($name)) { throw new RuntimeException('Invalid location name.'); }
            $name = trim($name);
            $current = $document->dab->locations ?? new stdClass();
            $configChanged = false;
            if ($action === 'save') {
                if ($name === '' || strlen($name)>100 || preg_match('//u',$name)!==1
                    || preg_match('/[\p{Cc}\p{Cf}]/u',$name) || ctype_digit($name)
                    || strcasecmp($name,self::FULL)===0) { throw new RuntimeException('Use a location name of at most 100 UTF-8 bytes, without control characters.'); }
                $original = $request['original'] ?? null;
                if ($original !== null && (!is_string($original) || $original !== $name || !property_exists($current,$name))) {
                    throw new RuntimeException('Original location changed or disappeared. Reopen the editor.');
                }
                foreach (array_keys(get_object_vars($current)) as $existing) {
                    if (preg_match('/\A'.preg_quote((string)$existing,'/').'\z/iu',$name) && ($original === null || $existing !== $original)) {
                        throw new RuntimeException('Another reception location already has that name.');
                    }
                }
                $channels = $request['channels'] ?? null;
                if (!is_array($channels) || !array_is_list($channels) || count($channels)>38) { throw new RuntimeException('Choose one or more DAB blocks.'); }
                $checked = (new Radio\Dab\LocationChannels())->resolve(['dab'=>['locations'=>[$name=>$channels]]],$name);
                $current->{$name} = $checked;
                if (count(get_object_vars($current))>50) { throw new RuntimeException('At most 50 reception locations are supported.'); }
                $document->dab ??= new stdClass();
                $document->dab->locations = $current;
                $preferences->dab_location = $name;
                $configChanged = true;
                $message = 'Saved location: ' . $name . '. It is now selected for scanning.';
            } elseif ($action === 'delete') {
                if (!property_exists($current,$name)) { throw new RuntimeException('Choose an existing named location.'); }
                unset($current->{$name});
                $document->dab->locations = $current;
                if ($selected === $name) { $preferences->dab_location = self::FULL; }
                $configChanged = true;
                $message = 'Deleted location plan only; saved stations are unchanged.';
            } else {
                if (!in_array($name,array_column($plans,'name'),true)) { throw new RuntimeException('Unknown reception location.'); }
                $preferences->dab_location = $name;
                $message = 'Reception location selected.';
            }
            if ($configChanged) {
                // Retain one exact private pre-edit config copy; preserve unrelated fields/types.
                $encoded = json_encode($document,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT)."\n";
                ScanOperations::locations(json_decode($encoded,true,64,JSON_THROW_ON_ERROR));
                $this->atomic($this->directory.'/config.json.before-locations',$bytes);
                $this->atomic($this->directory.'/config.json',$encoded);
            }
            try { $this->atomic($this->directory.'/gui-scan-settings.json', json_encode($preferences,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE)."\n"); }
            catch(Throwable $error) { throw new RuntimeException('Location configuration may be saved, but selection could not be updated. Reopen the editor.',0,$error); }
            return $this->response($this->snapshot(),$message);
        } finally { flock($lock,LOCK_UN);fclose($lock); }
    }
}
