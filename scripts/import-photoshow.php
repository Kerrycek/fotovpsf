<?php
/** Import an archived PhotoShow installation into an EMPTY new Piwigo gallery.
 * Run as root on the new VPS. Never connects to, writes to, or executes old code.
 */
if (PHP_SAPI !== 'cli' || posix_geteuid() !== 0) {
    throw new RuntimeException('Run as root on the new VPS');
}
umask(0077);
$source = $argv[1] ?? '/srv/foto-migration/source/foto.vpsfree.cz';
$state = $argv[2] ?? '/var/lib/piwigo';
$db = new mysqli('localhost', 'root', '', 'piwigo');
$db->set_charset('utf8mb4');
if ((int)$db->query('SELECT COUNT(*) FROM piwigo_images')->fetch_row()[0] !== 0
    || (int)$db->query('SELECT COUNT(*) FROM piwigo_categories')->fetch_row()[0] !== 0) {
    throw new RuntimeException('Target gallery is not empty; refusing a duplicate import');
}
if (!is_file($source . '/fotky_thumbs/Conf/accounts.xml')) {
    throw new RuntimeException('Archived source not found');
}
function insertRow(string $table, array $row): int {
    global $db;
    $columns = implode(',', array_map(fn($c) => '`'.$c.'`', array_keys($row)));
    $sql = "INSERT INTO `$table` ($columns) VALUES (".implode(',', array_fill(0, count($row), '?')).')';
    $stmt = $db->prepare($sql);
    $values = array_values($row);
    $stmt->bind_param(str_repeat('s', count($values)), ...$values);
    $stmt->execute();
    return (int)$stmt->insert_id;
}
function configValue(string $key, string $value): void {
    global $db;
    $stmt = $db->prepare('REPLACE INTO piwigo_config (param,value,comment) VALUES (?, ?, ?)');
    $comment = 'Managed vpsFree gallery configuration';
    $stmt->bind_param('sss', $key, $value, $comment);
    $stmt->execute();
}
require $state.'/app/include/passwordhash.class.php';
$hasher = new PasswordHash(13, true);
$credentialsPath = '/root/fotovpsf-access.json';
$credentials = json_decode(file_get_contents($credentialsPath), true, flags: JSON_THROW_ON_ERROR);
// Replace installer's transitional MD5 immediately, without waiting for login.
$hash = $hasher->HashPassword($credentials['admin_password']);
$stmt = $db->prepare('UPDATE piwigo_users SET password=? WHERE id=1');
$stmt->bind_param('s', $hash);
$stmt->execute();
$groupIds = [];
foreach (simplexml_load_file($source.'/fotky_thumbs/Conf/groups.xml') as $group) {
    $name = (string)$group->name;
    $groupIds[$name] = insertRow('piwigo_groups', ['name'=>$name, 'is_default'=>'false']);
}
$userIds = [];
$credentials['migrated_users'] = [];
foreach (simplexml_load_file($source.'/fotky_thumbs/Conf/accounts.xml') as $account) {
    $login = (string)$account->login;
    $password = bin2hex(random_bytes(18));
    $id = insertRow('piwigo_users', ['username'=>$login, 'password'=>$hasher->HashPassword($password), 'mail_address'=>(string)$account->email]);
    $groups = array_map('strval', iterator_to_array($account->groups->children(), false));
    insertRow('piwigo_user_infos', ['user_id'=>$id, 'status'=>in_array('root', $groups, true) ? 'admin' : 'normal', 'language'=>'cs_CZ', 'theme'=>'vpsfree', 'registration_date'=>date('Y-m-d H:i:s')]);
    foreach ($groups as $group) {
        if (!isset($groupIds[$group])) throw new RuntimeException('Unknown source group');
        insertRow('piwigo_user_group', ['user_id'=>$id, 'group_id'=>$groupIds[$group]]);
    }
    $userIds[$login] = $id;
    $credentials['migrated_users'][] = ['username'=>$login, 'password'=>$password, 'groups'=>$groups];
}
// Do not retain PhotoShow's unsalted SHA1 hashes as working credentials.
file_put_contents($credentialsPath, json_encode($credentials, JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE)."\n");
$root = realpath($source.'/fotky_galerie');
$iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root, FilesystemIterator::SKIP_DOTS), RecursiveIteratorIterator::SELF_FIRST);
$dirs = [];
$files = [];
foreach ($iterator as $entry) {
    if ($entry->isLink()) throw new RuntimeException('Symlinks in source need manual review');
    $rel = substr($entry->getPathname(), strlen($root)+1);
    if ($entry->isDir()) $dirs[] = $rel;
    elseif ($entry->isFile()) $files[] = $rel;
}
usort($dirs, fn($a,$b) => substr_count($a,'/') <=> substr_count($b,'/') ?: strnatcasecmp($a,$b));
sort($files, SORT_NATURAL|SORT_FLAG_CASE);
$categories = [];
$paths = [];
$ranks = [];
$rights = [];
foreach ($dirs as $rel) {
    $parent = dirname($rel);
    $parentId = $categories[$parent] ?? null;
    $rank = ($ranks[$parent] ?? 0)+1;
    $ranks[$parent] = $rank;
    $rightsFile = $source.'/fotky_thumbs/Thumbs/'.$rel.'/.rights.xml';
    $access = $rights[$parent] ?? ['public'=>true,'users'=>[],'groups'=>[]];
    if (is_file($rightsFile)) {
        $xml = simplexml_load_file($rightsFile);
        $access = ['public'=>(string)$xml->public==='1','users'=>array_map('strval',iterator_to_array($xml->users->children(),false)),'groups'=>array_map('strval',iterator_to_array($xml->groups->children(),false))];
    }
    $rights[$rel] = $access;
    $id = insertRow('piwigo_categories', ['name'=>str_replace('_',' ',basename($rel)), 'id_uppercat'=>$parentId, 'rank'=>$rank, 'status'=>$access['public']?'public':'private', 'uppercats'=>'', 'global_rank'=>isset($paths[$parent])?$paths[$parent]['rank'].'.'.$rank:(string)$rank, 'commentable'=>'false']);
    $uppercats = isset($paths[$parent])?$paths[$parent]['ids'].','.$id:(string)$id;
    $stmt = $db->prepare('UPDATE piwigo_categories SET uppercats=? WHERE id=?');
    $stmt->bind_param('si',$uppercats,$id);$stmt->execute();
    $categories[$rel] = $id;
    $paths[$rel] = ['ids'=>$uppercats,'rank'=>isset($paths[$parent])?$paths[$parent]['rank'].'.'.$rank:(string)$rank];
    foreach ($access['users'] as $login) {
        if (!isset($userIds[$login])) throw new RuntimeException('Unmapped private album user');
        insertRow('piwigo_user_access',['user_id'=>$userIds[$login],'cat_id'=>$id]);
    }
    foreach ($access['groups'] as $group) {
        if (!isset($groupIds[$group])) throw new RuntimeException('Unmapped private album group');
        insertRow('piwigo_group_access',['group_id'=>$groupIds[$group],'cat_id'=>$id]);
    }
}
$manifest = [];
$representatives = [];
foreach ($files as $rel) {
    $src = $root.'/'.$rel;
    $size = getimagesize($src);
    if (!$size || $size[2] !== IMAGETYPE_JPEG) throw new RuntimeException('Unexpected image type in archive');
    $parent = dirname($rel);
    if (!isset($categories[$parent])) throw new RuntimeException('Root photos need an explicit migration album');
    if (is_file($source.'/fotky_thumbs/Thumbs/'.$parent.'/.'.basename($rel).'_rights.xml')) throw new RuntimeException('Per-image permissions require manual translation');
    $path = './galleries/legacy/'.$rel;
    if (strlen($path)>255) throw new RuntimeException('Photo path exceeds Piwigo storage limit');
    $target = $state.'/galleries/legacy/'.$rel;
    if (!is_dir(dirname($target))) mkdir(dirname($target),0750,true);
    if (!copy($src,$target)) throw new RuntimeException('Photo copy failed');
    chmod($target,0640);chown($target,'piwigo');chgrp($target,'nginx');
    $sha = hash_file('sha256',$src);
    if (!hash_equals($sha,hash_file('sha256',$target))) throw new RuntimeException('Photo checksum differs');
    $exif = @exif_read_data($src);
    $created = $exif['DateTimeOriginal'] ?? null;
    if ($created && preg_match('/^\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}$/',$created)) $created = substr_replace(substr_replace($created,'-',4,1),'-',7,1);
    else $created = null;
    $id = insertRow('piwigo_images',['file'=>basename($rel),'date_available'=>date('Y-m-d H:i:s',filemtime($src)),'date_creation'=>$created,'name'=>pathinfo($rel,PATHINFO_FILENAME),'path'=>$path,'filesize'=>(int)ceil(filesize($src)/1024),'width'=>$size[0],'height'=>$size[1],'level'=>0,'md5sum'=>hash_file('md5',$src),'added_by'=>1]);
    insertRow('piwigo_image_category',['image_id'=>$id,'category_id'=>$categories[$parent],'rank'=>$id]);
    $representatives[$parent] ??= $id;
    $manifest[] = ['path'=>$rel,'sha256'=>$sha,'image_id'=>$id,'category_id'=>$categories[$parent]];
}
foreach (array_reverse($dirs) as $rel) {
    $rep = $representatives[$rel] ?? null;
    if (!$rep) continue;
    $stmt=$db->prepare('UPDATE piwigo_categories SET representative_picture_id=? WHERE id=?');
    $id=$categories[$rel];$stmt->bind_param('ii',$rep,$id);$stmt->execute();
    $parent=dirname($rel);$representatives[$parent] ??= $rep;
}
$db->query("INSERT INTO piwigo_themes (id,version) VALUES ('vpsfree','1.0.0')");
$db->query("UPDATE piwigo_user_infos SET theme='vpsfree', language='cs_CZ'");
configValue('gallery_title','Fotogalerie vpsFree.cz');
configValue('page_banner','<div class="vpsfree-brand"><a href="./"><span>vps<span class="brand-orange">Free</span>.cz</span><small>Fotogalerie</small></a></div>');
configValue('allow_user_registration','false');
configValue('comments_forall','false');
configValue('comments_validation','true');
$db->query('DELETE FROM piwigo_user_cache');
$db->query('DELETE FROM piwigo_user_cache_categories');
// Preserve all profile fields and original XML/INI in the private source archive.
file_put_contents('/srv/foto-migration/import-manifest.json',json_encode($manifest,JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE)."\n");
echo 'Imported '.count($files).' photos, '.count($dirs).' albums, '.count($userIds).' users, '.count($groupIds)." groups.\n";
