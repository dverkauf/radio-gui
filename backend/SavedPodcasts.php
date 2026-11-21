<?php

declare(strict_types=1);

use Radio\Podcast\EpisodeSelectionResolver;
use Radio\Podcast\JsonSubscriptionRepository;

/** Startup snapshot and bounded episode pages. No feed fetching or media I/O. */
final class SavedPodcasts
{
    public const PAGE_SIZE = 40;
    private array $subscriptions = [];
    private ?string $error = null;

    public function __construct(string $directory)
    {
        // Preserve read-only empty startup: the repository's lock is unnecessary
        // until a saved catalogue exists. Existing stores retain library locking.
        if (!file_exists($directory . '/podcasts.json')) { return; }
        try {
            $rows = (new JsonSubscriptionRepository($directory))->all();
            if (count($rows) > 1000) { throw new RuntimeException('At most 1000 saved podcasts are supported.'); }
            foreach ($rows as $row) { $this->subscriptions[$row->id()] = $row; }
        } catch (Throwable $error) {
            $this->subscriptions = [];
            $this->error = substr($error->getMessage(), 0, 1000);
        }
    }

    public function error(): ?string { return $this->error; }

    public function summaries(): array
    {
        return array_map(static fn($s): array => [
            'id' => $s->id(), 'name' => self::label($s->name),
            'detail' => count($s->feed->episodes) . ' saved episodes',
        ], array_values($this->subscriptions));
    }

    public function page(string $feed, int $page): array
    {
        $subscription = $this->subscriptions[$feed] ?? throw new InvalidArgumentException('Unknown saved podcast.');
        $episodes = $subscription->feed->episodes;
        $total = count($episodes);
        if ($page < 0 || $page > max(0, (int) ceil($total / self::PAGE_SIZE) - 1)) {
            throw new InvalidArgumentException('Invalid episode page.');
        }
        return ['feed' => $feed, 'page' => $page, 'total' => $total, 'page_size' => self::PAGE_SIZE,
            'items' => array_map(static fn($episode): array => [
                'id' => 'podcast/' . $feed . '/' . $episode->keyForFeed($feed),
                'source' => 'podcast', 'name' => self::label($episode->title),
                'detail' => $episode->publishedAt?->format('Y-m-d') ?? '',
            ], array_slice($episodes, $page * self::PAGE_SIZE, self::PAGE_SIZE))];
    }

    public function selection(string $id): array
    {
        if (preg_match('~\Apodcast/([0-9a-f]{64})/([0-9a-f]{64})\z~', $id, $match) !== 1) {
            throw new InvalidArgumentException('Choose a saved podcast episode.');
        }
        try {
            $selected = (new EpisodeSelectionResolver())->resolve(array_values($this->subscriptions), $match[1] . '/' . $match[2]);
        } catch (Throwable $error) {
            throw new InvalidArgumentException('Unknown saved podcast episode.', 0, $error);
        }
        return ['source' => 'podcast', 'selection' => $selected->selection()];
    }

    private static function label(string $text): string
    {
        // Display-only truncation. IDs and library selections always remain full.
        preg_match('/\A.{0,128}/us', $text, $match);
        return ($match[0] ?? '') . (strlen($match[0] ?? '') < strlen($text) ? '…' : '');
    }
}
