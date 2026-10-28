// Read-only DOM audit, evaluated through the browser tool on each QA page.
(() => {
  const errors = [];
  const visible = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
  };
  const rgb = (value) => (value.match(/[\d.]+/g) || []).map(Number);
  const background = (el) => {
    while (el) {
      const c = rgb(getComputedStyle(el).backgroundColor);
      if (c.length === 3 || (c.length > 3 && c[3] > 0.95)) return c;
      el = el.parentElement;
    }
    return [255, 255, 255];
  };
  const luminance = (c) => {
    const linear = c.slice(0, 3).map(v => v / 255).map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
  };
  const contrast = (a, b) => (Math.max(luminance(a), luminance(b)) + 0.05) / (Math.min(luminance(a), luminance(b)) + 0.05);
  if (document.documentElement.scrollWidth > innerWidth + 1) errors.push('Horizontal page overflow');
  for (const selector of ['#menubar', '#imageToolBar', '#imageHeaderBar', '.titrePage']) {
    const el = document.querySelector(selector);
    if (visible(el) && luminance(background(el)) > 0.8) errors.push('Light chrome strip: ' + selector);
  }
  const toolbar = document.querySelector('#imageToolBar');
  if (visible(toolbar)) {
    const bar = toolbar.getBoundingClientRect();
    for (const button of toolbar.querySelectorAll('.pwg-button')) {
      if (!visible(button)) continue;
      const r = button.getBoundingClientRect();
      const popup = button.closest('.actionButtons');
      const inPopup = popup && getComputedStyle(popup).position === 'absolute';
      if (r.height < 39 || r.width < 39) errors.push('Small photo control: ' + (button.title || button.id));
      if (!inPopup && (r.top < bar.top - 1 || r.bottom > bar.bottom + 1 || r.left < bar.left - 1 || r.right > bar.right + 1)) errors.push('Photo control escapes toolbar: ' + (button.title || button.id));
      const icon = button.querySelector('.pwg-icon');
      if (icon && !icon.textContent.trim() && ['none', 'normal', '""'].includes(getComputedStyle(icon, '::before').content) && getComputedStyle(icon).backgroundImage === 'none') errors.push('Empty photo icon: ' + (button.title || button.id));
      if (icon && !button.classList.contains('pwg-state-disabled') && contrast(rgb(getComputedStyle(icon).color), background(button)) < 3) errors.push('Low-contrast photo icon: ' + (button.title || button.id));
    }
  }
  for (const box of document.querySelectorAll('.switchBox')) {
    if (!visible(box)) continue;
    const r = box.getBoundingClientRect();
    if (r.left < -1 || r.right > innerWidth + 1 || r.top < -1 || r.bottom > innerHeight + 1) errors.push('Popup escapes viewport: ' + box.id);
    const link = box.querySelector('a');
    if (link && contrast(rgb(getComputedStyle(link).color), background(link)) < 4.5) errors.push('Low-contrast popup: ' + box.id);
  }
  const menu = document.querySelector('#menubar');
  if (innerWidth > 1000 && visible(menu)) {
    const centers = [...menu.querySelectorAll(':scope > dl')].filter(visible).map(e => { const r = e.getBoundingClientRect(); return r.top + r.height / 2; });
    if (centers.length && Math.max(...centers) - Math.min(...centers) > 1) errors.push('Navigation centers differ');
    const search = menu.querySelector('#qsearchInput');
    if (visible(search) && search.getBoundingClientRect().left < menu.getBoundingClientRect().left + menu.getBoundingClientRect().width / 2) errors.push('Search is not on the right');
  }
  const main = document.querySelector('#theMainImage');
  if (main && (!main.complete || !main.naturalWidth)) errors.push('Main photo has not loaded');
  return {page: document.location.href, width: innerWidth, height: innerHeight, errors};
})()
