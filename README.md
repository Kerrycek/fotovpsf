# Fotogalerie vpsFree.cz

Piwigo 16.4.0 on NixOS 26.05 with PHP 8.4 and MariaDB 11.4. An immutable
application package, a vpsFree theme derived from bundled Modus, and separate
portable state make the test installation suitable for later integration into
the existing `int.web` container.

The bundled white vpsFree wordmark comes from the existing vpsFree website's
`obrazky/vpsFree-bile.png`. Gallery, login/profile and administration styling
uses its blue/orange identity while retaining Piwigo's supported workflows.
The favicon and Apple touch icon are the existing vpsFree website assets from
`obrazky/favicon.png` and `obrazky/ctverec.png`. Versioned URLs refresh browser
icon caches across gallery, sign-in and administration pages.

## Scope

Development target: `root@37.205.8.218`, preview `foto.crucio.cz`.
Original `root@172.16.9.28` is **read only**. No production cutover is included.
All photo data, accounts, credentials, database dumps and receipts remain
outside Git. The original PhotoShow archive is private and never served.

## Deploy

```sh
nixos-rebuild build --flake /srv/fotovpsf#foto-test
nixos-rebuild switch --flake /srv/fotovpsf#foto-test
```

`nixos/gallery.nix` exports `services.vpsfreeGallery`. Import this module on the
eventual target alongside existing websites. Configure its hostname, public
listening and TLS (disable local TLS when using the existing TLS proxy).
Set `trustedProxyAddresses` to the actual proxy addresses, retain
`externalHTTPS = true` for secure cookies, and leave `openFirewall = false`
on the original host so its existing proxy-only access rule remains effective.
Use the same package lock while rehearsing the move. The gallery has its own
PHP pool and system user. MariaDB listens only on a Unix socket and uses a
separate `/var/lib/mysql-piwigo` data directory, preserving old `/var/lib/mysql`.

Application code/themes/plugins are read only in the Nix store. Update pinned
packages through Git/Nix, not through the web interface. Writable state lives
in `/var/lib/piwigo`, with `app` pointing to the built package.

Daily consistent backups run at 03:15–03:20 local time via
`piwigo-backup.timer`, in `/var/backups/piwigo` (root only). The PHP pool pauses
briefly so uploaded files and MyISAM tables form one coherent backup. Run
`systemctl start piwigo-backup` for a manual checkpoint. Copies on the same VPS
are recovery checkpoints; arrange off-host storage, retention and disk-space
monitoring before production. No backup is deleted automatically.

## Initial migration

1. Copy the whole original PhotoShow tree into private staging on the NEW VPS.
   Compare sorted SHA256 manifests of every source and archived file.
2. Keep the initial listener on loopback, enable `installationMode`, then run
   `python3 scripts/install.py` on the new VPS. It refuses a nonempty database.
   Generated credentials stay in `/root/fotovpsf-access.json` (0600).
   For a fresh machine, first set `public = false`, `tls = false`,
   `basicAuthFile = null`, `installationMode = true` in the host configuration.
   The installer creates the private preview gate; only then enable the final
   public/TLS configuration. The committed host is the configured preview.
3. Take a pre-import dump. Run `php scripts/import-photoshow.php` as root on
   the new VPS. It refuses a nonempty gallery. Photos retain their bytes and
   directory layout; album nesting, accounts and groups are imported. Source
   XML/INI, profiles, old code and thumbnails remain in the private archive.
4. Old unsalted SHA1 passwords are replaced with random passwords, saved in
   the root-only access file. No email is sent. Deliver credentials securely
   and rotate them when handing over the gallery.
   Outbound mail is disabled on the preview; configure the administrator's
   real email and mail transport before enabling email-based recovery or
   contributor notifications in production.
   Then initialize the theme and contributor policy once with
   `runuser -u piwigo -- php /srv/fotovpsf/scripts/configure.php`. This bootstrap
   resets Community contributor rules to the documented uploaders/moderation
   baseline; do not rerun it over later operator customizations.
5. Disable `installationMode`, verify permissions and direct-file access,
   apply HTTPS and a temporary preview access gate before exposing test data.

