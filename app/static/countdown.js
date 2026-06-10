(function () {
  function pad(n) {
    return String(n).padStart(2, '0');
  }

  function tick(el) {
    const target = Number(el.dataset.targetMs);
    if (!target) return;

    const diff = target - Date.now();
    const done = el.querySelector('.countdown-done');
    const units = el.querySelector('.countdown-units');

    if (diff <= 0) {
      if (units) units.classList.add('hidden');
      if (done) done.classList.remove('hidden');
      return;
    }

    const secs = Math.floor(diff / 1000);
    const days = Math.floor(secs / 86400);
    const hours = Math.floor((secs % 86400) / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    const s = secs % 60;

    const set = (sel, val) => {
      const node = el.querySelector(sel);
      if (node) node.textContent = days > 0 && sel === '.cd-hours' ? pad(val) : (days > 0 ? pad(val) : pad(val));
    };

    el.querySelector('.cd-days').textContent = days;
    el.querySelector('.cd-hours').textContent = pad(hours);
    el.querySelector('.cd-mins').textContent = pad(mins);
    el.querySelector('.cd-secs').textContent = pad(s);
  }

  function init() {
    document.querySelectorAll('.countdown[data-target-ms]').forEach((el) => {
      tick(el);
      setInterval(() => tick(el), 1000);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
