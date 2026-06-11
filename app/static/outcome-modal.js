(function () {
  const modal = document.getElementById('outcome-modal');
  if (!modal) return;

  const backdrop = modal.querySelector('.modal-backdrop');
  const closeBtn = modal.querySelector('.modal-close');
  const authMsg = modal.querySelector('#outcome-modal-auth');
  const closedMsg = modal.querySelector('#outcome-modal-closed');
  const readonlyWrap = modal.querySelector('#outcome-modal-readonly-wrap');
  const readonlyText = modal.querySelector('#outcome-modal-readonly-text');
  const wagerReadonly = modal.querySelector('#outcome-modal-wager-readonly');
  const wagerReadonlyText = modal.querySelector('#outcome-modal-wager-text');
  const outcomeForm = document.getElementById('outcome-form');
  const wagerCancelForm = document.getElementById('wager-cancel-form');
  const wagerCancelBtn = modal.querySelector('#outcome-modal-wager-cancel');
  const wagerOption = modal.querySelector('#outcome-modal-wager-option');
  const wagerEnable = modal.querySelector('#outcome-modal-wager-enable');
  const wagerStakeWrap = modal.querySelector('#outcome-modal-stake-wrap');
  const wagerStake = modal.querySelector('#outcome-modal-wager-stake');
  const wagerBalanceHint = modal.querySelector('#outcome-modal-wager-balance-hint');
  const submitBtn = modal.querySelector('#outcome-modal-submit');

  const els = {
    homeName: modal.querySelector('#outcome-modal-home-name'),
    awayName: modal.querySelector('#outcome-modal-away-name'),
    homeFlag: modal.querySelector('#outcome-modal-home-flag'),
    awayFlag: modal.querySelector('#outcome-modal-away-flag'),
    homeBadge: modal.querySelector('#outcome-modal-home-badge'),
    awayBadge: modal.querySelector('#outcome-modal-away-badge'),
    meta: modal.querySelector('#outcome-modal-meta'),
    matchId: modal.querySelector('#outcome-modal-match-id'),
    homeLabel: modal.querySelector('#outcome-modal-home-label'),
    awayLabel: modal.querySelector('#outcome-modal-away-label'),
    title: modal.querySelector('#outcome-modal-title'),
  };

  const communityStats = modal.querySelector('#outcome-modal-community-stats');
  const communityBar = modal.querySelector('#outcome-modal-outcome-bar');
  const communityLabels = modal.querySelector('#outcome-modal-outcome-labels');
  const communityTotal = modal.querySelector('#outcome-modal-community-total');

  const auth = {
    loggedIn: modal.dataset.loggedIn === '1',
    verified: modal.dataset.verified === '1',
  };

  let activeRow = null;
  let saving = false;

  function hasOutcome(d) {
    return d.hasOutcome === '1';
  }

  function hasWager(d) {
    return d.hasWager === '1';
  }

  function pickLabel(pick, home, away) {
    if (pick === '1') return `Gana ${home}`;
    if (pick === '2') return `Gana ${away}`;
    if (pick === 'X') return 'Empate';
    return pick || '—';
  }

  function wagerAvailable() {
    return Number(modal.dataset.wagerAvailable || 0);
  }

  function wagerMinStake() {
    return Number(modal.dataset.wagerMin || 1);
  }

  function setRadio(formEl, name, value) {
    if (!formEl || !value) return;
    const input = formEl.querySelector(`input[name="${name}"][value="${value}"]`);
    if (input) input.checked = true;
  }

  function clearRadios(formEl, name) {
    if (!formEl) return;
    formEl.querySelectorAll(`input[name="${name}"]`).forEach((input) => {
      input.checked = false;
    });
  }

  function selectedPick() {
    if (!outcomeForm) return '';
    const checked = outcomeForm.querySelector('input[name="outcome_pick"]:checked');
    return checked ? checked.value : '';
  }

  function refreshWagerUI() {
    if (!wagerBalanceHint) return;
    const available = wagerAvailable();
    const min = wagerMinStake();
    const canWager = available >= min;
    if (wagerBalanceHint) {
      wagerBalanceHint.innerHTML = canWager
        ? `Tienes <strong>${available} HP disponibles</strong>. Si aciertas, duplicas lo apostado.`
        : 'No tienes HP disponibles para apostar.';
    }
    if (wagerStake) {
      wagerStake.min = String(min);
      wagerStake.max = String(Math.max(Math.min(available, Number(modal.dataset.wagerMax || available)), 0));
      if (canWager && wagerEnable?.checked) {
        wagerStake.value = String(available);
      }
    }
    if (wagerEnable) {
      wagerEnable.disabled = !canWager;
    }
  }

  function toggleWagerStake() {
    if (!wagerStakeWrap || !wagerEnable) return;
    const show = wagerEnable.checked && wagerAvailable() >= wagerMinStake();
    wagerStakeWrap.classList.toggle('hidden', !show);
    if (show && wagerStake && !wagerStake.value) {
      wagerStake.value = String(wagerAvailable());
    }
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

  function wagerStatusText(d) {
    const stake = d.wagerStake;
    const pick = pickLabel(d.wagerPick, d.home, d.away);
    if (d.wagerStatus === 'won') return `${stake} HP · ${pick} — ✓ Ganaste +${stake} HP`;
    if (d.wagerStatus === 'lost') return `${stake} HP · ${pick} — ✗ Perdiste −${stake} HP`;
    return `${stake} HP · ${pick} — ⏳ En juego`;
  }

  function setupForm(d, isOpen) {
    const pendingWager = hasWager(d) && d.wagerStatus === 'pending';

    if (readonlyWrap) readonlyWrap.classList.add('hidden');
    if (wagerReadonly) wagerReadonly.classList.add('hidden');
    if (outcomeForm) outcomeForm.classList.add('hidden');
    if (wagerOption) wagerOption.classList.add('hidden');

    if (hasOutcome(d) && !isOpen && readonlyWrap && readonlyText) {
      const sym = window.HF?.resultSymbol(d.outcomeResult) || '⏳';
      readonlyText.textContent = `${pickLabel(d.outcomePick, d.home, d.away)} ${sym}`;
      readonlyWrap.classList.remove('hidden');
    }

    if (hasWager(d) && wagerReadonly && wagerReadonlyText) {
      wagerReadonlyText.textContent = wagerStatusText(d);
      wagerReadonly.classList.remove('hidden');
      if (wagerCancelForm && d.wagerId) {
        wagerCancelForm.action = `/apuestas/${d.wagerId}/cancelar`;
      }
      if (wagerCancelBtn) {
        wagerCancelBtn.classList.toggle('hidden', !pendingWager || !isOpen);
      }
    }

    if (isOpen && outcomeForm) {
      outcomeForm.classList.remove('hidden');
      if (hasOutcome(d)) setRadio(outcomeForm, 'outcome_pick', d.outcomePick);
      else clearRadios(outcomeForm, 'outcome_pick');

      const showWagerOption = !pendingWager && modal.dataset.wagerAvailable !== undefined;
      if (wagerOption) {
        wagerOption.classList.toggle('hidden', !showWagerOption);
      }
      if (showWagerOption) {
        if (wagerEnable) {
          wagerEnable.checked = false;
          wagerEnable.disabled = wagerAvailable() < wagerMinStake();
        }
        if (wagerStakeWrap) wagerStakeWrap.classList.add('hidden');
        if (wagerStake) wagerStake.value = '';
        refreshWagerUI();
      }

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = hasOutcome(d) ? 'Actualizar' : 'Guardar';
      }
    }
  }

  function syncBodyScroll() {
    const scoreOpen = document.getElementById('score-modal')?.classList.contains('open');
    document.body.classList.toggle('modal-open', modal.classList.contains('open') || !!scoreOpen);
  }

  function openModal(row) {
    activeRow = row;
    const d = row.dataset;
    if (window.HF?.syncMatchOpenState) window.HF.syncMatchOpenState(d);
    if (!els.homeName) return;

    if (els.matchId) els.matchId.value = d.matchId;
    els.homeName.textContent = d.home;
    els.awayName.textContent = d.away;
    if (els.homeLabel) els.homeLabel.textContent = `Gana ${d.home}`;
    if (els.awayLabel) els.awayLabel.textContent = `Gana ${d.away}`;
    els.meta.textContent = d.meta || '';
    setFlag(els.homeFlag, els.homeBadge, d.homeFlag || '', d.home);
    setFlag(els.awayFlag, els.awayBadge, d.awayFlag || '', d.away);
    renderCommunityStats(d);

    const isFinished = d.finished === '1';
    const isOpen = d.open === '1' && !isFinished;

    if (authMsg) authMsg.classList.add('hidden');
    if (closedMsg) closedMsg.classList.add('hidden');

    if (!auth.loggedIn) {
      if (authMsg) {
        authMsg.innerHTML = '<a href="/auth/login">Inicia sesión</a> para registrar predicciones.';
        authMsg.classList.remove('hidden');
      }
      els.title.textContent = 'Resultado 1X2';
    } else if (!auth.verified) {
      if (authMsg) {
        authMsg.innerHTML = '<a href="/verificar-telefono">Verifica tu celular</a> para participar.';
        authMsg.classList.remove('hidden');
      }
      els.title.textContent = hasOutcome(d) ? 'Tu 1X2' : 'Resultado 1X2';
    } else if (!isOpen) {
      if (closedMsg) {
        closedMsg.textContent = isFinished
          ? '🔒 Predicciones cerradas — ya hay resultado oficial'
          : '⚽ El partido ya inició';
        closedMsg.classList.remove('hidden');
      }
      els.title.textContent = hasOutcome(d) ? 'Tu 1X2' : '1X2 cerrado';
      setupForm(d, false);
    } else {
      els.title.textContent = hasOutcome(d) ? 'Modificar 1X2' : 'Elegir 1X2';
      setupForm(d, true);
    }

    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
    syncBodyScroll();
  }

  function closeModal() {
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    syncBodyScroll();
    activeRow = null;
  }

  if (wagerEnable) {
    wagerEnable.addEventListener('change', toggleWagerStake);
  }

  if (outcomeForm) {
    outcomeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (saving || !window.HF) return;

      if (activeRow && !window.HF.matchPredictionsOpen(activeRow.dataset)) {
        window.HF.toast('El partido ya inició', 'error');
        return;
      }

      const pick = selectedPick();
      if (!pick) {
        window.HF.toast('Elige un resultado: local, empate o visitante', 'error');
        return;
      }

      const wantWager = wagerEnable?.checked && !wagerOption?.classList.contains('hidden');
      const stake = wantWager ? Number(wagerStake?.value || 0) : 0;
      if (wantWager && (!stake || stake < wagerMinStake())) {
        window.HF.toast('Indica cuántos HP quieres apostar', 'error');
        return;
      }

      saving = true;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Guardando…';
      }

      try {
        const outcomeData = new FormData(outcomeForm);
        const data = await window.HF.postForm(outcomeForm.action, outcomeData);
        window.HF.updateOutcomeRow(data);
        window.HF.updateNavPoints(data.user_points);
        if (activeRow) {
          activeRow.dataset.hasOutcome = '1';
          activeRow.dataset.outcomePick = data.outcome_pick;
          activeRow.dataset.outcomeResult = data.result;
        }

        let wagerMsg = '';
        const d = activeRow?.dataset;
        const canPlaceWager = wantWager && d && !(d.hasWager === '1' && d.wagerStatus === 'pending');
        if (canPlaceWager) {
          const wagerData = new FormData();
          wagerData.set('match_id', d.matchId);
          wagerData.set('pick', pick);
          wagerData.set('stake', String(stake));
          const catInput = outcomeForm.querySelector('input[name="return_category_id"]');
          const dateInput = outcomeForm.querySelector('input[name="return_match_date"]');
          const groupInput = outcomeForm.querySelector('input[name="return_group"]');
          if (catInput?.value) wagerData.set('return_category_id', catInput.value);
          if (dateInput?.value) wagerData.set('return_match_date', dateInput.value);
          if (groupInput?.value) wagerData.set('return_group', groupInput.value);

          const wagerResult = await window.HF.postForm('/apuestas', wagerData);
          window.HF.updateWagerRow(wagerResult);
          window.HF.updateNavPoints(wagerResult.user_points);
          window.HF.updateWagerBalance(modal, wagerResult.wager_balance);
          if (activeRow) {
            activeRow.dataset.hasWager = '1';
            activeRow.dataset.wagerId = String(wagerResult.wager_id);
            activeRow.dataset.wagerPick = wagerResult.pick;
            activeRow.dataset.wagerStake = String(wagerResult.stake_hp);
            activeRow.dataset.wagerStatus = wagerResult.status;
          }
          wagerMsg = ' y apuesta registrada';
        }

        window.HF.toast((data.updated ? 'Resultado actualizado' : 'Resultado guardado') + wagerMsg);
        closeModal();
      } catch (err) {
        window.HF?.toast(err.message || 'Error al guardar', 'error');
        if (submitBtn) {
          submitBtn.disabled = false;
          const d = activeRow?.dataset;
          submitBtn.textContent = d && hasOutcome(d) ? 'Actualizar' : 'Guardar';
        }
      } finally {
        saving = false;
      }
    });
  }

  if (wagerCancelForm) {
    wagerCancelForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (saving || !window.HF) return;
      if (!confirm('¿Retirar tu apuesta? Recuperarás los HP apostados.')) return;

      saving = true;
      if (wagerCancelBtn) wagerCancelBtn.disabled = true;

      try {
        const data = await window.HF.postForm(wagerCancelForm.action, new FormData(wagerCancelForm));
        window.HF.updateWagerRow(data);
        window.HF.updateNavPoints(data.user_points);
        window.HF.updateWagerBalance(modal, data.wager_balance);
        if (activeRow) {
          activeRow.dataset.hasWager = '0';
          delete activeRow.dataset.wagerId;
          delete activeRow.dataset.wagerPick;
          delete activeRow.dataset.wagerStake;
          delete activeRow.dataset.wagerStatus;
        }
        window.HF.toast('Apuesta retirada');
        if (activeRow) setupForm(activeRow.dataset, activeRow.dataset.open === '1' && activeRow.dataset.finished !== '1');
      } catch (err) {
        window.HF?.toast(err.message || 'Error al retirar apuesta', 'error');
      } finally {
        saving = false;
        if (wagerCancelBtn) wagerCancelBtn.disabled = false;
      }
    });
  }

  function handleOpenClick(e) {
    const trigger = e.target.closest('[data-open-modal="outcome"]');
    if (!trigger) return;
    const row = trigger.closest('.match-row[data-match-id]');
    if (!row) return;
    e.preventDefault();
    e.stopPropagation();
    openModal(row);
  }

  document.addEventListener('click', handleOpenClick);
  document.addEventListener('keydown', (e) => {
    const trigger = e.target.closest('[data-open-modal="outcome"]');
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

  window.HFOutcomeModal = { open: openModal, close: closeModal };
})();
