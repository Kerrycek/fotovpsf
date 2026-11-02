/* Real Playwright coverage for the named non-production PhotoShow gallery.
 * NODE_PATH must point at an installed official Playwright package. Credentials,
 * synthetic images, screenshots and reports must stay outside this repository.
 * Create receipt-owned roles with browser-fixtures.py first; clean up separately.
 */
const { chromium, webkit } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const base = 'https://foto.crucio.cz/kra/';
const directory = process.env.PHOTOSHOW_QA_PRIVATE;
if (!directory || directory.includes('/git/')) throw Error('Private output directory required');

(async () => {
  const fixtures = JSON.parse(await fs.readFile(path.join(directory, 'browser-audit-fixtures.json')));
  const run = fixtures.album + Date.now();
  const report = { date: new Date().toISOString(), target: base, fixture: run, checks: [] };
  const check = async (name, fn) => {
    try { await fn(); report.checks.push({ name, result: 'PASS' }); console.log('PASS', name); await fs.writeFile(path.join(directory,'browser-current-progress.json'),JSON.stringify(report,null,2),{mode:0o600}); }
    catch (error) { report.checks.push({ name, result: 'FAIL', error: error.message }); console.log('FAIL', name); await fs.writeFile(path.join(directory,'browser-last-failure.txt'),error.message,{mode:0o600}); await fs.writeFile(path.join(directory,'browser-current-progress.json'),JSON.stringify(report,null,2),{mode:0o600}); }
  };
  const browser = await (process.env.PHOTOSHOW_QA_ENGINE === 'webkit' ? webkit : chromium).launch({ headless: true });
  const contexts = [];
  const create = async () => { const c = await browser.newContext({ viewport: { width: 1280, height: 900 } }); c.setDefaultTimeout(10000); contexts.push(c); return c; };
  const admin = await create(), member = await create(), uploader = await create(), guest = await create();
  const clients = { admin, member, uploader, guest };
  const tokens = new Map();
  const request = async (context, query = '', form) => {
    const response = await context.request.fetch(base + query, form === undefined ? {} : { method: 'POST', form: { ...form, csrf: tokens.get(context) || '' } });
    const body = await response.body();
    const token = body.toString().match(/name="photoshow-csrf" content="([a-f0-9]+)"/);
    if (token) tokens.set(context, token[1]);
    return { status: response.status(), body, headers: response.headers() };
  };
  const login = async (context, account) => {
    await request(context, '?t=Login');
    const response = await request(context, '?t=Login', { login: account.username, password: account.password });
    assert.equal(response.status, 200); assert(!response.body.includes('Wrong password'));
  };
  const q = value => encodeURIComponent(value);
  const folder = (parent, name) => request(admin, '?a=Upl', { path: parent, newdir: name, inherit: '1' });
  try {
    for (const role of ['admin', 'member', 'uploader']) await login(clients[role], fixtures.accounts[role]);
    await check('create isolated fixture album', async () => assert.equal((await folder('', run)).status, 200));
    for (const name of ['Public', 'Private', 'Destination']) await folder(run, name);
    const page = await admin.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const go = async query => { const r = await page.goto(base + query); assert.equal(r.status(), 200); await page.locator('body').waitFor({state:'attached'}); };
    const openPanel = async () => {
      if (!(await page.locator('#menuright').getAttribute('class') || '').includes('active')) {
        await page.locator('a[href="#menuright"]').click();
      }
      await page.getByRole('button', { name: 'Upload images here', exact: true }).waitFor({ state: 'visible' });
    };
    await check('browser login through native form', async () => {
      const c = await create(), p = await c.newPage();
      await p.goto(base + '?t=Login');
      await p.getByPlaceholder('Login', { exact: true }).fill(fixtures.accounts.admin.username);
      await p.getByPlaceholder('Password', { exact: true }).fill(fixtures.accounts.admin.password);
      await p.locator('form input[type=submit]').click();
      await p.locator('#menuright').getByText(fixtures.accounts.admin.username, { exact: false }).waitFor();
      assert.equal((await request(c, '?t=Adm')).status, 200);
    });
    await check('create nested album with native UI', async () => {
      await go('?f=' + q(run + '/Public')); await openPanel();
      await page.locator('#foldername').fill('Nested');
      await page.locator('form').filter({ has: page.locator('#foldername') }).getByRole('button', { name: 'Create', exact: true }).click();
      await page.waitForURL(url => url.searchParams.has('f') && !url.searchParams.has('a'));
      assert((await page.locator('h1').innerText()).includes('Nested'));
    });
    await check('multiple-image upload auto submits from file chooser', async () => {
      await go('?f=' + q(run + '/Public')); await openPanel();
      const chooserEvent = page.waitForEvent('filechooser');
      await page.getByRole('button', { name: 'Upload images here', exact: true }).click();
      const chooser = await chooserEvent;
      assert(chooser.isMultiple());
      const image = await fs.readFile(path.join(directory, 'photoshow-upload-test.jpg'));
      await Promise.all([page.waitForNavigation(), chooser.setFiles([{ name: 'first.jpg', mimeType: 'image/jpeg', buffer: image }, { name: 'second.jpg', mimeType: 'image/jpeg', buffer: image }])]);
      assert((await page.locator('body').innerText()).includes('Public'));
      const r = await request(guest, '?t=Big&f=' + q(run + '/Public/first.jpg'));
      assert.equal(r.status, 200); assert(r.body.equals(image));
    });
    await check('duplicate upload preserves original and allocates a new name', async () => {
      await go('?f=' + q(run + '/Public')); await openPanel();
      const chooserEvent = page.waitForEvent('filechooser');
      await page.getByRole('button', { name: 'Upload images here', exact: true }).click();
      const chooser = await chooserEvent;
      const image = await fs.readFile(path.join(directory, 'photoshow-upload-test.jpg'));
      await Promise.all([page.waitForNavigation(), chooser.setFiles({ name: 'first.jpg', mimeType: 'image/jpeg', buffer: image })]);
      assert.equal((await request(guest, '?t=Big&f=' + q(run + '/Public/first-1.jpg'))).status, 200);
    });
    await check('album images, next/previous and keyboard', async () => {
      await go('?f=' + q(run + '/Public'));
      await page.locator('.sectionimg .item a').first().click();
      await page.locator('.image_panel').waitFor({ state: 'visible' });
      await page.waitForFunction(() => [...document.querySelectorAll('.image_panel img')].some(i => i.complete && i.naturalWidth > 0));
      const before = await page.url(); await page.keyboard.press('ArrowRight');
      await page.waitForFunction(previous => location.href !== previous, before);
      await page.keyboard.press('ArrowLeft');
      await page.waitForFunction(previous => location.href === previous, before);
      assert(await page.locator('.image_panel').isVisible());
    });
    await check('slideshow start, pause, resume and stop', async () => {
      await go('?f=' + q(run + '/Public/first.jpg'));
      await page.locator('#image_bar #slideshow a').click();
      await page.locator('#image_bar #pause a').waitFor({ state: 'visible' });
      if (await page.evaluate(() => document.fullscreenEnabled || document.webkitFullscreenEnabled)) await page.waitForFunction(() => !!(document.fullscreenElement || document.webkitFullscreenElement));
      const initialFullscreen = await page.evaluate(() => !!(document.fullscreenElement || document.webkitFullscreenElement));
      await page.locator('#image_bar #pause a').click();
      await page.locator('#image_bar #play a').waitFor({ state: 'visible' });
      await page.locator('#image_bar #play a').click();
      if (initialFullscreen) assert(await page.evaluate(() => !!(document.fullscreenElement || document.webkitFullscreenElement)), 'resume retains fullscreen');
      await page.locator('#image_bar #stop a').click();
      await page.locator('#image_bar #slideshow a').waitFor({ state: 'visible' });
      await page.waitForFunction(() => !(document.fullscreenElement || document.webkitFullscreenElement));
    });
    await check('native browser original and ZIP downloads', async () => {
      await go('?f=' + q(run + '/Public/first.jpg'));
      const downloadEvent = page.waitForEvent('download');
      await page.locator('#image_bar #get a').click();
      const download = await downloadEvent;
      const filename = path.join(directory, 'audit-download-original.jpg');
      await download.saveAs(filename);
      assert((await fs.readFile(filename)).equals(await fs.readFile(path.join(directory, 'photoshow-upload-test.jpg'))));
      await go('?f=' + q(run + '/Public'));
      await page.locator('a[href="#menuright"]').click();
      const zipEvent = page.waitForEvent('download');
      await page.locator('#menuright a[href^="?t=Zip"]').click();
      const zip = await zipEvent;
      const zipfile = path.join(directory, 'audit-download-album.zip'); await zip.saveAs(zipfile);
      assert.equal((await fs.readFile(zipfile)).subarray(0, 2).toString(), 'PK');
    });
    await check('comment text and escaping through native browser form', async () => {
      await go('?f=' + q(run + '/Public/first.jpg'));
      await page.locator('a[href="#menuright"]').click();
      await page.locator('#content').fill('Audit <img src=x onerror="window.auditXss=1"> & český komentář');
      await page.getByRole('button', { name: 'Post Comment', exact: true }).click();
      await page.getByText('Audit <img src=x onerror="window.auditXss=1"> & český komentář', { exact: false }).waitFor();
      assert.equal(await page.evaluate(() => window.auditXss), undefined);
    });
    await check('desktop and mobile layout, loaded synthetic images', async () => {
      for (const width of [1280, 768, 390, 320]) {
        await page.setViewportSize({ width, height: 900 }); await go('?f=' + q(run + '/Public'));
        const metrics = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth, broken: [...document.images].filter(i => i.complete && !i.naturalWidth).length }));
        assert(metrics.scroll <= metrics.width + 1, JSON.stringify(metrics)); assert.equal(metrics.broken, 0);
      }
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.screenshot({ path: path.join(directory, 'photoshow-audit-synthetic-desktop.png') });
    });
    await check('all native administration and profile pages render', async () => {
      for (const a of ['Abo', 'Sta', 'VTk', 'Set', 'Acc', 'EdA']) { await go('?t=Adm&a=' + a); assert(!(await page.locator('body').innerText()).includes('Požadavek se nepodařilo')); }
      await go('?t=Acc');
    });
    await check('native settings form saves unchanged displayed preferences', async () => {
      await go('?t=Adm&a=Set');
      const title = await page.title();
      await Promise.all([page.waitForNavigation(), page.locator('form[action="?t=Adm&a=Set"] input[type=submit]').click()]);
      assert.equal(await page.title(), title);
      assert(await page.locator('form[action="?t=Adm&a=Set"]').isVisible());
    });
    await check('native delete removes only its synthetic duplicate photo', async () => {
      await go('?f=' + q(run + '/Public/first-1.jpg'));
      await page.locator('a[href="#menuright"]').click();
      await Promise.all([page.waitForNavigation(), page.locator('form[action="?a=Del"] button[type=submit]').click()]);
      assert.equal((await request(admin, '?t=Big&f=' + q(run + '/Public/first-1.jpg'))).status, 404);
      assert.equal((await request(admin, '?t=Big&f=' + q(run + '/Public/first.jpg'))).status, 200);
    });
    await check('uploader can add an album, member cannot upload', async () => {
      assert.equal((await request(uploader, '?a=Upl', { path: run, newdir: 'UploaderAlbum', inherit: '1' })).status, 200);
      assert.equal((await request(member, '?a=Upl', { path: run, newdir: 'DeniedAlbum', inherit: '1' })).status, 403);
    });
    await check('anonymous and member deny every privileged endpoint', async () => {
      for (const c of [guest, member]) for (const query of ['?t=Adm', '?j=Acc', '?j=Jud']) assert.equal((await request(c, query)).status, 403);
      assert.equal((await request(guest, '?t=Acc')).status, 403);
      for (const c of [guest, member, uploader]) for (const action of ['Mov', 'Del', 'AAc', 'ADe', 'GEd', 'Set']) assert.equal((await request(c, '?t=Adm&a=' + action, {})).status, 403);
    });
    await check('CSRF, GET mutations, source and traversal boundaries', async () => {
      for (const query of ['?t=Pri&f=' + q(run), '?t=Logout', '?a=Del']) assert.equal((await request(admin, query)).status, 405);
      const r = await admin.request.post(base + '?a=Del', { form: { del: run } }); assert.equal(r.status(), 403);
      for (const query of ['?t=Big&f=..%2Fgenerated%2FConf%2Faccounts.xml', '?t=Big&f=%2Fetc%2Fpasswd']) assert.equal((await request(guest, query)).status, 400);
      for (const resource of ['config.php', 'src/classes/Account.php', 'generated/Conf/accounts.xml', '.git/config']) assert.equal((await request(guest, resource)).status, 404);
    });
    await check('private album denied in all originals, thumbnails and AJAX panels', async () => {
      assert.equal((await request(admin, '?t=Pri&f=' + q(run + '/Public'), {})).status, 200);
      for (const c of [guest, member, uploader]) for (const t of ['Page', 'Img', 'Big', 'BDl', 'Thb', 'Zip']) assert.equal((await request(c, '?t=' + t + '&f=' + q(run + '/Public/first.jpg'))).status, 403);
      for (const j of ['Inf', 'Pan', 'Pag']) assert.equal((await request(guest, '?j=' + j + '&f=' + q(run + '/Public/first.jpg'))).status, 403);
      assert(!(await request(guest, '?t=Rss')).body.includes(run + '/Public'));
      assert.equal((await request(uploader, '?a=Upl', { path: run, newdir: 'Public', inherit: '1' })).status, 403);
      assert.equal((await request(member, '?t=Com&f=' + q(run + '/Public/first.jpg'), { content: 'Denied comment', login: fixtures.accounts.member.username })).status, 403);
      assert(!(await request(admin, '?f=' + q(run + '/Public/first.jpg'))).body.includes('Denied comment'));
    });
    await check('moving private album preserves ACL and cached-photo privacy', async () => {
      const r = await request(admin, '?a=Mov', { pathFrom: run + '/Public', pathTo: run + '/Destination', move: 'directory' });
      assert.equal(r.status, 200);
      for (const t of ['Big', 'Thb', 'Page']) assert.equal((await request(guest, '?t=' + t + '&f=' + q(run + '/Destination/Public/first.jpg'))).status, 403);
    });
    await check('rename preserves private ACL and comments', async () => {
      assert.equal((await request(admin, '?a=Mov', { pathFrom: run + '/Destination/Public', pathTo: 'Renamed', move: 'rename' })).status, 200);
      assert.equal((await request(guest, '?t=Big&f=' + q(run + '/Destination/Renamed/first.jpg'))).status, 403);
      await go('?f=' + q(run + '/Destination/Renamed/first.jpg'));
      assert((await page.locator('#comments').innerText()).includes('český komentář'));
    });
    await check('guest share token grants only its album and revokes existing sessions', async () => {
      await request(admin, '?t=Pri&f=' + q(run + '/Private'), {});
      await request(admin, '?t=Pri&f=' + q(run + '/Destination/Renamed'), {});
      const r = await request(admin, '?t=CTk&f=' + q(run + '/Private'), {});
      const token = r.body.toString().match(/[?&](?:amp;)?token=([a-f0-9]{64})/);
      assert(token, 'share link exists');
      const visitor = await create();
      assert.equal((await request(visitor, '?f=' + q(run + '/Private') + '&token=' + token[1])).status, 200);
      assert.equal((await request(visitor, '?f=' + q(run + '/Destination/Renamed'))).status, 403);
      await request(admin, '?t=Adm&a=DTk', { tokenkey: token[1] });
      assert.equal((await request(visitor, '?f=' + q(run + '/Private'))).status, 403);
    });
    await check('password change revokes a previous member session', async () => {
      const original = fixtures.accounts.member;
      const replacement = crypto.randomBytes(32).toString('hex');
      await request(admin, '?t=Adm&a=Acc', { edit: '1', login: original.username, password: replacement, name: '', email: '', language: '' });
      try { assert.equal((await request(member, '?t=Acc')).status, 403); }
      finally { await request(admin, '?t=Adm&a=Acc', { edit: '1', login: original.username, password: original.password, name: '', email: '', language: '' }); }
    });
    await check('account deletion and recreation cannot resurrect old sessions', async () => {
      await login(member, fixtures.accounts.member);
      const second = await create(); await login(second, fixtures.accounts.member);
      assert.equal((await request(admin, '?t=Adm&a=ADe', { name: fixtures.accounts.member.username })).status, 200);
      assert.equal((await request(member, '?t=Acc')).status, 403);
      assert.equal((await request(admin, '?t=Adm&a=AAc', { login: fixtures.accounts.member.username, password: fixtures.accounts.member.password, verif: fixtures.accounts.member.password })).status, 200);
      assert.equal((await request(second, '?t=Acc')).status, 403);
      await login(member, fixtures.accounts.member);
      assert.equal((await request(member, '?t=Acc')).status, 200);
    });
    await check('unsafe global settings are rejected without changing them', async () => {
      for (const values of [{ name: 'Audit\nInjected=1' }, { name: 'Audit', user_theme: '../../' }, { name: 'Audit', loc: '../../' }, { name: 'Audit', thumbs_size: '999999999' }, { name: 'Audit', encode_video: 'on' }]) assert.equal((await request(admin, '?t=Adm&a=Set', values)).status, 400);
    });
    await check('Unicode and ampersand album paths work with guest sharing', async () => {
      const target = run + '/Zkouška & fotky';
      await folder(run, 'Zkouška & fotky'); await request(admin, '?t=Pri&f=' + q(target), {});
      const r = await request(admin, '?t=CTk&f=' + q(target), {});
      const match = r.body.toString().match(/[?&](?:amp;)?token=([a-f0-9]{64})/); assert(match);
      const visitor = await create(); assert.equal((await request(visitor, '?f=' + q(target) + '&token=' + match[1])).status, 200);
      await request(admin, '?t=Adm&a=DTk', { tokenkey: match[1] });
      assert.equal((await request(visitor, '?f=' + q(target))).status, 403);
    });
    await check('browser has no JavaScript errors', async () => assert.deepEqual(errors, []));
    await check('browser logout removes privileged access', async () => {
      await go('?f=' + q(run));
      await page.locator('a[href="#menuright"]').click();
      await page.locator('#menuright').getByText(fixtures.accounts.admin.username, { exact: false }).click();
      await page.locator('a[href="?t=Logout"]').click();
      assert.equal((await request(admin, '?t=Adm')).status, 403);
    });
  } finally {
    await fs.writeFile(path.join(directory, 'photoshow-browser-audit-' + (process.env.PHOTOSHOW_QA_ENGINE || 'chromium') + '.json'), JSON.stringify(report, null, 2), { mode: 0o600 });
    for (const c of contexts) await c.close(); await browser.close();
  }
  const failures = report.checks.filter(c => c.result === 'FAIL');
  console.log(`${report.checks.length - failures.length}/${report.checks.length} checks passed`);
  process.exitCode = failures.length ? 1 : 0;
})().catch(async error => { await fs.writeFile(path.join(directory, 'browser-harness-error.txt'), String(error), {mode:0o600}); console.error('Browser harness failed; inspect private report, no credentials printed'); process.exitCode = 1; });
