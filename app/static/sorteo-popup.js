(function () {
  var STORAGE_KEY = 'hf-sorteo-popup-dismissed';
  var popup = document.getElementById('sorteo-popup');
  if (!popup) return;

  if (sessionStorage.getItem(STORAGE_KEY) === '1') return;

  var backdrop = popup.querySelector('.modal-backdrop');
  var closeBtn = popup.querySelector('.modal-close');

  function closePopup() {
    popup.classList.remove('open');
    popup.setAttribute('aria-hidden', 'true');
    popup.hidden = true;
    document.body.classList.remove('modal-open');
    sessionStorage.setItem(STORAGE_KEY, '1');
  }

  function openPopup() {
    popup.hidden = false;
    popup.classList.add('open');
    popup.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    closeBtn.focus();
  }

  closeBtn.addEventListener('click', closePopup);
  backdrop.addEventListener('click', closePopup);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && popup.classList.contains('open')) closePopup();
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', openPopup);
  } else {
    openPopup();
  }
})();
