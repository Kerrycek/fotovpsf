<?php
// Loaded by the immutable policy before Piwigo's user functions are declared.
const VPSFREE_ARGON_OPTIONS = ['memory_cost' => 65536, 'time_cost' => 3, 'threads' => 1];

function pwg_password_hash($password)
{
    return password_hash($password, PASSWORD_ARGON2ID, VPSFREE_ARGON_OPTIONS);
}

function pwg_password_verify($password, $hash, $user_id = null)
{
    global $conf;
    if (!is_string($password) || !is_string($hash)) return false;
    if (password_get_info($hash)['algoName'] !== 'unknown') {
        $valid = password_verify($password, $hash);
    } elseif (str_starts_with($hash, '$P$') || str_starts_with($hash, '$H$')) {
        require_once PHPWG_ROOT_PATH.'include/passwordhash.class.php';
        $valid = (new PasswordHash(13, true))->CheckPassword($password, $hash);
    } elseif (preg_match('/^[a-f0-9]{32}$/', $hash)) {
        // Retain Piwigo's legacy migration path; never create new MD5 hashes.
        $valid = hash_equals($hash, md5($password));
    } else {
        $valid = false;
    }
    if ($valid && $user_id !== null && empty($conf['external_authentification'])
        && password_needs_rehash($hash, PASSWORD_ARGON2ID, VPSFREE_ARGON_OPTIONS)) {
        // Compare the old hash too, so a concurrent password reset wins.
        single_update(USERS_TABLE,
            [$conf['user_fields']['password'] => pwg_password_hash($password)],
            [$conf['user_fields']['id'] => (int)$user_id, $conf['user_fields']['password'] => $hash]);
    }
    return $valid;
}

class VpsfreeLoginLimited extends RuntimeException
{
    public function __construct(public readonly int $retryAfter) { parent::__construct('Login limited'); }
}

// One bucket per IPv4 address / IPv6 /64. Forwarded headers are never trusted
// here: only Nginx's REMOTE_ADDR, with explicitly configured trusted proxies.
function vpsfree_login_bucket(string $address): string
{
    $packed = @inet_pton($address);
    if ($packed === false) return hash('sha256', 'unknown');
    if (strlen($packed) === 16 && substr($packed, 0, 12) === str_repeat("\0", 10)."\xff\xff") {
        $packed = substr($packed, 12);
    }
    if (strlen($packed) === 16) $packed = substr($packed, 0, 8);
    return hash('sha256', $packed);
}

class VpsfreeLoginGate
{
    public function __construct(private string $directory, private int $capacity = 5, private int $refillSeconds = 30) {}

    private function change(string $address, bool $reserve, ?float $now): void
    {
        $now ??= microtime(true);
        $file = $this->directory.'/'.vpsfree_login_bucket($address).'.json';
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
            if ($reserve && $tokens < 1) throw new VpsfreeLoginLimited((int)ceil((1 - $tokens) * $this->refillSeconds));
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

function vpsfree_login_response(int $status, int $retry): never
{
    http_response_code($status);
    header('Retry-After: '.$retry);
    header('Cache-Control: no-store');
    $message = $status === 429 ? 'Too many login attempts. Try again later.' : 'Login is temporarily unavailable.';
    global $service;
    if (defined('IN_WS')) {
        if (isset($service)) {
            $service->sendResponse(new PwgError($status, $message));
        } else {
            // Header API keys authenticate before the WS encoder exists.
            header('Content-Type: application/json; charset=utf-8');
            echo json_encode(['stat' => 'fail', 'err' => $status, 'message' => $message]);
        }
    } else {
        header('Content-Type: text/html; charset=utf-8');
        $title = $status === 429 ? 'Chvilku prosím počkejte' : 'Přihlášení je dočasně nedostupné';
        $link = htmlspecialchars(get_root_url().'identification.php', ENT_QUOTES, 'UTF-8');
        echo '<!doctype html><html lang="cs"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            .'<title>'.$title.' | vpsFree.cz</title><style>body{margin:0;background:#1f3959;color:#edf3fa;font:16px/1.6 system-ui;display:grid;min-height:100vh;place-items:center}main{margin:24px;padding:32px;max-width:440px;background:#16273f;border-radius:12px}h1{color:#f6914b;font-size:24px}a{color:#f6914b}:focus-visible{outline:3px solid #f6914b;outline-offset:4px}</style>'
            .'<main><h1>'.$title.'</h1>'.($status === 429 ? '<p>Příliš mnoho chybných pokusů o přihlášení z této sítě.</p>' : '')
            .'<p>Zkuste přihlášení znovu přibližně za '.$retry.' s.</p><a href="'.$link.'">Zpět na přihlášení</a></main></html>';
    }
    exit;
}

function vpsfree_limited_authentication(callable $authenticate): bool
{
    global $conf;
    $address = $_SERVER['REMOTE_ADDR'] ?? 'unknown';
    $gate = new VpsfreeLoginGate($conf['vpsfree_login_throttle_directory']);
    try {
        $gate->reserve($address);
    } catch (VpsfreeLoginLimited $limited) {
        vpsfree_login_response(429, $limited->retryAfter);
    } catch (RuntimeException $error) {
        error_log('Gallery login throttle state unavailable');
        vpsfree_login_response(503, 30);
    }
    $success = false;
    try {
        $success = (bool)$authenticate();
        return $success;
    } finally {
        // Successful authentication refunds only its own reservation, never
        // clears earlier failures. Parallel requests cannot overspend a bucket.
        if ($success) {
            try { $gate->refund($address); }
            catch (RuntimeException $error) { error_log('Gallery login throttle refund unavailable'); }
        }
    }
}

function try_log_user($username, $password, $remember_me)
{
    return vpsfree_limited_authentication(fn() => is_string($username) && is_string($password)
        && vpsfree_original_try_log_user($username, $password, $remember_me));
}

function auth_key_login($auth_key, $connection_by_header = false)
{
    return vpsfree_limited_authentication(fn() => is_string($auth_key)
        && vpsfree_original_auth_key_login($auth_key, $connection_by_header));
}
