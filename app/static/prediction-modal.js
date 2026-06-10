(function () {
  const modal = document.getElementById('prediction-modal');
  if (!modal) return;

  const backdrop = modal.querySelector('.modal-backdrop');
  const closeBtn = modal.querySelector('.modal-close');
  const formWrap = modal.querySelector('.modal-form-wrap');
  const readonlyWrap = modal.querySelector('#modal-readonly-wrap');
  const readonlyScore = modal.querySelector('#modal-readonly-score');
  const editHint = modal.querySelector('#modal-edit-hint');
  const closedMsg = modal.querySelector('.modal-closed-msg');
  const authMsg = modal.querySelector('.modal-auth-msg');
  const form = document.getElementById('prediction-form');

  const els = {
    homeName: modal.querySelector('#modal-home-name'),
    awayName: modal.querySelector('#modal-away-name'),
    homeFlag: modal.querySelector('#modal-home-flag'),
    awayFlag: modal.querySelector('#modal-away-flag'),
    homeBadge: modal.querySelector('#modal-home-badge'),
    awayBadge: modal.querySelector('#modal-away-badge'),
    meta: modal.querySelector('#modal-meta'),
    matchId: modal.querySelector('#modal-match-id'),
    homeScore: modal.querySelector('#modal-home-score'),
    awayScore: modal.querySelector('#modal-away-score'),
    homeIcons: modal.querySelector('#modal-home-icons'),
    awayIcons: modal.querySelector('#modal-away-icons'),
    homeLabel: modal.querySelector('#modal-home-label-text'),
    awayLabel: modal.querySelector('#modal-away-label-text'),
    title: modal.querySelector('#modal-title'),
    submit: modal.querySelector('#modal-submit'),
  };

  const auth = {
    loggedIn: modal.dataset.loggedIn === '1',
    verified: modal.dataset.verified === '1',
    isAdmin: modal.dataset.isAdmin === '1',
  };

  const adminWrap = modal.querySelector('#modal-admin-wrap');
  const officialForm = modal.querySelector('#official-score-form');
  const officialHome = modal.querySelector('#modal-official-home');
  const officialAway = modal.querySelector('#modal-official-away');
  const officialClear = modal.querySelector('#modal-official-clear');
  const officialSave = modal.querySelector('#modal-official-save');
  const communityStats = modal.querySelector('#modal-community-stats');
  const communityBar = modal.querySelector('#modal-outcome-bar');
  const communityLabels = modal.querySelector('#modal-outcome-labels');
  const communityTotal = modal.querySelector('#modal-community-total');

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

  function renderCommunityStats(d) {
    if (!communityStats) return;
    const total = Number(d.pctTotal || 0);
    if (!total) {
      communityStats.classList.add('hidden');
      return;
    }
    const home = Number(d.pctHome || 0);
    const draw = Number(d.pctDraw || 0);
    const away = Number(d.pctAway || 0);

    if (communityBar) {
      communityBar.innerHTML = [
        home ? `<span class="outcome-seg home" style="width:${home}%"></span>` : '',
        draw ? `<span class="outcome-seg draw" style="width:${draw}%"></span>` : '',
        away ? `<span class="outcome-seg away" style="width:${away}%"></span>` : '',
      ].join('');
    }
    if (communityLabels) {
      communityLabels.innerHTML = [
        `<span class="outcome-label home" title="Gana local">L ${home}%</span>`,
        `<span class="outcome-label draw" title="Empate">E ${draw}%</span>`,
        `<span class="outcome-label away" title="Gana visitante">V ${away}%</span>`,
      ].join('');
    }
    if (communityTotal) {
      communityTotal.textContent = `${total} predicción${total === 1 ? '' : 'es'}`;
    }
    communityStats.classList.remove('hidden');
  }

  function openModal(row) {
    activeRow = row;
    const d = row.dataset;
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

    const setFlag = (img, badge, url, name) => {
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
    };
    setFlag(els.homeFlag, els.homeBadge, d.homeFlag || '', d.home);
    setFlag(els.awayFlag, els.awayBadge, d.awayFlag || '', d.away);
    renderCommunityStats(d);

    if (auth.isAdmin && adminWrap) {
      adminWrap.classList.remove('hidden');
      if (officialHome) officialHome.value = d.officialHome !== '' ? d.officialHome : '0';
      if (officialAway) officialAway.value = d.officialAway !== '' ? d.officialAway : '0';
      if (officialForm) officialForm.action = `/matches/${d.matchId}/score`;
      if (officialClear) officialClear.classList.toggle('hidden', d.finished !== '1');
    } else if (adminWrap) {
      adminWrap.classList.add('hidden');
    }

    const isFinished = d.finished === '1';
    const isOpen = d.open === '1' && !isFinished;

    if (formWrap) formWrap.classList.add('hidden');
    if (readonlyWrap) readonlyWrap.classList.add('hidden');
    if (closedMsg) closedMsg.classList.add('hidden');
    if (authMsg) authMsg.classList.add('hidden');
    if (editHint) editHint.classList.add('hidden');

    if (!auth.loggedIn) {
      authMsg.innerHTML = '<a href="/auth/login">Inicia sesión</a> para registrar predicciones.';
      authMsg.classList.remove('hidden');
      els.title.textContent = 'Predicciones';
    } else if (!auth.verified) {
      authMsg.innerHTML = '<a href="/verificar-telefono">Verifica tu celular</a> para participar.';
      authMsg.classList.remove('hidden');
      els.title.textContent = hasPred ? 'Tu marcador' : 'Predicciones';
    } else if (!isOpen) {
      if (hasPred && readonlyWrap && readonlyScore) {
        readonlyScore.textContent = predictionLabel(d);
        readonlyWrap.classList.remove('hidden');
      }
      if (closedMsg) {
        closedMsg.textContent = isFinished
          ? '🔒 Predicciones cerradas — ya hay resultado oficial'
          : '🔒 Predicciones cerradas — 5 min antes del inicio';
        closedMsg.classList.remove('hidden');
      }
      els.title.textContent = hasPred ? 'Tu marcador' : 'Predicciones cerradas';
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
    document.body.classList.add('modal-open');
    if (isOpen && auth.loggedIn && auth.verified && els.homeScore) {
      els.homeScore.focus();
      els.homeScore.select();
    }
  }

  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
    activeRow = null;
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (saving || !window.HF) return;
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

  document.addEventListener('click', (e) => {
    const row = e.target.closest('.match-row[data-match-id]');
    if (row) openModal(row);
  });

  document.addEventListener('keydown', (e) => {
    const row = e.target.closest('.match-row[data-match-id]');
    if (row && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      openModal(row);
    }
  });

  closeBtn.addEventListener('click', closeModal);
  backdrop.addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  });
})();
