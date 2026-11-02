<?php
/** Shared failure budget for native PhotoShow login. */
class PhotoShowLoginLimited extends RuntimeException
{
    public function __construct(public readonly int $retryAfter) { parent::__construct('Login limited'); }
}

// One bucket per IPv4 address / IPv6 /64. Forwarded headers are never trusted
// here: only Nginx's REMOTE_ADDR, with explicitly configured trusted proxies.
function photoshow_login_bucket(string $address): string
{
    $packed = @inet_pton($address);
    if ($packed === false) return hash('sha256', 'unknown');
    if (strlen($packed) === 16 && substr($packed, 0, 12) === str_repeat("\0", 10)."\xff\xff") {
        $packed = substr($packed, 12);
    }
    if (strlen($packed) === 16) $packed = substr($packed, 0, 8);
    return hash('sha256', $packed);
}

class PhotoShowLoginGate
{
    public function __construct(private string $directory, private int $capacity = 5, private int $refillSeconds = 30) {}

    private function change(string $address, bool $reserve, ?float $now): void
    {
        $now ??= microtime(true);
        $file = $this->directory.'/'.photoshow_login_bucket($address).'.json';
        $handle = @fopen($file, 'c+');
        if ($handle === false) throw new RuntimeException('Login state unavailable');
        try {
            // The lock covers only bounded local IO, never password hashing.
            if (!flock($handle, LOCK_EX)) throw new RuntimeException('Cannot lock login state');
            chmod($file, 0600);
            $raw = stream_get_contents($handle, 1024);
            $state = $raw === '' ? ['tokens' => $this->capacity, 'time' => $now] : json_decode($raw, true);
            if (!is_array($state) || !isset($state['tokens'], $state['time'])
                || !is_numeric($state['tokens']) || !is_numeric($state['time'])) {
                throw new RuntimeException('Invalid login state');
            }
            $tokens = min($this->capacity, max(0, (float)$state['tokens']) + max(0, $now - $state['time']) / $this->refillSeconds);
            if ($reserve && $tokens < 1) throw new PhotoShowLoginLimited((int)ceil((1 - $tokens) * $this->refillSeconds));
            $state = ['tokens' => min($this->capacity, $tokens + ($reserve ? -1 : 1)), 'time' => max($now, $state['time'])];
            $data = json_encode($state, JSON_THROW_ON_ERROR);
            rewind($handle);
            if (!ftruncate($handle, 0) || fwrite($handle, $data) !== strlen($data) || !fflush($handle)) {
                throw new RuntimeException('Cannot persist login state');
            }
        } finally {
            flock($handle, LOCK_UN);
            fclose($handle);
        }
    }

    public function reserve(string $address, ?float $now = null): void { $this->change($address, true, $now); }
    public function refund(string $address, ?float $now = null): void { $this->change($address, false, $now); }
}

