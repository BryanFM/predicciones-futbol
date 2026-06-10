(function () {
  'use strict';

  var STORAGE_KEY = 'hf-cookie-consent';

  function getStoredConsent() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (_) {
      return null;
    }
  }

  function setConsent(value) {
    try {
      localStorage.setItem(STORAGE_KEY, value);
    } catch (_) {}
  }

  function getAnalyticsIds() {
    var banner = document.getElementById('cookie-consent');
    if (!banner) return { ga: '', clarity: '' };
    return {
      ga: banner.dataset.gaId || '',
      clarity: banner.dataset.clarityId || '',
    };
  }

  function loadGoogleAnalytics(measurementId) {
    if (!measurementId || window.__hfGaLoaded) return;
    window.__hfGaLoaded = true;

    var script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(measurementId);
    document.head.appendChild(script);

    window.dataLayer = window.dataLayer || [];
    function gtag() {
      window.dataLayer.push(arguments);
    }
    window.gtag = gtag;
    gtag('js', new Date());
    gtag('config', measurementId, { anonymize_ip: true });
  }

  function loadClarity(projectId) {
    if (!projectId || window.__hfClarityLoaded) return;
    window.__hfClarityLoaded = true;

    window.clarity =
      window.clarity ||
      function () {
        (window.clarity.q = window.clarity.q || []).push(arguments);
      };
    var script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.clarity.ms/tag/' + encodeURIComponent(projectId);
    document.head.appendChild(script);
  }

  function loadAnalytics() {
    var ids = getAnalyticsIds();
    loadGoogleAnalytics(ids.ga);
    loadClarity(ids.clarity);
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

  function saveEssentialOnly() {
    setConsent('essential');
    hideBanner();
  }

  function saveAcceptAll() {
    setConsent('all');
    loadAnalytics();
    hideBanner();
  }

  function init() {
    var consent = getStoredConsent();
    if (consent === 'all') {
      loadAnalytics();
      return;
    }
    if (consent === 'essential') return;

    var banner = document.getElementById('cookie-consent');
    var essentialBtn = document.getElementById('cookie-consent-essential');
    var acceptBtn = document.getElementById('cookie-consent-accept');
    if (!banner || !essentialBtn || !acceptBtn) return;

    essentialBtn.addEventListener('click', saveEssentialOnly);
    acceptBtn.addEventListener('click', saveAcceptAll);
    showBanner();
  }

  window.hfCookieConsent = {
    get: getStoredConsent,
    loadAnalytics: loadAnalytics,
    reopen: showBanner,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
