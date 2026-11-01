<?php
/** Regression checks against the packaged application, using synthetic fixtures. */
$app = $argv[1];
require $app.'/src/classes/Modern.php';
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
    check(Modern::resolvePath('',$photos)===$photos.'/', 'root');
    check(Modern::resolvePath('Album/nová fotka.jpg',$photos)===$photos.'/Album/nová fotka.jpg','new file');
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
    $image=imagecreatetruecolor(80,60);imagejpeg($image,$root.'/valid.jpg');
    check(Modern::validImage($root.'/valid.jpg','valid.jpg'),'JPEG upload');
    check(!Modern::validImage($root.'/valid.jpg','fake.png'),'mismatched MIME');
    file_put_contents($root.'/fake.jpg','<?php echo 1;');
    check(!Modern::validImage($root.'/fake.jpg','fake.jpg'),'fake JPEG');
    require_once $app.'/src/phpthumb/ThumbLib.inc.php';
    $thumb=PhpThumbFactory::create($root.'/valid.jpg');$thumb->adaptiveResize(32,32);$thumb->save($root.'/thumb.jpg');
    check(array_slice(getimagesize($root.'/thumb.jpg'),0,2)===[32,32],'fresh GD thumbnail');
    echo "PASS $checks checks\n";
} finally {
    unlink($root.'/photos/escape');rmdir($root.'/photos');rmdir($root.'/elsewhere');
    foreach(glob($root.'/*') as $file) unlink($file);rmdir($root);
}
