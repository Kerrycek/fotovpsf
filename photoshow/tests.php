<?php
/** Regression checks against the packaged application, using synthetic fixtures. */
$app = $argv[1];
require $app.'/src/classes/Modern.php';
require $app.'/src/security/login-gate.php';
spl_autoload_register(static function($class) use ($app) {
    $path=$app.'/src/classes/'.$class.'.php';
    if(is_file($path)) require_once $path;
});
$checks=0;
function check($condition, $label) { global $checks; if(!$condition) throw new RuntimeException($label); ++$checks; }
function rejects($fn, $label) { try { $fn(); } catch(InvalidArgumentException $e) { check(true,$label); return; } check(false,$label); }
foreach(glob($app.'/src/classes/*.php') as $path) {
    if(basename($path)==='API.php') continue;
    $class=basename($path,'.php');
    check(class_exists($class) || interface_exists($class), 'class '.$class);
}
$root=sys_get_temp_dir().'/photoshow-test-'.bin2hex(random_bytes(8));
mkdir($root,0700);mkdir($root.'/photos');mkdir($root.'/elsewhere');symlink($root.'/elsewhere',$root.'/photos/escape');
try {
    $photos=$root.'/photos';
    check(Modern::resolvePath('',$photos)===realpath($photos).'/', 'root');
    check(Modern::resolvePath('Album/nová fotka.jpg',$photos)===realpath($photos).'/Album/nová fotka.jpg','new file');
    foreach(['../secret','Album/../../secret','/etc/passwd',"test\0.jpg",'escape/image.jpg'] as $bad) rejects(fn()=>Modern::resolvePath($bad,$photos),'path rejected');
    foreach(['.hidden','..','a/b.jpg',"a\\b.jpg"] as $bad) rejects(fn()=>Modern::validateName($bad),'filename rejected');
    $plain="Dlouhé heslo: ' \\ 🐷 ".str_repeat('x',90);
    $hash=Account::password($plain);
    check(password_get_info($hash)['algoName']==='argon2id','modern password');
    check(Modern::verifyPassword($plain,$hash),'long Unicode password');
    check(!Modern::verifyPassword($plain.'x',$hash),'wrong modern password');
    check(Modern::verifyPassword($plain,sha1($plain)),'legacy SHA1 verify');
    check(!Modern::verifyPassword('wrong',sha1($plain)),'legacy wrong password');
    check(Modern::verifyPassword($plain,sha1(addslashes($plain))),'legacy magic-quotes password');
    check(Modern::verifyPassword($plain,'legacy-sha1:'.Account::password(sha1($plain))),'wrapped legacy password');
    check(Modern::verifyPassword($plain,'legacy-sha1:'.Account::password(sha1(addslashes($plain)))),'wrapped legacy magic quotes');
    check(!Modern::verifyPassword('wrong','legacy-sha1:'.Account::password(sha1($plain))),'wrapped legacy wrong password');
    $account = new Account(); $account->login = 'Fixture'; $account->password = $hash;
    $identity = ['auth_fingerprint'=>hash('sha256', "Fixture\0".$hash), 'auth_started'=>1000, 'auth_seen'=>1000];
    $_SESSION = $identity;
    check(Modern::sessionMatches($account,1100),'bound session valid');
    $_SESSION = $identity;
    check(!Modern::sessionMatches($account,2800),'idle timeout');
    $_SESSION = $identity; $_SESSION['auth_seen'] = 44199;
    check(!Modern::sessionMatches($account,44200),'absolute timeout');
    $_SESSION = $identity; $account->password = Account::password('replacement password');
    check(!Modern::sessionMatches($account,1100),'changed password revokes session');
    $_SESSION = $identity;
    check(!Modern::sessionMatches(new Account(),1100),'deleted account session rejected');
    $_SESSION = ['login'=>'Fixture']; $account->password = $hash;
    check(!Modern::sessionMatches($account,1100),'unbound legacy session rejected');
    $_SESSION = $identity;
    check(!Modern::sessionMatches($account,999),'future session timestamp rejected');
    $image=imagecreatetruecolor(80,60);imagejpeg($image,$root.'/valid.jpg');
    check(Modern::validImage($root.'/valid.jpg','valid.jpg'),'JPEG upload');
    check(!Modern::validImage($root.'/valid.jpg','fake.png'),'mismatched MIME');
    file_put_contents($root.'/fake.jpg','<?php echo 1;');
    check(!Modern::validImage($root.'/fake.jpg','fake.jpg'),'fake JPEG');
    require_once $app.'/src/phpthumb/ThumbLib.inc.php';
    $thumb=PhpThumbFactory::create($root.'/valid.jpg');$thumb->adaptiveResize(32,32);$thumb->save($root.'/thumb.jpg');
    check(array_slice(getimagesize($root.'/thumb.jpg'),0,2)===[32,32],'fresh GD thumbnail');
    // Hidden XML is authoritative access data, not a disposable thumbnail cache.
    mkdir($root.'/sandbox'); mkdir($root.'/metadata');
    Settings::$photos_dir = $root.'/sandbox'; Settings::$thumbs_dir = $root.'/metadata';
    CurrentUser::$tokens_file = $root.'/tokens.xml'; CurrentUser::$admin = true;
    mkdir($root.'/sandbox/Private'); mkdir($root.'/sandbox/Destination');
    copy($root.'/valid.jpg', $root.'/sandbox/Private/image.jpg');
    Judge::edit($root.'/sandbox/Private', [], [], true);
    file_put_contents($root.'/metadata/Private/.image.jpg_comments.xml', '<comments/>');
    StateFiles::move($root.'/sandbox/Private', $root.'/sandbox/Destination/Moved');
    CurrentUser::$admin = false;
    check(!Judge::view($root.'/sandbox/Destination/Moved/image.jpg'),'moved private album stays private');
    check(is_file($root.'/metadata/Destination/Moved/.image.jpg_comments.xml'),'moved comments retained');
    CurrentUser::$admin = true;
    StateFiles::move($root.'/sandbox/Destination/Moved/image.jpg', $root.'/sandbox/renamed.jpg');
    CurrentUser::$admin = false;
    check(!Judge::view($root.'/sandbox/renamed.jpg'),'inherited private file stays private after move');
    check(is_file($root.'/metadata/.renamed.jpg_comments.xml'),'file comment renamed');
    CurrentUser::$admin = true;
    StateFiles::remove($root.'/sandbox/renamed.jpg');
    check(!file_exists($root.'/metadata/.renamed.jpg_rights.xml'),'deleted file ACL cleaned');
    StateFiles::remove($root.'/sandbox/Destination');
    rmdir($root.'/sandbox'); rmdir($root.'/metadata');
    CurrentUser::$accounts_file = $root.'/accounts.xml';
    file_put_contents(CurrentUser::$accounts_file, '<accounts><account><login>Alice</login><password>fixture</password><name/><email/><language/><key/><groups><group>root</group></groups></account></accounts>');
    Account::edit('Alice', null, null, null, null, []);
    check((new Account('Alice'))->groups === [],'remove final group from capitalized account');
    rejects(fn()=>Account::edit('Alice', null, '🐷🐷🐷🐷'), 'password length counts Unicode characters');
    unlink(CurrentUser::$accounts_file);
    mkdir($root.'/gate',0700);
    $gate=new PhotoShowLoginGate($root.'/gate');
    for($i=0;$i<5;$i++) $gate->reserve('192.0.2.5', 1000);
    try { $gate->reserve('192.0.2.5',1000); check(false,'failure budget'); }
    catch(PhotoShowLoginLimited $e) { check($e->retryAfter===30,'failure budget'); }
    $gate->reserve('192.0.2.5',1030); $gate->refund('192.0.2.5',1030);
    check(true,'refill/refund');
    $xml=new SimpleXMLElement('<test><value>retained</value></test>');
    Modern::saveXml($xml,$root.'/state.xml');
    check((string)simplexml_load_file($root.'/state.xml')->value==='retained','atomic XML');
    check((fileperms($root.'/state.xml')&0777)===0600,'XML mode');
    foreach(glob($root.'/gate/*') as $file) unlink($file);rmdir($root.'/gate');
    echo "PASS $checks checks\n";
} finally {
    unlink($root.'/photos/escape');rmdir($root.'/photos');rmdir($root.'/elsewhere');
    foreach(glob($root.'/*') as $file) unlink($file);rmdir($root);
}
