<?php

declare(strict_types=1);

/** GUI display preference only; catalogue identities and playback selections stay intact. */
final class PresetOrder
{
    private const SOURCES = ['fm', 'dab', 'internet', 'podcast'];
    public function __construct(private readonly string $directory) {}

    private function read(): array
    {
        $path = $this->directory . '/gui-preset-order.json';
        if (!file_exists($path) && !is_link($path)) { return []; }
        if (is_link($path) || !is_file($path) || filesize($path) > 3145728) {
            throw new RuntimeException('Invalid or oversized GUI preset order file.');
        }
        $document = json_decode(file_get_contents($path), false, 16, JSON_THROW_ON_ERROR);
        if (!$document instanceof stdClass) { throw new RuntimeException('GUI preset order must be an object.'); }
        $orders = get_object_vars($document);
        foreach ($orders as $source => $ids) {
            if (!in_array($source, self::SOURCES, true) || !is_array($ids) || count($ids) > 1000) {
                throw new RuntimeException('Invalid GUI preset order source.');
            }
            $seen = [];
            foreach ($ids as $id) {
                if (!is_string($id) || $id === '' || strlen($id) > 512 || isset($seen[$id])) {
                    throw new RuntimeException('Invalid or duplicate GUI preset order identity.');
                }
                $seen[$id] = true;
            }
        }
        return $orders;
    }

    private static function sort(array $rows, array $ids): array
    {
        $remaining = array_column($rows, null, 'id');
        $result = [];
        foreach ($ids as $id) {
            if (isset($remaining[$id])) { $result[] = $remaining[$id]; unset($remaining[$id]); }
        }
        // New entries follow the existing preferred entries in catalogue order.
        return array_merge($result, array_values($remaining));
    }

    public function apply(string $source, array $rows, bool $strict = false): array
    {
        try { return self::sort($rows, $this->read()[$source] ?? []); }
        catch (Throwable $error) {
            if ($strict) { throw $error; }
            // A damaged display preference never disables listening or overwrites itself.
            return $rows;
        }
    }

    public static function revision(array $rows): string
    {
        return hash('sha256', json_encode(array_column($rows, 'id'), JSON_THROW_ON_ERROR));
    }

    public function move(string $source, array $rows, string $key, int $direction, string $revision): array
    {
        if (!in_array($source, self::SOURCES, true) || !in_array($direction, [-1, 1], true)) {
            throw new RuntimeException('Invalid preset move.');
        }
        $lockPath = $this->directory . '/gui-preset-order.lock';
        if (is_link($lockPath)) { throw new RuntimeException('Invalid preset order lock.'); }
        $mask = umask(0077);
        try { $lock = fopen($lockPath, 'c'); } finally { umask($mask); }
        if ($lock === false) { throw new RuntimeException('Cannot open preset order lock.'); }
        try {
            if (!flock($lock, LOCK_EX | LOCK_NB)) { throw new RuntimeException('Preset order is busy. Try again.'); }
            $orders = $this->read();
            $rows = self::sort($rows, $orders[$source] ?? []);
            if (!hash_equals(self::revision($rows), $revision)) {
                throw new RuntimeException('Presets changed elsewhere. Reopen Manage presets.');
            }
            $ids = array_column($rows, 'id');
            $index = array_search($key, $ids, true);
            if ($index === false) { throw new RuntimeException('Preset is no longer available.'); }
            $target = $index + $direction;
            if ($target < 0 || $target >= count($rows)) { throw new RuntimeException('Preset is already at the end of the list.'); }
            [$rows[$index], $rows[$target]] = [$rows[$target], $rows[$index]];
            $orders[$source] = array_column($rows, 'id');
            $bytes = json_encode((object) $orders, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE) . "\n";
            $path = $this->directory . '/gui-preset-order.json';
            $temporary = $path . '.tmp-' . bin2hex(random_bytes(6));
            $mask = umask(0077);
            try {
                $file = fopen($temporary, 'xb');
                if ($file === false) { throw new RuntimeException('Cannot create preset order file.'); }
                try {
                    if (fwrite($file, $bytes) !== strlen($bytes) || !fflush($file)) { throw new RuntimeException('Cannot write preset order.'); }
                } finally { fclose($file); }
                if (!rename($temporary, $path)) { throw new RuntimeException('Cannot replace preset order.'); }
            } finally {
                if (is_file($temporary)) { unlink($temporary); }
                umask($mask);
            }
            return $rows;
        } finally { flock($lock, LOCK_UN); fclose($lock); }
    }
}
