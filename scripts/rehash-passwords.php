<?php
// Root-only, after a consistent backup. Never reset a changed password.
if (PHP_SAPI !== 'cli' || posix_geteuid() !== 0) exit(1);
chdir('/var/lib/piwigo/app');
define('PHPWG_ROOT_PATH', './');
$_SERVER['REMOTE_ADDR'] = '127.0.0.1';
$_SERVER['SCRIPT_NAME'] = '/index.php';
include './include/common.inc.php';
$access = json_decode(file_get_contents('/root/fotovpsf-access.json'), true, flags: JSON_THROW_ON_ERROR);
$credentials = [['username' => $access['admin_username'], 'password' => $access['admin_password']]];
$credentials = array_merge($credentials, $access['migrated_users'] ?? []);
$matched = 0;
$deferred = 0;
foreach ($credentials as $credential) {
    $row = pwg_db_fetch_assoc(pwg_query('SELECT id,password FROM '.USERS_TABLE
        ." WHERE username='".pwg_db_real_escape_string($credential['username'])."'"));
    if (!$row || !pwg_password_verify($credential['password'], $row['password'], $row['id'])) {
        $deferred++;
        continue;
    }
    $matched++;
}
echo "Verified existing credentials and modernized $matched accounts; deferred $deferred changed/absent credentials. No password reset.\n";
