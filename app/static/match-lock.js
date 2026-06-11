(function () {
  function syncStartButton(row, open, parked, finished) {
    if (!row) return;
    const btn = row.querySelector('[data-match-start-btn]');
    if (!btn) return;
    const show = !finished && !parked && (open === true || open === '1');
    btn.classList.toggle('hidden', !show);
  }

  function syncParkButton(row, open, parked, finished) {
    if (!row) return;
    const btn = row.querySelector('[data-match-park-btn]');
    if (!btn) return;
    const show = !finished && !parked && open !== true && open !== '1';
    btn.classList.toggle('hidden', !show);
  }

  function syncModalAdminButtons(payload) {
    const startBtn = document.getElementById('score-modal-start-btn');
    const parkBtn = document.getElementById('score-modal-park-btn');
    const finished = payload.finished || payload.parked;
    if (startBtn && payload.match_id) {
      startBtn.dataset.matchId = String(payload.match_id);
      startBtn.classList.toggle('hidden', finished || payload.predictions_open === false);
    }
    if (parkBtn && payload.match_id) {
      parkBtn.dataset.matchId = String(payload.match_id);
      parkBtn.classList.toggle(
        'hidden',
        finished || payload.predictions_open === true || payload.parked
      );
    }
  }

  async function startMatch(btn) {
    if (!btn || btn.disabled || !window.HF) return;
    const matchId = btn.dataset.matchId || btn.closest('[data-match-id]')?.dataset.matchId;
    if (!matchId) return;

    btn.disabled = true;
    try {
      const fd = new FormData();
      fd.set('return_to', window.location.pathname + window.location.search);
      const data = await window.HF.postForm(`/matches/${matchId}/match-start`, fd);
      window.HF.updateMatchAdminRow(data);
      window.HF.toast(data.message || 'El partido ya inició');
    } catch (err) {
      window.HF.toast(err.message || 'No se pudo marcar el inicio', 'error');
    } finally {
      btn.disabled = false;
    }
  }

  async function parkMatch(btn) {
    if (!btn || btn.disabled || !window.HF) return;
    const matchId = btn.dataset.matchId || btn.closest('[data-match-id]')?.dataset.matchId;
    if (!matchId) return;

    btn.disabled = true;
    try {
      const fd = new FormData();
      fd.set('return_to', window.location.pathname + window.location.search);
      const data = await window.HF.postForm(`/matches/${matchId}/match-park`, fd);
      window.HF.updateMatchAdminRow(data);
      window.HF.toast(data.message || 'Partido dado por finalizado');
    } catch (err) {
      window.HF.toast(err.message || 'No se pudo finalizar el partido', 'error');
    } finally {
      btn.disabled = false;
    }
  }

  document.addEventListener('click', (e) => {
    const startBtn = e.target.closest('[data-match-start-btn]');
    if (startBtn) {
      e.preventDefault();
      e.stopPropagation();
      startMatch(startBtn);
      return;
    }
    const parkBtn = e.target.closest('[data-match-park-btn]');
    if (parkBtn) {
      e.preventDefault();
      e.stopPropagation();
      parkMatch(parkBtn);
    }
  });

  window.HF = window.HF || {};
  window.HF.syncStartButton = syncStartButton;
  window.HF.syncParkButton = syncParkButton;
  window.HF.syncModalAdminButtons = syncModalAdminButtons;
})();
