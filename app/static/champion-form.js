(function () {
  'use strict';

  var lastSavedTeam = '';
  var saving = false;

  function flagMarkup(team, flagUrl) {
    if (flagUrl) {
      return '<img data-src="' + flagUrl + '" alt="" class="team-flag sm" width="28" height="21">';
    }
    return '<span class="team-badge sm">' + team.slice(0, 2).toUpperCase() + '</span>';
  }

  function setStatus(statusEl, text, type) {
    if (!statusEl) return;
    statusEl.textContent = text || '';
    statusEl.className = 'champion-save-status' + (type ? ' is-' + type : '');
  }

  function updateHeaderPick(headerPick, team, flagUrl) {
    if (!headerPick) return;
    if (!team) {
      headerPick.innerHTML = '<span class="champion-header-empty">Sin elegir</span>';
      return;
    }
    headerPick.innerHTML = flagMarkup(team, flagUrl || '') + '<strong>' + team + '</strong>';
    if (window.hfLazyLoad) window.hfLazyLoad.scan(headerPick);
  }

  function collapsePanel(panel, body, toggle) {
    if (!panel || !body || !toggle) return;
    panel.classList.remove('is-open');
    panel.classList.add('is-collapsed');
    body.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
  }

  function bindChampionPanel() {
    var panel = document.getElementById('campeon');
    var form = document.getElementById('champion-form');
    var headerPick = document.getElementById('champion-header-pick');
    var statusEl = document.getElementById('champion-save-status');
    var toggle = panel ? panel.querySelector('.champion-toggle') : null;
    var body = document.getElementById('champion-body');

    if (!panel) return;

    if (toggle && body && panel.dataset.championBound !== '1') {
      panel.dataset.championBound = '1';
      toggle.addEventListener('click', function () {
        var open = panel.classList.toggle('is-open');
        panel.classList.toggle('is-collapsed', !open);
        body.hidden = !open;
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    }

    if (!form || form.dataset.championBound === '1') return;
    form.dataset.championBound = '1';

    var hiddenInput = document.getElementById('champion-team-input');
    var options = form.querySelectorAll('.champion-option[data-team]');
    lastSavedTeam = hiddenInput ? hiddenInput.value || '' : '';

    async function saveTeam(team) {
      if (!hiddenInput || !team || saving || !window.HF) return;
      if (team === lastSavedTeam) return;

      saving = true;
      setStatus(statusEl, 'Guardando…', 'loading');
      options.forEach(function (opt) {
        opt.classList.toggle('is-saving', opt.dataset.team === team);
      });

      var fd = new FormData(form);
      fd.set('champion_team', team);

      try {
        var data = await window.HF.postForm(form.action, fd);
        lastSavedTeam = team;
        updateHeaderPick(headerPick, data.champion_team, data.flag_url || '');
        window.HF.updateNavPoints(data.user_points);
        if (data.champion_stats) window.HF.updateChampionStats(data.champion_stats);
        setStatus(statusEl, 'Guardado ✓', 'success');
        window.HF.toast('Campeón: ' + data.champion_team);
        collapsePanel(panel, body, toggle);
        setTimeout(function () { setStatus(statusEl, '', ''); }, 2000);
      } catch (err) {
        setStatus(statusEl, 'Error al guardar', 'error');
        window.HF.toast(err.message || 'Error al guardar', 'error');
      } finally {
        saving = false;
        options.forEach(function (opt) { opt.classList.remove('is-saving'); });
      }
    }

    function selectTeam(team) {
      if (!hiddenInput) return;
      hiddenInput.value = team;
      options.forEach(function (opt) {
        var selected = opt.dataset.team === team;
        opt.classList.toggle('selected', selected);
        opt.setAttribute('aria-pressed', selected ? 'true' : 'false');
      });
      var active = Array.prototype.find.call(options, function (opt) { return opt.dataset.team === team; });
      updateHeaderPick(headerPick, team, active ? active.dataset.flag || '' : '');
      saveTeam(team);
    }

    options.forEach(function (opt) {
      opt.addEventListener('click', function () { selectTeam(opt.dataset.team); });
    });

    if (hiddenInput && hiddenInput.value) {
      var current = Array.prototype.find.call(options, function (opt) {
        return opt.dataset.team === hiddenInput.value;
      });
      options.forEach(function (opt) {
        var selected = opt.dataset.team === hiddenInput.value;
        opt.classList.toggle('selected', selected);
        opt.setAttribute('aria-pressed', selected ? 'true' : 'false');
      });
      if (current) updateHeaderPick(headerPick, hiddenInput.value, current.dataset.flag || '');
    }

    form.addEventListener('submit', function (e) { e.preventDefault(); });
  }

  window.hfChampionForm = { init: bindChampionPanel };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindChampionPanel);
  } else {
    bindChampionPanel();
  }
})();
