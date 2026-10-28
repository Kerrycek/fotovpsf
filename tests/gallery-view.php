<?php
// Check that the overview changes presentation without removing privacy filters.
define('PHPWG_ROOT_PATH', './');
define('IMAGES_TABLE', 'piwigo_images');
define('IMAGE_CATEGORY_TABLE', 'piwigo_image_category');
define('CATEGORIES_TABLE', 'piwigo_categories');
function add_event_handler(...$arguments): void {}
require dirname(__DIR__).'/php/gallery-view.php';

function check(bool $condition, string $message): void {
    if (!$condition) throw new RuntimeException($message);
}
$page = ['section'=>'categories'];
$user = ['level'=>0];
$query = 'SELECT SQL_CALC_FOUND_ROWS c.*, nb_images FROM piwigo_categories c '
    .'INNER JOIN piwigo_user_cache_categories ucc ON c.id=ucc.cat_id AND user_id=2 '
    .'WHERE count_images > 0 AND id_uppercat is NULL AND id NOT IN (99) '
    .'ORDER BY `rank` LIMIT 48 OFFSET 0';
$overview = vpsfree_album_overview_query($query);
check($overview !== $query, 'Root overview was not changed');
check(str_contains($overview, 'AND nb_images > 0'), 'Empty year containers included');
check(str_contains($overview, 'AND user_id=2'), 'Native user cache condition lost');
check(str_contains($overview, 'AND id NOT IN (99)'), 'Private category filter lost');
check(str_contains($overview, 'i.level <= 0'), 'Photo privacy level not applied to chronology');
check(str_contains($overview, 'LIMIT 48 OFFSET 0'), 'Native pagination lost');
check(str_contains($overview, 'ORDER BY vpsfree_album_date DESC, c.id DESC'), 'Newest-first order missing');
$page['category'] = ['id'=>12];
check(vpsfree_album_overview_query($query) === $query, 'Nested album view changed');
unset($page['category']);$page['section']='recent_cats';
check(vpsfree_album_overview_query($query) === $query, 'Special view changed');
$page['section']='categories';
check(vpsfree_album_overview_query(str_replace('ORDER BY `rank`','ORDER BY name',$query)) === str_replace('ORDER BY `rank`','ORDER BY name',$query), 'Unknown query was partially rewritten');
$albums = vpsfree_album_overview_labels([['vpsfree_album_date'=>'2018-10-15 20:47:16'],['NAME'=>'Nested']]);
check($albums[0]['vpsfree_album_year'] === '2018' && !isset($albums[1]['vpsfree_album_year']), 'Year context leaked into unrelated views');
echo "11 overview scope, privacy and ordering checks passed\n";
