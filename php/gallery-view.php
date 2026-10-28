<?php
// Theme-only overview: preserve album hierarchy and Piwigo's visibility checks.
if (!defined('PHPWG_ROOT_PATH')) {
    exit;
}

// A scrollable overview fits the complete migrated collection on one page.
$conf['nb_categories_page'] = 48;

add_event_handler('loc_begin_index_category_thumbnails_query', 'vpsfree_album_overview_query');
add_event_handler('loc_end_index_category_thumbnails', 'vpsfree_album_overview_labels', 60);

function vpsfree_album_overview_query(string $query): string
{
    global $page, $user;
    if (($page['section'] ?? '') !== 'categories' || isset($page['category'])) {
        return $query;
    }

    // Only replace the root-container condition. Keep the native user-cache
    // join, category permission filters, pagination and representative checks.
    $overview = preg_replace('/\bAND id_uppercat is NULL\b/i', 'AND nb_images > 0', $query, 1, $replaced);
    if ($replaced !== 1) {
        return $query;
    }

    $level = (int)$user['level'];
    // Early albums have no EXIF date and were recopied in 2016. Their original
    // year folder is the chronological source, rather than the copy timestamp.
    // Ordinary/new albums use the latest visible photo's capture/upload date.
    $date = '(SELECT CONCAT('
        .'COALESCE(MAX(CASE WHEN p.name REGEXP \'^[0-9]{4}$\' THEN p.name END), '
        .'DATE_FORMAT(MAX(COALESCE(i.date_creation,i.date_available)), \'%Y\')), '
        .'DATE_FORMAT(MAX(COALESCE(i.date_creation,i.date_available)), \'-%m-%d %H:%i:%s\')) '
        .'FROM '.IMAGES_TABLE.' i '
        .'INNER JOIN '.IMAGE_CATEGORY_TABLE.' ic ON ic.image_id=i.id '
        .'LEFT JOIN '.CATEGORIES_TABLE.' p ON p.id=c.id_uppercat '
        .'WHERE ic.category_id=c.id AND i.level <= '.$level.')';
    $overview = preg_replace('/\bc\.\*,/', 'c.*, '.$date.' AS vpsfree_album_date,', $overview, 1, $selected);
    $overview = preg_replace('/ORDER BY `rank`/', 'ORDER BY vpsfree_album_date DESC, c.id DESC', $overview, 1, $ordered);
    return $selected === 1 && $ordered === 1 ? $overview : $query;
}

function vpsfree_album_overview_labels(array $albums): array
{
    foreach ($albums as &$album) {
        if (!empty($album['vpsfree_album_date'])) {
            $album['vpsfree_album_year'] = substr($album['vpsfree_album_date'], 0, 4);
        }
    }
    return $albums;
}
