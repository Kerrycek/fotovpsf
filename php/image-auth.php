<?php
/** Nginx internal authorization for both cached and on-demand derivatives.
 * Piwigo's i.php deliberately skips database/ACL bootstrap. Authorize against
 * the ORIGINAL image before allowing either i.php or its cached output.
 */
function galleryOriginalPath(string $uri): ?string
{
    if (str_starts_with($uri, '/i.php?/')) {
        $path = substr($uri, strlen('/i.php?/'));
    } elseif (str_starts_with($uri, '/_data/i/')) {
        $path = explode('?', substr($uri, strlen('/_data/i/')), 2)[0];
    } else {
        return null;
    }
    $path = rawurldecode($path);
    if (!preg_match('~^(?:galleries|upload)/~', $path)
        || preg_match('~(?:^|/)\.{1,2}(?:/|$)|[\x00-\x1f\\\\]~', $path)) {
        return null;
    }
    $original = preg_replace('/-(?:sq|th|2s|xs|sm|me|la|xl|xx|cu_[a-zA-Z0-9_]+)(\.[a-zA-Z0-9]+)$/', '$1', $path, 1, $count);
    return $count === 1 ? './'.$original : null;
}
if (PHP_SAPI === 'cli') return;
$original = galleryOriginalPath($_SERVER['GALLERY_ORIGINAL_URI'] ?? '');
if ($original === null) { http_response_code(403); exit; }
define('PHPWG_ROOT_PATH', './');
include PHPWG_ROOT_PATH.'include/common.inc.php';
$sql = 'SELECT i.id FROM '.IMAGES_TABLE.' i INNER JOIN '.IMAGE_CATEGORY_TABLE.' ic ON ic.image_id=i.id'
    .' WHERE i.path=\''.pwg_db_real_escape_string($original).'\''
    .get_sql_condition_FandF(['forbidden_categories'=>'ic.category_id','forbidden_images'=>'i.id'], ' AND'). ' LIMIT 1';
if (pwg_db_num_rows(pwg_query($sql)) !== 1) {
    error_log('Gallery image authorization denied: user='.(int)$user['id'].' session_cookie='.(isset($_COOKIE[session_name()])?'present':'absent').' source='.$original);
    http_response_code(403); exit;
}
http_response_code(204);
