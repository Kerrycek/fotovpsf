# Working on this gallery

- The user authorized porting the original PhotoShow to current PHP on
  `root@172.16.9.28` on 2026-11-01. Work in an isolated preview with copied
  state; preserve the original installation and unrelated hosted websites.
- Keep Piwigo on `root@37.205.8.218` available for comparison. Do not change
  the production proxy or switch the production domain without instruction.
- Store photographs, source archives, account data, hashes, credentials,
  dumps, receipts and browser screenshots outside Git. Never log passwords.
- PhotoShow keeps its native filesystem/XML state; do not add a database.
  Piwigo uses MariaDB/MySQL, never SQLite. Keep gallery services independently
  configurable for later integration alongside the original VPS websites.
- Preserve privacy on direct original/derivative URLs, not only album pages.
- Pin official releases with hashes. Keep executable application code read
  only. Update via Nix; avoid web-writable PHP/theme/plugin directories.
- Check typography, spacing and mobile/desktop rendering in the browser.
- Test upload, member/admin/anonymous roles, direct-file permissions, checksum
  integrity, a consistent backup and an isolated restore before completion.
- Use small imperative commits with rationale; write commit messages to a
  temporary file and commit with `git commit -F`. Do not deploy to production.