An interrupted import must be inspected and restored from the pre-import
backup before repeating. The import deliberately stops on symlinks, unknown
image types, per-image ACLs or unmapped ACL principals instead of silently
publishing data. Source PhotoShow defaults to public access when no inherited
rights file exists. Recheck that assumption for a different source archive.

## Migration to the original VPS

Prepare a new gallery module in the managed `vpsfree-cz-configuration` repository;
the original `/etc/nixos` files are stale. Build against that host's pinned
Nixpkgs. Take a consistent database dump and archive `/var/lib/piwigo` during
a short write freeze; copy the private source archive separately. Recreate
the package/user/socket database on the target, import the dump and restore
state ownership. Validate on a temporary local port before enabling the
existing `foto.vpsfree.cz` virtual host. Test original hashes, albums, users,
upload, private images, cache and TLS proxy headers. Keep the test VPS and
pre-move backups for rollback. Production changes require a later instruction.

Reapply `systemd-tmpfiles --create` after restoring state so managed code/policy
symlinks and directory ownership match the target build. Test legacy
PhotoShow URL redirects, mail settings and off-host backups before a production
cutover; the preview does not change the original domain or its links.

## Preview access and checks

Retrieve credentials over your existing SSH connection (never put them in Git):

```sh
ssh root@37.205.8.218 'cat /root/fotovpsf-access.json'
```

The preview now allows public browsing, as requested. Sign in to the gallery
with `admin_username` / `admin_password` for administration and uploads.
`migrated_users` contains replacement passwords for the two legacy accounts.
The former `preview_*` gate credentials are unused while `basicAuthFile = null`.

On the new VPS, `python3 /srv/fotovpsf/tests/health.py` performs read-only
service, valid HTTPS/certificate, public browsing, administrator authentication,
image and data-count checks.
Add `--full` to compare every original against the private import manifest.
Its count baseline describes the imported preview; adjust it after deliberate
user uploads or account changes. `tests/live.py` exercises disposable upload,
moderation, private-image permissions and rejected file types on this preview.
Do not run the mutation suite on the original gallery or over operator work.

To rehearse a backup restore, verify `SHA256SUMS` **from inside the backup
directory**, extract `piwigo-state.tar.gz` into a new private directory, create
an unused MariaDB database and import `piwigo.sql` there. Compare original
hashes against the private import manifest and check album/user/image counts.
Never import a rehearsal over the live database. The archive omits managed
`app` / `local/config/config.inc.php` symlinks and sessions: the target NixOS
module recreates those. It includes private database configuration, so retain
root-only permissions for all copies. Restore `preview-gate.tar.gz` and
`access.json` privately when moving the preview as well.

## Album overview

The home page shows albums containing visible photos directly, newest first.
Up to 48 albums fit on one scrollable page, with lazy-loaded cover images.
The imported year folders remain in the underlying hierarchy, preserving links
and source organization. The theme's query hook retains Piwigo's user-cache and
permission conditions. It orders by the latest visible photo date; imported
albums retain their source year because early files have no EXIF dates and were
recopied in 2016. A small year label distinguishes recurring events without
requiring navigation through year folders. New albums use capture/upload dates.

## Theme checks

The child theme supplies a native Modus blue/orange skin rather than inheriting
the newspaper skin's white controls. Its content-hashed name invalidates the
compiled palette cache; the layout stylesheet also has a content-hashed URL.
Preserve the newline before `</head>` in package substitutions: Piwigo needs
that marker to inject the dynamic thumbnail layout CSS.

Use `tests/browser-audit.js` as a read-only DOM expression through the browser
tool. It checks overflow, white chrome, photo-control bounds/size/icon presence,
popup bounds and contrast, search contrast, menu centering and image loading.
Exercise home, album, photo, metadata, open size/sort menus, running/paused
slideshow, search/results and login at phone, tablet and desktop widths.
Specifically check mobile nested menus and disabled first/last photo controls.
Keep screenshots and audit receipts outside Git. Run `tests/health.py` on the
new VPS and `php tests/gallery-view.php` to check services and overview scope.
