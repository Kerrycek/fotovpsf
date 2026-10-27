# Working on this gallery

- Original server `root@172.16.9.28` is READ ONLY. Never modify its files,
  services or database. Never run the archived PhotoShow application.
- All development, imports, uploads and test mutations belong on the new
  `root@37.205.8.218` VPS. Production proxy and cutover are outside scope.
- Store photographs, source archives, account data, hashes, credentials,
  dumps, receipts and browser screenshots outside Git. Never log passwords.
- Use MariaDB/MySQL, never SQLite. Keep gallery services independently
  configurable for later integration alongside the original VPS websites.
- Preserve privacy on direct original/derivative URLs, not only album pages.
- Pin official releases with hashes. Keep executable application code read
  only. Update via Nix; avoid web-writable PHP/theme/plugin directories.
- Check typography, spacing and mobile/desktop rendering in the browser.
- Test upload, member/admin/anonymous roles, direct-file permissions, checksum
  integrity, a consistent backup and an isolated restore before completion.
- Use small imperative commits with rationale; write commit messages to a
  temporary file and commit with `git commit -F`. Do not deploy to production.
