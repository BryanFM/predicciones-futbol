(function () {
  'use strict';

  const DEFAULT_BATCH = 12;
  const MEDIA_ROOT_MARGIN = '160px 0px';
  const LIST_ROOT_MARGIN = '280px 0px';

  let mediaObserver;

  function loadMedia(el) {
    const src = el.dataset.src;
    if (!src) return;

    el.src = src;
    delete el.dataset.src;

    if (el.tagName === 'VIDEO') {
      el.load();
      if (el.hasAttribute('data-autoplay')) {
        el.play().catch(function () {});
      }
    }

    el.classList.remove('lazy-pending');
    el.classList.add('lazy-loaded');
  }

  function ensureMediaObserver() {
    if (mediaObserver) return mediaObserver;

    mediaObserver = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        loadMedia(entry.target);
        obs.unobserve(entry.target);
      });
    }, { rootMargin: MEDIA_ROOT_MARGIN, threshold: 0.01 });

    return mediaObserver;
  }

  function observeMedia(root) {
    var scope = root || document;
    scope.querySelectorAll('img[data-src], video[data-src]').forEach(function (el) {
      if (!el.dataset.src) return;
      el.classList.add('lazy-pending');
      ensureMediaObserver().observe(el);
    });
  }

  function revealRow(row) {
    row.classList.remove('lazy-deferred', 'lazy-deferred-row');
    row.removeAttribute('aria-hidden');
    observeMedia(row);
  }

  function initLazyList(container) {
    if (container.dataset.lazyReady === '1') return;
    container.dataset.lazyReady = '1';

    var batchSize = parseInt(container.dataset.lazyBatch || String(DEFAULT_BATCH), 10);
    if (!batchSize || batchSize < 1) batchSize = DEFAULT_BATCH;

    var deferred = Array.prototype.slice.call(
      container.querySelectorAll('.match-row.lazy-deferred, .match-card.lazy-deferred, .lazy-deferred-row')
    );
    if (!deferred.length) return;

    var nextIndex = 0;
    var loadMoreWrap = null;
    var btn = null;
    var sentinel = null;
    var listObserver = null;
    var carousel = container.closest('[data-matches-carousel]');

    function remaining() {
      return deferred.length - nextIndex;
    }

    function updateControls() {
      var left = remaining();
      if (left <= 0) {
        if (loadMoreWrap) loadMoreWrap.remove();
        if (sentinel) sentinel.remove();
        if (listObserver) listObserver.disconnect();
        return;
      }
      if (btn) {
        btn.textContent = 'Cargar más (' + left + ')';
      }
    }

    function revealNextBatch() {
      var end = Math.min(nextIndex + batchSize, deferred.length);
      for (var i = nextIndex; i < end; i += 1) {
        revealRow(deferred[i]);
      }
      nextIndex = end;
      updateControls();
      if (carousel && window.hfMatchesCarousel) {
        var vp = carousel.querySelector('[data-carousel-viewport]');
        if (vp) window.hfMatchesCarousel.updateArrows(carousel, vp);
      }
      return nextIndex < deferred.length;
    }

    loadMoreWrap = document.createElement('div');
    loadMoreWrap.className = 'lazy-load-more-wrap';
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-outline btn-sm lazy-load-more';
    btn.addEventListener('click', revealNextBatch);
    loadMoreWrap.appendChild(btn);

    if (carousel) {
      carousel.insertAdjacentElement('afterend', loadMoreWrap);
    } else {
      container.insertAdjacentElement('afterend', loadMoreWrap);
    }

    sentinel = document.createElement('div');
    sentinel.className = 'lazy-sentinel';
    sentinel.setAttribute('aria-hidden', 'true');
    container.appendChild(sentinel);

    listObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) revealNextBatch();
      });
    }, { rootMargin: LIST_ROOT_MARGIN });

    listObserver.observe(sentinel);
    updateControls();
  }

  function scan(root) {
    observeMedia(root);
    if (!root) {
      document.querySelectorAll('[data-lazy-list]').forEach(initLazyList);
    } else if (root.matches && root.matches('[data-lazy-list]')) {
      initLazyList(root);
    } else {
      root.querySelectorAll('[data-lazy-list]').forEach(initLazyList);
    }
  }

  function init() {
    scan();
  }

  window.hfLazyLoad = { scan: scan, loadMedia: loadMedia };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
