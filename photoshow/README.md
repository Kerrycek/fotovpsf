# Original PhotoShow on PHP 8.5

This is a separate alternative to the Piwigo deployment. It keeps PhotoShow's
native filesystem albums, XML accounts/groups/permissions and original URLs.
It does not use a database. The existing Piwigo module remains unchanged.

The package pins the public PhotoShow revision
`3d15c06155af6c2340954d4b5a589b19bebf4aac` (the original 2014 installation),
normalizes its old text encodings and applies a reviewed patch. The original
three vpsFree branding changes are retained. Upstream GPL notices remain in the
packaged source. Private configuration, photographs and accounts never enter Nix
sources or Git.

## Compatibility and behavior

- PHP 8.5, including object-based GD images, static method calls, exception
  properties and explicit view-model properties. All diagnostics stay enabled;
  errors are logged privately rather than displayed to visitors.
- Passwords use Argon2id. Existing SHA1 passwords, including the historical
  magic-quotes variant, are verified and upgraded on successful login. Existing
  account passwords are not reset. Legacy account-key login is disabled.
- Existing album hierarchy, files and inherited access rules are retained.
  The homepage and menu show photo albums directly, newest year first, without
  presenting year-only containers as albums. Private content cannot determine
  public album ordering or cover images.
- The original upload endpoint accepts multiple genuine JPEG/PNG/GIF files,
  validates image type and dimensions, confines names/paths, and uses native
  browser file selection instead of the obsolete Blueimp uploader. Maximum
  image size is 50 megapixels, 48 MiB per file and 64 MiB per request (including
  multipart overhead). Native POST/redirect/GET avoids resubmission on refresh.
- Mutations require a session CSRF token and POST. Admin-only actions and
  account/rights panels enforce their role. Uploaders cannot rename/delete
  other people's photographs. Original/cached image routes check access on
  every request; downloads are not publicly cacheable.
- ZIP downloads use PHP's ZipArchive instead of a shell command. RSS is rebuilt
  from currently public content so changing an album to private also removes
  it from the feed.
- This compatibility preview is not approval to expose the old application to
  the Internet. Before production, review remaining legacy browser libraries,
  login throttling, account/XML write concurrency, TLS/proxy integration and
  scheduled off-host backups. Piwigo's separate security audit does not certify
  this PhotoShow port.

## Isolated preview on the shared original host

The preview listens only on `127.0.0.1:18085`, with its own Nginx, PHP-FPM,
DynamicUser and `/var/lib/photoshow-preview` state. It cannot read the original
`/var/www` tree or databases. Application code is immutable in the Nix store.
The shared host's Nginx/PHP services and production proxy are not reloaded.

Build from a checkout outside the original website tree:

```sh
python3 photoshow/build-preview.py
```

The script uses the existing `flake.lock` nixpkgs revision and creates persistent
Nix GC roots for the application and tools under `/srv/photoshow-php85-*`.
It does not switch the host's NixOS configuration. If Python is not installed
on the host, first build `tools.nix` using the same pinned nixpkgs and use its
`bin/python3`.

For the first deployment only, run `seed-preview.py` as root. It creates a
private checkpoint and source manifest, copies the original gallery into the
separate state directory, verifies all original photo checksums, and disables
preview self-registration. It refuses to replace an existing preview state.
Do not run it again over user edits.

`run-preview.py` is a standalone supervisor. For a temporary preview, copy
`photoshow-preview.service` into `/run/systemd/system/`, reload the unit manager,
and start **only** `photoshow-preview.service`. This temporary registration
expires on host reboot. To make the service persistent through the managed
configuration later, import `nixosModules.photoshowPreview` and enable
`services.vpsfreePhotoShowPreview.enable`. Seeded state is required in either
case; the module never imports or replaces existing state automatically.

View from the operator's Mac through an SSH tunnel:

```sh
ssh -N -L 127.0.0.1:18085:127.0.0.1:18085 root@172.16.9.28
```

Then open `http://127.0.0.1:18085/`. Existing original accounts remain usable.
An optional separate preview administrator can be created with
`create-preview-admin.py`; its random credentials are saved root-only outside
Git. The script never resets an existing account or changes original users.

## Validation and checkpoints

Use `/srv/photoshow-php85-tools/bin/php` and `bin/python3` for the standalone
preview. Run against the **preview only**, never an original/live website:

```sh
php photoshow/tests.php /srv/photoshow-php85-app
python3 photoshow/tests-live.py
python3 photoshow/tests-content.py
python3 photoshow/backup-preview.py
```

The live suite creates and removes only its own synthetic accounts/albums. It
checks native login, password migration, uploads, private/cached URLs, CSRF,
role boundaries, traversal rejection, ZIP/RSS and admin pages. The content suite
compares the original source manifest, every photo copy, HTTP originals,
thumbnails and metadata. Its historical 476-photo baseline is a diagnostic;
never remove/restore live user data merely because a count changes.

The checkpoint script pauses only the preview, archives native photo/generated
state (excluding sessions/logs), writes `SHA256SUMS`, verifies it and restores
into a new private temporary directory. It compares every restored file and
always resumes a previously running preview. It never restores over live state.
Checkpoints remain root-only under `/var/backups/photoshow-port`; configure
retention and off-host copies before production use.

To remove just the temporary runtime, stop `photoshow-preview.service`, remove
its unit from `/run/systemd/system/`, and reload the unit manager. Preserve state
and checkpoints for review. Do not boot an older PhotoShow against XML accounts
that now contain Argon2id hashes; code and state must stay compatible.
