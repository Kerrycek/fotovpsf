<?php
// Root-only, after a consistent backup. Never reset a changed password.
if (PHP_SAPI !== 'cli' || posix_geteuid() !== 0) exit(1);
define('PHPWG_ROOT_PATH', '/var/lib/piwigo/app/');
require dirname(__DIR__).'/php/authentication.php';
// Root has its own socket identity; do not bootstrap the web user's DB login.
$db = new mysqli('localhost', 'root', '', 'piwigo', 0, '/run/mysqld/mysqld.sock');
$db->set_charset('utf8mb4');
$select = $db->prepare('SELECT id,password FROM piwigo_users WHERE username=?');
$update = $db->prepare('UPDATE piwigo_users SET password=? WHERE id=? AND password=?');
$access = json_decode(file_get_contents('/root/fotovpsf-access.json'), true, flags: JSON_THROW_ON_ERROR);
$credentials = [['username' => $access['admin_username'], 'password' => $access['admin_password']]];
$credentials = array_merge($credentials, $access['migrated_users'] ?? []);
$matched = 0;
$deferred = 0;
foreach ($credentials as $credential) {
    $select->bind_param('s', $credential['username']);
    $select->execute();
    $row = $select->get_result()->fetch_assoc();
    if (!$row || !pwg_password_verify($credential['password'], $row['password'])) {
        $deferred++;
        continue;
    }
    if (password_needs_rehash($row['password'], PASSWORD_ARGON2ID, VPSFREE_ARGON_OPTIONS)) {
        $hash = pwg_password_hash($credential['password']);
        $update->bind_param('sis', $hash, $row['id'], $row['password']);
        $update->execute();
    }
    $matched++;
}
echo "Verified existing credentials and modernized $matched accounts; deferred $deferred changed/absent credentials. No password reset.\n";
