// A small accessible drawer around Piwigo's existing administration menu.
document.addEventListener('DOMContentLoaded', () => {
  const button = document.getElementById('vpsfree-admin-menu');
  const menu = document.getElementById('menubar');
  if (!button || !menu) return;
  const setOpen = (open) => {
    document.body.classList.toggle('vpsfree-admin-menu-open', open);
    button.setAttribute('aria-expanded', String(open));
    button.setAttribute('aria-label', open ? 'Zavřít menu' : 'Otevřít menu');
  };
  button.addEventListener('click', () => setOpen(button.getAttribute('aria-expanded') !== 'true'));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && button.getAttribute('aria-expanded') === 'true') {
      setOpen(false);
      button.focus();
    }
  });
  document.addEventListener('click', (event) => {
    if (!menu.contains(event.target) && !button.contains(event.target)) setOpen(false);
  });
});
