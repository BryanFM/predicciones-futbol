(function () {
  const panel = document.getElementById('grupos');
  if (!panel) return;

  const toggle = panel.querySelector('.groups-toggle');
  const body = document.getElementById('groups-body');
  if (!toggle || !body) return;

  function setOpen(open) {
    panel.classList.toggle('is-open', open);
    panel.classList.toggle('is-collapsed', !open);
    body.hidden = !open;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  setOpen(false);

  toggle.addEventListener('click', () => {
    setOpen(!panel.classList.contains('is-open'));
  });

  function openFromHash() {
    if (window.location.hash === '#grupos') {
      setOpen(true);
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  openFromHash();
  window.addEventListener('hashchange', openFromHash);
})();
