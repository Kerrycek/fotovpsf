<?php
require __DIR__.'/../php/image-auth.php';
$cases = [
    '/i.php?/galleries/legacy/2010/rack-th.JPG'=>'./galleries/legacy/2010/rack.JPG',
    '/_data/i/upload/2026/10/image-me.jpg'=>'./upload/2026/10/image.jpg',
    '/i.php?/upload/photo-cu_250_250.jpg'=>'./upload/photo.jpg',
    '/i.php?/galleries/A%20B/photo-sm.jpg'=>'./galleries/A B/photo.jpg',
    '/i.php?/galleries/%2e%2e/local/config-sq.php'=>null,
    '/i.php?/galleries/a%00-sm.jpg'=>null,
    '/i.php?/galleries/foo\\bar-sm.jpg'=>null,
    '/i.php?/local/config-sm.php'=>null,
    '/i.php?/galleries/photo.jpg'=>null,
    '/image-auth.php'=>null,
];
foreach ($cases as $uri=>$expected) {
    if (galleryOriginalPath($uri) !== $expected) {
        throw new RuntimeException('Path authorization mismatch: '.$uri);
    }
}
echo count($cases)." image authorization path cases passed.\n";
