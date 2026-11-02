<?php
/** PHP 8.5 compatibility and request boundaries for the original GPLv3 PhotoShow. */
final class Modern
{
    public static function bootstrap(): void
    {
        require_once dirname(__DIR__).'/security/login-gate.php';
        $path = getenv('PHOTOSHOW_BASE_PATH') ?: '/';
        if (!preg_match('#^/(?:[a-zA-Z0-9_-]+/)*$#D', $path)) throw new RuntimeException('Invalid cookie path');
        session_set_cookie_params(['path'=>$path, 'secure'=>str_starts_with(getenv('PHOTOSHOW_PUBLIC_URL') ?: '', 'https://'), 'httponly'=>true, 'samesite'=>'Lax']);
        session_name('photoshow85');
        session_start();
        $_SESSION['csrf'] ??= bin2hex(random_bytes(32));
        header('X-Content-Type-Options: nosniff');
        header('Referrer-Policy: same-origin');
        header("Content-Security-Policy: frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'");
        header('Cache-Control: private, no-store');
        $action = $_GET['t'] ?? '';
        $adminAction = $_GET['a'] ?? '';
        if (!is_string($action) || !is_string($adminAction)) {
            http_response_code(400); exit('Neplatný požadavek.');
        }
        // These historical GET links change state and now require a CSRF-protected POST.
        $mutation = in_array($action, ['Rig','CTk','Pub','Pri','Logout','Log','Com'], true)
            || in_array($adminAction, ['Upl','Mov','Del','GDe','GEd','AEd','ANw','AGA','AGR','ADe','CDe','GAl','GC','AAc','DTk'], true);
        $post = ($_SERVER['REQUEST_METHOD'] ?? 'GET') === 'POST';
        if ($mutation && !$post) { http_response_code(405); exit('Použijte tlačítko v galerii.'); }
        if ($post) {
            $token = $_SERVER['HTTP_X_PHOTOSHOW_CSRF'] ?? $_POST['csrf'] ?? '';
            if (!is_string($token) || !hash_equals($_SESSION['csrf'], $token)) {
                http_response_code(403); exit('Platnost formuláře vypršela. Obnovte stránku.');
            }
        }
        if ($post) {
            self::$writeLock = fopen('/var/lib/photoshow-preview/request.lock', 'c');
            if (!self::$writeLock || !flock(self::$writeLock, LOCK_EX)) {
                http_response_code(503); header('Retry-After: 3'); exit('Zkuste požadavek za chvíli.');
            }
            chmod('/var/lib/photoshow-preview/request.lock', 0600);
        }
        ob_start(static function(string $body): string {
            foreach (headers_list() as $header) {
                if (stripos($header, 'Content-Type:') === 0 && stripos($header, 'text/html') === false) return $body;
            }
            $token = htmlspecialchars($_SESSION['csrf'] ?? '', ENT_QUOTES, 'UTF-8');
            $body = preg_replace('/(<form\b[^>]*>)/i', '$1<input type="hidden" name="csrf" value="'.$token.'">', $body);
            return str_replace('</head>', '<meta name="photoshow-csrf" content="'.$token.'"></head>', $body);
        });
    }

    private static $writeLock;

    /** Serialize state mutations, then replace XML atomically for concurrent readers. */
    public static function saveXml(SimpleXMLElement $xml, string $target): bool
    {
        $temporary = tempnam(dirname($target), '.photoshow-xml-');
        if ($temporary === false) throw new RuntimeException('XML storage unavailable');
        try {
            $bytes = $xml->asXML();
            if ($bytes === false || file_put_contents($temporary, $bytes, LOCK_EX) !== strlen($bytes)) throw new RuntimeException('XML save failed');
            chmod($temporary, 0600);
            if (!rename($temporary, $target)) throw new RuntimeException('XML replacement failed');
            return true;
        } finally { if (file_exists($temporary)) unlink($temporary); }
    }

