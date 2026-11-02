<?php
/** Move native metadata together with photos; hidden XML contains access rights. */
final class StateFiles
{
    private static function relative(string $path): string
    {
        $canonical = realpath($path);
        if ($canonical === false) {
            $parent = realpath(dirname($path));
            if ($parent === false) throw new InvalidArgumentException('Missing parent album');
            $canonical = $parent.'/'.basename($path);
        }
        $root = realpath(Settings::$photos_dir);
        if ($canonical === $root) return '';
        if (!str_starts_with($canonical, $root.'/')) throw new InvalidArgumentException('Path outside gallery');
        return substr($canonical, strlen($root) + 1);
    }

    private static function pairs(string $from, string $to): array
    {
        $old = File::r2a(self::relative($from), Settings::$thumbs_dir);
        $new = File::r2a(self::relative($to), Settings::$thumbs_dir);
        if (is_dir($from)) return [[$old, $new]];
        $pairs = [[$old, $new]];
        foreach (['_rights.xml', '_comments.xml'] as $suffix) {
            $pairs[] = [dirname($old).'/.'.basename($old).$suffix, dirname($new).'/.'.basename($new).$suffix];
        }
        $small = static fn($p) => dirname($p).'/'.pathinfo($p, PATHINFO_FILENAME).'_small.'.pathinfo($p, PATHINFO_EXTENSION);
        $pairs[] = [$small($old), $small($new)];
        return $pairs;
    }

    public static function move(string $from, string $to): void
    {
        $source = realpath($from);
        $relative = self::relative($from);
        $to = File::r2a(self::relative($to));
        $root = realpath(Settings::$photos_dir);
        if ($source === false || is_link($from) || is_link($to) || $source === $root || $source === realpath($to)
            || str_starts_with($to.'/', $source.'/')) throw new InvalidArgumentException('Invalid move');
        if (file_exists($to)) throw new InvalidArgumentException('Destination exists');
        // Materialize inherited rights before changing the parent directory.
        $judge = new Judge($from);
        $judge->save();
        $moved = [];
        try {
            foreach (self::pairs($from, $to) as [$old, $new]) {
                if (!file_exists($old)) continue;
                if (file_exists($new)) throw new InvalidArgumentException('Destination metadata exists');
                if (!is_dir(dirname($new)) && !mkdir(dirname($new), 0700, true)) throw new RuntimeException('Metadata directory unavailable');
                if (!rename($old, $new)) throw new RuntimeException('Metadata move failed');
                $moved[] = [$old, $new];
            }
            if (!rename($from, $to)) throw new RuntimeException('Photo move failed');
        } catch (Throwable $failure) {
            foreach (array_reverse($moved) as [$old, $new]) {
                if (!rename($new, $old)) throw new RuntimeException('Metadata rollback failed');
            }
            throw $failure;
        }
        self::revokeShares($relative);
    }

    /** Remove only a confined item's metadata, never an album root or a symlink. */
    public static function remove(string $from): void
    {
        $relative = self::relative($from);
        if (realpath($from) === realpath(Settings::$photos_dir)) throw new InvalidArgumentException('Cannot delete gallery root');
        $pairs = self::pairs($from, $from);
        foreach ($pairs as [$metadata]) self::removeTree($metadata);
        self::removeTree($from);
        self::revokeShares($relative);
    }

    private static function removeTree(string $path): void
    {
        if (is_link($path)) throw new InvalidArgumentException('Symlink cannot be removed');
        if (!file_exists($path)) return;
        if (is_dir($path)) {
            foreach (new DirectoryIterator($path) as $item) {
                if (!$item->isDot()) self::removeTree($item->getPathname());
            }
            if (!rmdir($path)) throw new RuntimeException('Directory removal failed');
        } elseif (!unlink($path)) throw new RuntimeException('File removal failed');
    }

    private static function revokeShares(string $relative): void
    {
        if (!file_exists(CurrentUser::$tokens_file)) return;
        $xml = simplexml_load_file(CurrentUser::$tokens_file);
        for ($i = count($xml->token) - 1; $i >= 0; --$i) {
            $path = (string)$xml->token[$i]->path;
            if ($path === $relative || str_starts_with($path, $relative.'/')) unset($xml->token[$i]);
        }
        Modern::saveXml($xml, CurrentUser::$tokens_file);
    }
}
