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
  The original homepage and year tree, ordering, colors, fonts and core styles
  are retained. The logical root label remains `fotky_galerie` even though the
  isolated data copy is stored under a different physical path.
- The original upload endpoint accepts multiple genuine JPEG/PNG/GIF files,
  validates image type and dimensions, confines names/paths, and uses native
  browser file selection instead of the obsolete Blueimp uploader. The original
  gray dropzone appearance and automatic upload after selection are retained. Maximum
  image size is 50 megapixels, 48 MiB per file and 64 MiB per request (including
  multipart overhead). Native POST/redirect/GET avoids resubmission on refresh.
- Mutations require a session CSRF token and POST. Admin-only actions and
  account/rights panels enforce their role. Uploaders cannot rename/delete
  other people's photographs. Original/cached image routes check access on
  every request; downloads are not publicly cacheable.
- ZIP downloads use PHP's ZipArchive instead of a shell command. RSS is rebuilt
  from currently public content so changing an album to private also removes
  it from the feed.
- Public mounting uses the existing TLS host, a canonical HTTPS URL, a
  path-scoped Secure/HttpOnly session and trusted edge-provided client addresses.
  Five source-address failures are allowed, refilling one credit per 30 seconds;
  successful login refunds only its own reservation. IPv6 shares a /64 bucket.
- State-changing requests take one exclusive write lock. XML is replaced
  atomically so readers cannot observe partially written credentials or ACLs.
  Readers share that lock while serving a response; photo moves carry their
  native ACL/comment metadata and preserve inherited rights at the destination.
  Moving/deleting an album revokes its old share links rather than allowing
  those links to expose a later album reusing the same path.
- Sessions are bound to the current password verifier, with a 30-minute idle
  timeout and 12-hour absolute lifetime. Changing a password or deleting and
  recreating a username invalidates existing logins. New passwords require at
  least 12 characters. Existing passwords remain usable.
- After deploying wrapper verification and taking a consistent checkpoint,
  root may run `python3 photoshow/migrate-passwords.py` once. This replaces
  stored bare SHA1 verifiers with salted Argon2id wrappers, preserving existing
  passwords. Successful login replaces the wrapper with direct Argon2id.
  Historical private checkpoints still contain historical verifiers.
- Settings reject INI line injection, invalid theme/language paths and unbounded
  thumbnail sizes. Shell process functions are disabled. This deployment accepts
  JPEG/PNG/GIF photos; the obsolete shell-based video encoder is unavailable.
- The browser uses pinned official jQuery 4.0.0 and Migrate 4.0.2. Unused jQuery
  UI and Blueimp upload libraries are removed, without changing the core CSS.
  The old scrolling helper no longer relies on the removed browser sniffing API.
- Before a production-domain cutover, review off-host backups, retention and
  operator accounts. The separate Piwigo audit does not certify this application.

## Public mount beside Piwigo

The deployed alternative is `https://foto.crucio.cz/kra/` on the test VPS. The
module is enabled persistently in `hosts/foto-test.nix`; `/kra` redirects to
`/kra/`, its assets/forms stay beneath that prefix, and the main Piwigo gallery
continues to use `/`. Both applications keep separate state and sessions.

`services.vpsfreePhotoShowPreview.virtualHost` selects an existing TLS virtual
host and `mountPath` selects a path without a trailing slash. A null virtualHost
keeps the original loopback-only mode. Seed the private native state copy before
activating the module; no installer or import runs automatically.

The daily `photoshow-backup.timer` runs at 03:35–03:40 Prague time, separately
from Piwigo's database backup. It verifies an isolated restore and keeps all
checkpoints. No retention deletion is configured. This server backup timer is
unrelated to the cancelled work-monitor automation.

## Optional loopback preview on the shared original host

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

Then open `http://127.0.0.1:18085/`. This older temporary preview is stopped once
its state has been copied to `/kra`; do not restart it for concurrent edits.
Existing original accounts remain usable in the copied gallery.
An optional separate preview administrator can be created with
`create-preview-admin.py`; its random credentials are saved root-only outside
Git. The script never resets an existing account or changes original users.

## Validation and checkpoints

Use `/srv/photoshow-php85-tools/bin/php` and `bin/python3` for the standalone
preview. Run against the **preview only**, never an original/live website:

```sh
php photoshow/tests.php /srv/photoshow-php85-app
PHOTOSHOW_TEST_URL=https://foto.crucio.cz/kra/ python3 photoshow/tests-live.py
PHOTOSHOW_TEST_URL=https://foto.crucio.cz/kra/ python3 photoshow/tests-content.py --copy-only
python3 photoshow/backup-preview.py
python3 photoshow/tests-public.py
```

The public test spends the test VPS's own login-failure budget, verifies that
spoofed forwarding headers cannot bypass it, waits for the real refill, and
checks a successful login without deleting/resetting limiter state. Run it from
the test VPS, not an operator's shared network.

The service reports readiness only after its Nginx and PHP have served a page,
so backup/restart completion does not precede the first usable HTTP response.

The live suite creates and removes only its own synthetic accounts/albums. It
checks native login, password migration, uploads, private/cached URLs, CSRF,
role boundaries, traversal rejection, ZIP/RSS and admin pages. The content suite
compares the original source manifest, every photo copy, HTTP originals,
thumbnails and metadata. Its historical 476-photo baseline is a diagnostic;
never remove/restore live user data merely because a count changes.

`tests-browser.cjs` uses official Playwright in Chromium and WebKit, with separate
browser contexts for admin/member/uploader/guest. It tests native forms and file
choosers, multiple/duplicate uploads, downloads, keyboard navigation, fullscreen
presentation, comments, responsive layouts, account/session revocation, direct
private URLs and native ACL metadata through moves/renames. Its JSON reports and
screenshots contain fixture details and must remain outside Git.

Create test-only role accounts with `browser-fixtures.py create` on the named
preview, capturing stdout directly into a private mode-0600
`browser-audit-fixtures.json` on the Mac. Set `PHOTOSHOW_QA_PRIVATE` to that private
directory, containing a synthetic `photoshow-upload-test.jpg`, then run:

```sh
NODE_PATH=/path/to/node_modules node photoshow/tests-browser.cjs
PHOTOSHOW_QA_ENGINE=webkit NODE_PATH=/path/to/node_modules node photoshow/tests-browser.cjs
```

After inspecting results, run `browser-fixtures.py cleanup <synthetic-image-sha256>`
on the preview. It removes only receipt-owned roles and timestamped fixture
albums, refuses unexpected photo contents, and preserves unrelated XML entries.
The helper refuses to create another receipt until the old run is cleaned up.

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
