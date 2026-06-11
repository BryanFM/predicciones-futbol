(function () {
  'use strict';

  function getScrollStep(viewport) {
    var card = viewport.querySelector('.match-card');
    if (!card) return viewport.clientWidth * 0.85;
    var track = viewport.querySelector('.matches-carousel-track');
    var gap = track ? parseFloat(window.getComputedStyle(track).gap) || 0 : 0;
    return card.offsetWidth + gap;
  }

  function isPendingCard(card) {
    return card.dataset.finished !== '1' && card.dataset.parked !== '1' && card.dataset.open === '1';
  }

  function scrollToPending(viewport, smooth) {
    if (!viewport) return;
    var firstPending = viewport.querySelector('.match-row[data-open="1"]:not(.lazy-deferred)');
    if (!firstPending) {
      viewport.scrollTo({ left: 0, behavior: smooth ? 'smooth' : 'auto' });
      return;
    }
    var track = viewport.querySelector('.matches-carousel-track');
    var offset = track ? firstPending.offsetLeft - track.offsetLeft : firstPending.offsetLeft;
    viewport.scrollTo({ left: Math.max(0, offset), behavior: smooth ? 'smooth' : 'auto' });
  }

  function repositionPending(root) {
    if (!root) root = document.querySelector('[data-matches-carousel]');
    if (!root) return;
    var viewport = root.querySelector('[data-carousel-viewport]');
    var track = viewport && viewport.querySelector('.matches-carousel-track');
    if (!viewport || !track) return;

    var cards = Array.from(track.querySelectorAll('.match-row'));
    var archived = cards.filter(function (c) { return !isPendingCard(c); });
    var pending = cards.filter(isPendingCard);
    archived.concat(pending).forEach(function (card) {
      track.appendChild(card);
    });
    scrollToPending(viewport, true);
    updateArrows(root, viewport);
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
    var viewport = root.querySelector('[data-carousel-viewport]');
    if (!viewport) return;

    var prev = root.querySelector('[data-carousel-prev]');
    var next = root.querySelector('[data-carousel-next]');

    function scrollBy(delta) {
      viewport.scrollBy({ left: delta, behavior: 'smooth' });
    }

    if (!root.dataset.carouselReady) {
      root.dataset.carouselReady = '1';

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
    }

    repositionPending(root);
    scrollToPending(viewport, false);
    updateArrows(root, viewport);
  }

  function init() {
    document.querySelectorAll('[data-matches-carousel]').forEach(initCarousel);
  }

  window.hfMatchesCarousel = {
    init: init,
    updateArrows: updateArrows,
    scrollToPending: scrollToPending,
    repositionPending: repositionPending,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
