(function () {
  const panel = document.getElementById('campeon');
  const form = document.getElementById('champion-form');
  const headerPick = document.getElementById('champion-header-pick');
  const statusEl = document.getElementById('champion-save-status');
  const toggle = panel?.querySelector('.champion-toggle');
  const body = document.getElementById('champion-body');

  if (toggle && body) {
    toggle.addEventListener('click', () => {
      const open = panel.classList.toggle('is-open');
      panel.classList.toggle('is-collapsed', !open);
      body.hidden = !open;
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  if (!form) return;

  const hiddenInput = document.getElementById('champion-team-input');
  const options = form.querySelectorAll('.champion-option[data-team]');
  let lastSavedTeam = hiddenInput?.value || '';
  let saving = false;

  function flagMarkup(team, flagUrl) {
    if (flagUrl) {
      return `<img src="${flagUrl}" alt="" class="team-flag sm" loading="lazy" width="28" height="21">`;
    }
    return `<span class="team-badge sm">${team.slice(0, 2).toUpperCase()}</span>`;
  }

  function setStatus(text, type) {
    if (!statusEl) return;
    statusEl.textContent = text || '';
    statusEl.className = 'champion-save-status' + (type ? ` is-${type}` : '');
  }

  function updateHeaderPick(team, flagUrl) {
    if (!headerPick) return;
    if (!team) {
      headerPick.innerHTML = '<span class="champion-header-empty">Sin elegir</span>';
      return;
    }
    headerPick.innerHTML = `${flagMarkup(team, flagUrl || '')}<strong>${team}</strong>`;
  }

  function collapsePanel() {
    if (!panel || !body || !toggle) return;
    panel.classList.remove('is-open');
    panel.classList.add('is-collapsed');
    body.hidden = true;
    toggle.setAttribute('aria-expanded', 'false');
  }

  async function saveTeam(team) {
    if (!hiddenInput || !team || saving || !window.HF) return;
    if (team === lastSavedTeam) return;

    saving = true;
    setStatus('Guardando…', 'loading');
    options.forEach((opt) => opt.classList.toggle('is-saving', opt.dataset.team === team));

    const fd = new FormData(form);
    fd.set('champion_team', team);

    try {
      const data = await window.HF.postForm(form.action, fd);
      lastSavedTeam = team;
      updateHeaderPick(data.champion_team, data.flag_url || '');
      window.HF.updateNavPoints(data.user_points);
      if (data.champion_stats) window.HF.updateChampionStats(data.champion_stats);
      setStatus('Guardado ✓', 'success');
      window.HF.toast(`Campeón: ${data.champion_team}`);
      collapsePanel();
      setTimeout(() => setStatus('', ''), 2000);
    } catch (err) {
      setStatus('Error al guardar', 'error');
      window.HF.toast(err.message || 'Error al guardar', 'error');
    } finally {
      saving = false;
      options.forEach((opt) => opt.classList.remove('is-saving'));
    }
  }

  function selectTeam(team) {
    if (!hiddenInput) return;
    hiddenInput.value = team;
    options.forEach((opt) => {
      const selected = opt.dataset.team === team;
      opt.classList.toggle('selected', selected);
      opt.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
    const active = [...options].find((opt) => opt.dataset.team === team);
    updateHeaderPick(team, active?.dataset.flag || '');
    saveTeam(team);
  }

  options.forEach((opt) => {
    opt.addEventListener('click', () => selectTeam(opt.dataset.team));
  });

  if (hiddenInput && hiddenInput.value) {
    const current = [...options].find((opt) => opt.dataset.team === hiddenInput.value);
    hiddenInput.value = hiddenInput.value;
    options.forEach((opt) => {
      const selected = opt.dataset.team === hiddenInput.value;
      opt.classList.toggle('selected', selected);
      opt.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
    if (current) updateHeaderPick(hiddenInput.value, current.dataset.flag || '');
  }

  form.addEventListener('submit', (e) => e.preventDefault());
})();
