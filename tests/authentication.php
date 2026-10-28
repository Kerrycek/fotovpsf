<?php
// Pure hash/bucket tests; no live database or credential files.
define('PHPWG_ROOT_PATH', '/var/lib/piwigo/app/');
define('USERS_TABLE', 'test_users');
require __DIR__.'/../php/authentication.php';
require PHPWG_ROOT_PATH.'include/passwordhash.class.php';
$conf = ['user_fields' => ['id' => 'id', 'password' => 'password']];
$updates = [];
function single_update($table, $set, $where) { global $updates; $updates[] = [$table, $set, $where]; }
$checks = 0;
function check($condition, $message) { global $checks; if (!$condition) throw new RuntimeException($message); $checks++; }
function limited(callable $call, int $retry) {
    try { $call(); } catch (VpsfreeLoginLimited $error) { check($error->retryAfter === $retry, 'Retry interval incorrect'); return; }
    throw new RuntimeException('Expected login limit');
}

$password = 'Synthetic unicode heslo čřž '.str_repeat('x', 100);
$hash = pwg_password_hash($password);
check(str_starts_with($hash, '$argon2id$'), 'New hash is not Argon2id');
check(pwg_password_verify($password, $hash), 'Modern password rejected');
check(!pwg_password_verify($password.'different', $hash), 'Long password truncated');
check(!pwg_password_verify('wrong', $hash), 'Wrong password accepted');
check(!pwg_password_verify([], $hash), 'Malformed password accepted');
check(!pwg_password_verify('x', 'invalid'), 'Unknown hash accepted');
$portable = (new PasswordHash(13, true))->HashPassword($password);
check(!pwg_password_verify('wrong', $portable, 42) && $updates === [], 'Wrong legacy password rehashed');
check(pwg_password_verify($password, $portable, 42), 'Legacy password rejected');
check(count($updates) === 1 && $updates[0][2] === ['id' => 42, 'password' => $portable], 'Rehash can overwrite a concurrent password reset');
check(password_verify($password, $updates[0][1]['password']), 'Rehash changed the password');
$updates = [];
check(pwg_password_verify($password, $hash, 42) && !$updates, 'Current hash was rewritten');
check(pwg_password_verify($password, md5($password), 42) && count($updates) === 1, 'MD5 migration failed');
$updates = [];
check(pwg_password_verify($password, password_hash($password, PASSWORD_BCRYPT), 42) && count($updates) === 1, 'bcrypt migration failed');
$updates = [];
check(pwg_password_verify($password, $hash) && !$updates, 'API-key verification changed a user');
$conf['external_authentification'] = true;
check(pwg_password_verify($password, $portable, 42) && !$updates, 'External identity rewritten');
unset($conf['external_authentification']);

$directory = sys_get_temp_dir().'/gallery-auth-unit-'.bin2hex(random_bytes(8));
mkdir($directory, 0700);
try {
    $gate = new VpsfreeLoginGate($directory);
    for ($i = 0; $i < 5; $i++) $gate->reserve('192.0.2.1', 1000);
    limited(fn() => $gate->reserve('192.0.2.1', 1000), 30);
    // State survives another request/object, not tied to cookies or username.
    limited(fn() => (new VpsfreeLoginGate($directory))->reserve('192.0.2.1', 1015), 15);
    $gate->reserve('192.0.2.1', 1030);
    limited(fn() => $gate->reserve('192.0.2.1', 1030), 30);
    $gate->reserve('192.0.2.2', 1000);
    $gate->refund('192.0.2.2', 1000);
    for ($i = 0; $i < 5; $i++) $gate->reserve('192.0.2.2', 1000);
    limited(fn() => $gate->reserve('192.0.2.2', 1000), 30);
    $gate->reserve('192.0.2.3', 1000);
    $gate->reserve('192.0.2.3', 1000);
    $gate->refund('192.0.2.3', 1000);
    for ($i = 0; $i < 4; $i++) $gate->reserve('192.0.2.3', 1000);
    limited(fn() => $gate->reserve('192.0.2.3', 1000), 30);
    check(vpsfree_login_bucket('192.0.2.1') === vpsfree_login_bucket('::ffff:192.0.2.1'), 'IPv4-mapped bypass');
    check(vpsfree_login_bucket('2001:db8:1::1') === vpsfree_login_bucket('2001:db8:1::ffff'), 'IPv6 rotation bypass');
    check(vpsfree_login_bucket('2001:db8:1::1') !== vpsfree_login_bucket('2001:db8:2::1'), 'Independent IPv6 networks share a bucket');
    foreach (glob($directory.'/*') as $file) check((fileperms($file) & 0777) === 0600, 'State permissions too broad');
    file_put_contents($directory.'/'.vpsfree_login_bucket('192.0.2.4').'.json', 'corrupt');
    try { $gate->reserve('192.0.2.4', 1000); throw new LogicException('Corrupt state accepted'); }
    catch (LogicException $error) { throw $error; }
    catch (RuntimeException $error) { check(true, 'Corrupt state failed closed'); }
} finally {
    foreach (glob($directory.'/*') as $file) unlink($file);
    rmdir($directory);
}
echo "$checks hash migration, race protection, bucket and expiry checks passed\n";
