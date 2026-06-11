(function () {
  'use strict';

  function getScrollStep(viewport) {
    var card = viewport.querySelector('.match-card');
    if (!card) return viewport.clientWidth * 0.85;
    var style = window.getComputedStyle(card);
    var track = viewport.querySelector('.matches-carousel-track');
    var gap = track ? parseFloat(window.getComputedStyle(track).gap) || 0 : 0;
    return card.offsetWidth + gap;
  }

  function updateArrows(root, viewport) {
    var prev = root.querySelector('[data-carousel-prev]');
    var next = root.querySelector('[data-carousel-next]');
    var maxScroll = viewport.scrollWidth - viewport.clientWidth - 2;
    var atStart = viewport.scrollLeft <= 2;
    var atEnd = viewport.scrollLeft >= maxScroll;

    if (prev) {
      prev.disabled = atStart;
      prev.setAttribute('aria-disabled', atStart ? 'true' : 'false');
    }
    if (next) {
      next.disabled = atEnd;
      next.setAttribute('aria-disabled', atEnd ? 'true' : 'false');
    }
  }

  function initCarousel(root) {
    if (root.dataset.carouselReady === '1') return;
    root.dataset.carouselReady = '1';

    var viewport = root.querySelector('[data-carousel-viewport]');
    if (!viewport) return;

    var prev = root.querySelector('[data-carousel-prev]');
    var next = root.querySelector('[data-carousel-next]');

    function scrollBy(delta) {
      viewport.scrollBy({ left: delta, behavior: 'smooth' });
    }

    if (prev) {
      prev.addEventListener('click', function () {
        scrollBy(-getScrollStep(viewport));
      });
    }

    if (next) {
      next.addEventListener('click', function () {
        scrollBy(getScrollStep(viewport));
      });
    }

    viewport.addEventListener('scroll', function () {
      updateArrows(root, viewport);
    }, { passive: true });

    window.addEventListener('resize', function () {
      updateArrows(root, viewport);
    });

    if (window.ResizeObserver) {
      var ro = new ResizeObserver(function () {
        updateArrows(root, viewport);
      });
      ro.observe(viewport);
      var track = viewport.querySelector('.matches-carousel-track');
      if (track) ro.observe(track);
    }

    updateArrows(root, viewport);
  }

  function init() {
    document.querySelectorAll('[data-matches-carousel]').forEach(initCarousel);
  }

  window.hfMatchesCarousel = { init: init, updateArrows: updateArrows };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