    public static function loginGate(): PhotoShowLoginGate
    {
        $directory = '/var/lib/photoshow-preview/auth-throttle';
        if (!is_dir($directory) && !mkdir($directory, 0700, true) && !is_dir($directory)) throw new RuntimeException('Login state unavailable');
        return new PhotoShowLoginGate($directory);
    }

    public static function authorizeActions(): void
    {
        $type = $_GET['t'] ?? '';
        $action = $_GET['a'] ?? '';
        $panel = $_GET['j'] ?? '';
        $adminOnly = in_array($type, ['Adm','Rig','CTk','Pub','Pri'], true)
            || in_array($panel, ['Acc','Jud'], true)
            || in_array($action, ['Mov','Del','GDe','GEd','GC','AAc','AGA','AGR','ADe','CDe','GAl','DTk','Set','Acc'], true);
        if (($adminOnly && !CurrentUser::$admin)
            || ($action === 'Upl' && !CurrentUser::$admin && !CurrentUser::$uploader)
            || (in_array($type, ['Acc','Com'], true) && !isset(CurrentUser::$account))) {
            http_response_code(403); exit('K této akci nemáte oprávnění.');
        }
    }

    public static function verifyPassword($plain, $stored): bool
    {
        if (!is_string($plain) || !is_string($stored) || $stored === '') return false;
        if (preg_match('/\A[0-9a-f]{40}\z/D', $stored)) return hash_equals($stored, sha1($plain)) || hash_equals($stored, sha1(addslashes($plain)));
        return password_verify($plain, $stored);
    }

    public static function resolvePath($relative, $directory): string
    {
        if (!is_string($relative) || !is_string($directory) || preg_match('/[\\x00-\\x1f\\x7f\\\\]/', $relative)
            || str_starts_with($relative, '/') || in_array('..', explode('/', $relative), true)) {
            throw new InvalidArgumentException('Invalid gallery path');
        }
        $root = realpath($directory);
        if ($root === false) throw new InvalidArgumentException('Missing gallery root');
        $path = $root.'/'.ltrim($relative, '/');
        $ancestor = $path;
        while (!file_exists($ancestor) && !is_link($ancestor)) $ancestor = dirname($ancestor);
        $real = realpath($ancestor);
        if ($real === false || ($real !== $root && !str_starts_with($real, $root.'/'))) {
            throw new InvalidArgumentException('Gallery path escapes root');
        }
        return $path;
    }

    public static function validateName($name): void
    {
        if (!is_string($name) || $name === '' || $name[0] === '.' || strlen($name) > 200
            || preg_match('/[\\x00-\\x1f\\x7f\/\\\\]/', $name)) throw new InvalidArgumentException('Invalid filename');
    }

    public static function validImage(string $temporary, string $name): bool
    {
        $extensions = ['jpg'=>IMAGETYPE_JPEG, 'jpeg'=>IMAGETYPE_JPEG, 'png'=>IMAGETYPE_PNG, 'gif'=>IMAGETYPE_GIF];
        $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
        $info = @getimagesize($temporary);
        return isset($extensions[$ext]) && $info !== false && $info[2] === $extensions[$ext]
            && $info[0] > 0 && $info[1] > 0 && $info[0] * $info[1] <= 50000000;
    }

    public static function rootName(): string { return 'fotky_galerie'; }

    public static function fail(Throwable $exception): void
    {
        http_response_code($exception instanceof InvalidArgumentException ? 400 : 500);
        // Do not log query strings, account data, absolute paths or credentials.
        error_log('PhotoShow request failed: '.get_class($exception).' '.basename($exception->getFile()).':'.$exception->getLine());
        foreach ($exception->getTrace() as $frame) {
            error_log('PhotoShow frame: '.basename($frame['file'] ?? '').':'.($frame['line'] ?? 0).' '.($frame['function'] ?? ''));
        }
        echo 'Požadavek se nepodařilo zpracovat.';
    }
}
