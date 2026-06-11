(function () {
  const modal = document.getElementById('score-modal');
  if (!modal) return;

  const backdrop = modal.querySelector('.modal-backdrop');
  const closeBtn = modal.querySelector('.modal-close');
  const formWrap = modal.querySelector('#score-modal-form-wrap');
  const readonlyWrap = modal.querySelector('#score-modal-readonly-wrap');
  const readonlyScore = modal.querySelector('#score-modal-readonly-score');
  const editHint = modal.querySelector('#score-modal-edit-hint');
  const closedMsg = modal.querySelector('#score-modal-closed');
  const authMsg = modal.querySelector('#score-modal-auth');
  const form = document.getElementById('prediction-form');

  const els = {
    homeName: modal.querySelector('#score-modal-home-name'),
    awayName: modal.querySelector('#score-modal-away-name'),
    homeFlag: modal.querySelector('#score-modal-home-flag'),
    awayFlag: modal.querySelector('#score-modal-away-flag'),
    homeBadge: modal.querySelector('#score-modal-home-badge'),
    awayBadge: modal.querySelector('#score-modal-away-badge'),
    meta: modal.querySelector('#score-modal-meta'),
    matchId: modal.querySelector('#score-modal-match-id'),
    homeScore: modal.querySelector('#score-modal-home-score'),
    awayScore: modal.querySelector('#score-modal-away-score'),
    homeIcons: modal.querySelector('#score-modal-home-icons'),
    awayIcons: modal.querySelector('#score-modal-away-icons'),
    homeLabel: modal.querySelector('#score-modal-home-label-text'),
    awayLabel: modal.querySelector('#score-modal-away-label-text'),
    title: modal.querySelector('#score-modal-title'),
    submit: modal.querySelector('#score-modal-submit'),
  };

  const auth = {
    loggedIn: modal.dataset.loggedIn === '1',
    verified: modal.dataset.verified === '1',
    isAdmin: modal.dataset.isAdmin === '1',
  };

  const adminWrap = modal.querySelector('#score-modal-admin-wrap');
  const officialForm = modal.querySelector('#official-score-form');
  const officialHome = modal.querySelector('#score-modal-official-home');
  const officialAway = modal.querySelector('#score-modal-official-away');
  const officialClear = modal.querySelector('#score-modal-official-clear');
  const officialSave = modal.querySelector('#score-modal-official-save');
  const modalStartBtn = modal.querySelector('#score-modal-start-btn');
  const modalParkBtn = modal.querySelector('#score-modal-park-btn');

  let iconsBound = false;
  let activeRow = null;
  let saving = false;
  let savingOfficial = false;

  function hasPrediction(d) {
    return d.hasPred === '1';
  }

  function predictionLabel(d) {
    if (!hasPrediction(d)) return '';
    return `${d.predHome} - ${d.predAway}`;
  }

  function bindIcons() {
    if (iconsBound || !window.HFGoalIcons) return;
    window.HFGoalIcons.bindGoalIcons(els.homeScore, els.homeIcons);
    window.HFGoalIcons.bindGoalIcons(els.awayScore, els.awayIcons);
    iconsBound = true;
  }

  function refreshIcons() {
    if (!window.HFGoalIcons) return;
    window.HFGoalIcons.renderGoalIcons(els.homeIcons, els.homeScore.value);
    window.HFGoalIcons.renderGoalIcons(els.awayIcons, els.awayScore.value);
  }

  function setFlag(img, badge, url, name) {
    if (url) {
      img.src = url;
      img.alt = name;
      img.classList.remove('hidden');
      badge.classList.add('hidden');
    } else {
      img.classList.add('hidden');
      badge.textContent = name.slice(0, 2).toUpperCase();
      badge.classList.remove('hidden');
    }
  }

  function syncBodyScroll() {
    const outcomeOpen = document.getElementById('outcome-modal')?.classList.contains('open');
    document.body.classList.toggle('modal-open', modal.classList.contains('open') || !!outcomeOpen);
  }

  function openModal(row) {
    activeRow = row;
    const d = row.dataset;
    if (window.HF?.syncMatchOpenState) window.HF.syncMatchOpenState(d);
    if (!els.homeName) return;

    const canEdit = auth.loggedIn && auth.verified;
    const hasPred = canEdit && hasPrediction(d);

    if (els.homeScore && els.awayScore) {
      els.homeScore.value = hasPred ? d.predHome : '0';
      els.awayScore.value = hasPred ? d.predAway : '0';
      bindIcons();
      refreshIcons();
    }

    if (els.matchId) els.matchId.value = d.matchId;
    els.homeName.textContent = d.home;
    els.awayName.textContent = d.away;
    if (els.homeLabel) els.homeLabel.textContent = d.home;
    if (els.awayLabel) els.awayLabel.textContent = d.away;
    els.meta.textContent = d.meta || '';
    setFlag(els.homeFlag, els.homeBadge, d.homeFlag || '', d.home);
    setFlag(els.awayFlag, els.awayBadge, d.awayFlag || '', d.away);

    if (auth.isAdmin && adminWrap) {
      adminWrap.classList.remove('hidden');
      if (officialHome) officialHome.value = d.officialHome !== '' ? d.officialHome : '0';
      if (officialAway) officialAway.value = d.officialAway !== '' ? d.officialAway : '0';
      if (officialForm) officialForm.action = `/matches/${d.matchId}/score`;
      if (officialClear) officialClear.classList.toggle('hidden', d.finished !== '1');
    } else if (adminWrap) {
      adminWrap.classList.add('hidden');
    }

    if (auth.isAdmin && modalStartBtn) {
      modalStartBtn.dataset.matchId = d.matchId;
      const parked = d.parked === '1';
      modalStartBtn.classList.toggle('hidden', d.finished === '1' || parked || d.open !== '1');
    }
    if (auth.isAdmin && modalParkBtn) {
      modalParkBtn.dataset.matchId = d.matchId;
      const parked = d.parked === '1';
      modalParkBtn.classList.toggle('hidden', d.finished === '1' || parked || d.open === '1');
    }

    const isFinished = d.finished === '1' || d.parked === '1';
    const isOpen = d.open === '1' && !isFinished;

    if (formWrap) formWrap.classList.add('hidden');
    if (readonlyWrap) readonlyWrap.classList.add('hidden');
    if (closedMsg) closedMsg.classList.add('hidden');
    if (authMsg) authMsg.classList.add('hidden');
    if (editHint) editHint.classList.add('hidden');

    if (!auth.loggedIn) {
      authMsg.innerHTML = '<a href="/auth/login">Inicia sesión</a> para registrar predicciones.';
      authMsg.classList.remove('hidden');
      els.title.textContent = 'Marcador';
    } else if (!auth.verified) {
      authMsg.innerHTML = '<a href="/verificar-telefono">Verifica tu celular</a> para participar.';
      authMsg.classList.remove('hidden');
      els.title.textContent = hasPred ? 'Tu marcador' : 'Marcador';
    } else if (!isOpen) {
      if (hasPred && readonlyWrap && readonlyScore) {
        readonlyScore.textContent = predictionLabel(d);
        readonlyWrap.classList.remove('hidden');
      }
      if (closedMsg) {
        closedMsg.textContent = isFinished && d.finished === '1'
          ? '🔒 Predicciones cerradas — ya hay resultado oficial'
          : isFinished
            ? 'Partido dado por finalizado'
            : '⚽ El partido ya inició';
        closedMsg.classList.remove('hidden');
      }
      els.title.textContent = hasPred ? 'Tu marcador' : 'Marcador cerrado';
    } else if (formWrap) {
      formWrap.classList.remove('hidden');
      if (editHint) editHint.classList.toggle('hidden', !hasPred);
      els.title.textContent = hasPred ? 'Modificar marcador' : 'Registrar marcador';
      if (els.submit) {
        els.submit.textContent = hasPred ? 'Actualizar marcador' : 'Guardar marcador';
        els.submit.disabled = false;
      }
    }

    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    syncBodyScroll();
    if (isOpen && auth.loggedIn && auth.verified && els.homeScore) {
      els.homeScore.focus();
      els.homeScore.select();
    }
  }

  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    syncBodyScroll();
    activeRow = null;
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (saving || !window.HF) return;
      if (activeRow && !window.HF.matchPredictionsOpen(activeRow.dataset)) {
        window.HF.toast('El partido ya inició', 'error');
        return;
      }
      if (!els.homeScore || !els.awayScore) return;

      saving = true;
      if (els.submit) {
        els.submit.disabled = true;
        els.submit.textContent = 'Guardando…';
      }

      try {
        const data = await window.HF.postForm(form.action, new FormData(form));
        window.HF.updateMatchRow(data);
        window.HF.updateNavPoints(data.user_points);
        if (activeRow) {
          activeRow.dataset.hasPred = '1';
          activeRow.dataset.predHome = String(data.predicted_home_score);
          activeRow.dataset.predAway = String(data.predicted_away_score);
        }
        window.HF.toast(data.updated ? 'Marcador actualizado' : 'Marcador guardado');
        closeModal();
      } catch (err) {
        window.HF?.toast(err.message || 'Error al guardar', 'error');
        if (els.submit) {
          els.submit.disabled = false;
          const hasPred = activeRow && hasPrediction(activeRow.dataset);
          els.submit.textContent = hasPred ? 'Actualizar marcador' : 'Guardar marcador';
        }
      } finally {
        saving = false;
      }
    });
  }

  if (officialForm) {
    officialForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (savingOfficial || !window.HF) return;

      savingOfficial = true;
      if (officialSave) {
        officialSave.disabled = true;
        officialSave.textContent = 'Guardando…';
      }

      try {
        const data = await window.HF.postForm(officialForm.action, new FormData(officialForm));
        window.HF.updateOfficialRow(data);
        if (activeRow) {
          activeRow.dataset.officialHome = String(data.home_score);
          activeRow.dataset.officialAway = String(data.away_score);
          activeRow.dataset.finished = data.finished ? '1' : '0';
        }
        if (officialClear) officialClear.classList.remove('hidden');
        window.HF.toast('Marcador oficial guardado');
      } catch (err) {
        window.HF?.toast(err.message || 'Error al guardar', 'error');
      } finally {
        savingOfficial = false;
        if (officialSave) {
          officialSave.disabled = false;
          officialSave.textContent = 'Guardar oficial';
        }
      }
    });
  }

  if (officialClear) {
    officialClear.addEventListener('click', async () => {
      if (savingOfficial || !window.HF || !activeRow) return;
      if (!confirm('¿Quitar el marcador oficial? Las predicciones volverán a pendiente.')) return;

      savingOfficial = true;
      officialClear.disabled = true;

      try {
        const matchId = activeRow.dataset.matchId;
        const data = await window.HF.postForm(`/matches/${matchId}/score/clear`, new FormData());
        window.HF.updateOfficialRow(data);
        activeRow.dataset.officialHome = '';
        activeRow.dataset.officialAway = '';
        activeRow.dataset.finished = '0';
        if (officialHome) officialHome.value = '0';
        if (officialAway) officialAway.value = '0';
        officialClear.classList.add('hidden');
        window.HF.toast('Marcador oficial eliminado');
      } catch (err) {
        window.HF?.toast(err.message || 'Error al quitar marcador', 'error');
      } finally {
        savingOfficial = false;
        officialClear.disabled = false;
      }
    });
  }

  function handleOpenClick(e) {
    const trigger = e.target.closest('[data-open-modal="score"]');
    if (!trigger) return;
    const row = trigger.closest('.match-row[data-match-id]');
    if (!row) return;
    e.preventDefault();
    e.stopPropagation();
    openModal(row);
  }

  document.addEventListener('click', handleOpenClick);
  document.addEventListener('keydown', (e) => {
    const trigger = e.target.closest('[data-open-modal="score"]');
    if (trigger && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      const row = trigger.closest('.match-row[data-match-id]');
      if (row) openModal(row);
    }
  });

  closeBtn.addEventListener('click', closeModal);
  backdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });

  window.HFScoreModal = { open: openModal, close: closeModal };
})();
