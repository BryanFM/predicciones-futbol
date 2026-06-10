(function () {
  'use strict';

  var STORAGE_KEY = 'hf-cookie-consent';

  function hasConsent() {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'accepted';
    } catch (_) {
      return false;
    }
  }

  function acceptConsent() {
    try {
      localStorage.setItem(STORAGE_KEY, 'accepted');
    } catch (_) {}
    hideBanner();
  }

  function hideBanner() {
    var banner = document.getElementById('cookie-consent');
    if (!banner) return;
    banner.classList.remove('is-visible');
    banner.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('cookie-banner-open');
    setTimeout(function () {
      banner.hidden = true;
    }, 280);
  }

  function showBanner() {
    var banner = document.getElementById('cookie-consent');
    if (!banner) return;
    banner.hidden = false;
    banner.setAttribute('aria-hidden', 'false');
    document.body.classList.add('cookie-banner-open');
    requestAnimationFrame(function () {
      banner.classList.add('is-visible');
    });
  }

  function init() {
    if (hasConsent()) return;

    var banner = document.getElementById('cookie-consent');
    var acceptBtn = document.getElementById('cookie-consent-accept');
    if (!banner || !acceptBtn) return;

    acceptBtn.addEventListener('click', acceptConsent);
    showBanner();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
