<?php
// Run as the piwigo service user on the new server, after the initial import.
if (PHP_SAPI !== 'cli') exit(1);
chdir('/var/lib/piwigo/app');
define('PHPWG_ROOT_PATH', './');
$_SERVER['REMOTE_ADDR'] = '127.0.0.1';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['SERVER_NAME'] = 'foto.crucio.cz';
include './include/common.inc.php';
include_once './admin/include/plugins.class.php';
$plugins = new plugins();
$errors = $plugins->perform_action('activate', 'community');
if ($errors) throw new RuntimeException(json_encode($errors));
$theme = is_array($conf['modus_theme']) ? $conf['modus_theme'] : unserialize($conf['modus_theme'], ['allowed_classes'=>false]);
$theme['display_page_banner'] = true;
$theme['album_thumb_size'] = 512;
conf_update_param('modus_theme', $theme, true);
// Grant ordinary contributors upload/create-album rights, not administration.
$row = pwg_db_fetch_assoc(pwg_query("SELECT id FROM ".$prefixeTable."groups WHERE name='uploaders'"));
if (!$row) throw new RuntimeException('Missing uploaders group');
pwg_query('DELETE FROM '.$prefixeTable.'community_permissions');
single_insert($prefixeTable.'community_permissions', [
    'type'=>'group', 'group_id'=>$row['id'], 'category_id'=>null,
    '`recursive`'=>'true', 'create_subcategories'=>'true', 'moderated'=>'true',
]);
community_update_cache_key();
echo "Community activated; uploaders can upload with moderation. Banner enabled.\n";
