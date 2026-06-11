(function () {
  'use strict';

  var loading = false;

  function toast(message, type) {
    if (window.HF && window.HF.toast) {
      window.HF.toast(message, type || 'error');
      return;
    }
    console.error(message);
  }

  function swapContent(targetId, html) {
    var target = document.querySelector('[data-swap-target="' + targetId + '"]');
    if (!target) {
      console.warn('Swap target no encontrado:', targetId);
      return false;
    }
    target.innerHTML = html;
    return true;
  }

  function updateHeroKicker(text) {
    var kicker = document.querySelector('.v2-hero-kicker');
    if (kicker && text) kicker.textContent = text.trim();
  }

  function updateModalReturnFields(categoryId, matchDate, group) {
    document.querySelectorAll('input[name="return_category_id"]').forEach(function (el) {
      el.value = categoryId || '';
    });
    document.querySelectorAll('input[name="return_match_date"]').forEach(function (el) {
      el.value = matchDate || '';
    });
    document.querySelectorAll('input[name="return_group"]').forEach(function (el) {
      el.value = group || '';
    });
  }

  function reinitDynamicUi() {
    if (window.hfMatchesCarousel && window.hfMatchesCarousel.init) {
      window.hfMatchesCarousel.init();
    }
    if (window.hfChampionForm && window.hfChampionForm.init) {
      window.hfChampionForm.init();
    }
  }

  function buildParams(form) {
    var params = new URLSearchParams(new FormData(form));
    if (!params.get('category_id')) {
      var hidden = form.querySelector('input[name="category_id"]');
      if (hidden && hidden.value) params.set('category_id', hidden.value);
    }
    if (!params.get('group')) params.delete('group');
    if (!params.get('match_date')) params.delete('match_date');
    return params;
  }

  function setLoading(isLoading) {
    var panel = document.getElementById('home-matches-panel');
    if (panel) panel.classList.toggle('is-loading', isLoading);
  }

  async function applyFilters(form) {
    if (!form || loading) return;

    var params = buildParams(form);
    loading = true;
    setLoading(true);

    try {
      var res = await fetch('/partials/home-filter?' + params.toString(), {
        headers: {
          'X-HF-Partial': '1',
          'Accept': 'text/html',
        },
        credentials: 'same-origin',
      });

      if (!res.ok) {
        throw new Error('No se pudieron cargar los partidos (HTTP ' + res.status + ')');
      }

      var html = await res.text();
      var doc = new DOMParser().parseFromString(html, 'text/html');
      var root = doc.querySelector('[data-home-filter-fragment]');
      if (!root) {
        throw new Error('Respuesta inválida del servidor');
      }

      var chunks = root.querySelectorAll('[data-swap-target]');
      for (var i = 0; i < chunks.length; i += 1) {
        var chunk = chunks[i];
        swapContent(chunk.getAttribute('data-swap-target'), chunk.innerHTML);
      }

      var kickerChunk = root.querySelector('[data-swap-target="home-hero-kicker"]');
      if (kickerChunk) updateHeroKicker(kickerChunk.textContent);

      var newForm = document.getElementById('home-filters-form');
      if (newForm) {
        var p = buildParams(newForm);
        updateModalReturnFields(p.get('category_id'), p.get('match_date'), p.get('group'));
        var qs = p.toString();
        history.replaceState(null, '', qs ? '/?' + qs : '/');
      }

      reinitDynamicUi();
    } catch (err) {
      toast(err.message || 'Error al filtrar', 'error');
    } finally {
      loading = false;
      setLoading(false);
    }
  }

  function onFilterChange(e) {
    var select = e.target.closest('[data-home-filter]');
    if (!select) return;
    var form = select.closest('#home-filters-form');
    if (!form) return;

    if (select.name === 'category_id') {
      var dateSel = form.querySelector('[name="match_date"]');
      var groupSel = form.querySelector('[name="group"]');
      if (dateSel) dateSel.value = '';
      if (groupSel) groupSel.value = '';
    }

    applyFilters(form);
  }

  function init() {
    document.addEventListener('change', onFilterChange);
    document.addEventListener('submit', function (e) {
      if (e.target.id !== 'home-filters-form') return;
      e.preventDefault();
      applyFilters(e.target);
    });
  }

  window.hfHomeFilters = { apply: applyFilters };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
