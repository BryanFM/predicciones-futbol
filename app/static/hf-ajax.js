(function () {
  function ensureToastHost() {
    let host = document.getElementById('hf-toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'hf-toast-host';
      host.className = 'hf-toast-host';
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }
    return host;
  }

  function toast(message, type) {
    const host = ensureToastHost();
    const el = document.createElement('div');
    el.className = `hf-toast hf-toast-${type || 'success'}`;
    el.textContent = message;
    host.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => {
      el.classList.remove('show');
      setTimeout(() => el.remove(), 250);
    }, 2800);
  }

  async function postForm(url, formData) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'X-HF-Ajax': '1' },
      body: formData,
      credentials: 'same-origin',
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      data = { ok: false, error: 'Respuesta inválida del servidor' };
    }
    if (!res.ok || !data.ok) {
      const err = new Error(data.error || 'No se pudo guardar');
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function updateNavPoints(userPoints) {
    if (!userPoints) return;
    const valueEl = document.querySelector('.hp-nav-value');
    const nav = document.querySelector('.hamster-points-nav');
    if (valueEl) valueEl.textContent = String(userPoints.total ?? 0);
    if (nav) {
      nav.title = `Marcadores: ${userPoints.score_points ?? 0} · Campeón: ${userPoints.champion_points ?? 0}`;
    }
  }

  function resultSymbol(result) {
    if (result === 'hit') return '✓';
    if (result === 'miss') return '✗';
    return '⏳';
  }

  function matchPredictionsOpen(dataset) {
    if (!dataset || dataset.finished === '1' || dataset.parked === '1') return false;
    if (dataset.started === '1') return false;
    const cutoff = Number(dataset.cutoffMs);
    if (cutoff) return Date.now() < cutoff;
    return dataset.open === '1';
  }

  function syncMatchOpenState(dataset) {
    if (!dataset) return false;
    const open = matchPredictionsOpen(dataset);
    dataset.open = open ? '1' : '0';
    return open;
  }

  function teamFlagMarkup(team, flagUrl) {
    if (flagUrl) {
      return `<img data-src="${flagUrl}" alt="" class="team-flag sm" width="28" height="21">`;
    }
    return `<span class="team-badge sm">${team.slice(0, 2).toUpperCase()}</span>`;
  }

  function updateChampionStats(stats) {
    if (!stats) return;

    const panel = document.getElementById('champion-community-stats');
    const countEl = document.getElementById('champion-stats-count');
    const listEl = document.getElementById('champion-stats-list');

    if (countEl) countEl.textContent = `(${stats.total})`;
    if (panel) panel.classList.toggle('hidden', !stats.total);

    if (listEl) {
      listEl.innerHTML = (stats.teams || [])
        .map(
          (row) => `
        <li class="champion-stats-row">
          <span class="champion-stats-team">
            ${teamFlagMarkup(row.team, row.flag_url || '')}
            <span>${row.team}</span>
          </span>
          <span class="pct-bar" aria-hidden="true"><span class="pct-bar-fill" style="width: ${row.pct}%"></span></span>
          <span class="champion-stats-pct">${row.pct}%</span>
        </li>`
        )
        .join('');
      if (window.hfLazyLoad) window.hfLazyLoad.scan(listEl);
    }

    document.querySelectorAll('.champion-option[data-team]').forEach((opt) => {
      const team = opt.dataset.team;
      const pct = stats.by_team?.[team];
      let pctEl = opt.querySelector('.champion-option-pct');
      if (pct) {
        if (!pctEl) {
          pctEl = document.createElement('span');
          pctEl.className = 'champion-option-pct';
          opt.appendChild(pctEl);
        }
        pctEl.textContent = `${pct}%`;
        pctEl.classList.remove('hidden');
      } else if (pctEl) {
        pctEl.textContent = '';
        pctEl.classList.add('hidden');
      }
    });
  }

  function updateMatchRow(payload) {
    const row = document.querySelector(`.match-row[data-match-id="${payload.match_id}"]`);
    if (!row) return;

    row.dataset.hasPred = '1';
    row.dataset.predHome = String(payload.predicted_home_score);
    row.dataset.predAway = String(payload.predicted_away_score);
    row.classList.remove('match-row-empty');

    const scoreSlot = row.querySelector('.score-slot');
    const statusSlot = row.querySelector('.status-slot');
    if (scoreSlot) {
      scoreSlot.classList.remove('empty');
      scoreSlot.classList.add('filled');
      const val = scoreSlot.querySelector('.pick-value');
      if (val) val.textContent = payload.label;
    }
    if (statusSlot) {
      statusSlot.classList.remove('empty');
      statusSlot.classList.add('filled');
      const val = statusSlot.querySelector('.pick-value');
      if (val) val.textContent = resultSymbol(payload.result);
    }
  }

  function updateOutcomeRow(payload) {
    const row = document.querySelector(`.match-row[data-match-id="${payload.match_id}"]`);
    if (!row) return;

    row.dataset.hasOutcome = '1';
    row.dataset.outcomePick = payload.outcome_pick;
    row.dataset.outcomeResult = payload.result;
    row.classList.remove('match-row-empty');

    const outcomeSlot = row.querySelector('.outcome-slot');
    if (outcomeSlot) {
      outcomeSlot.classList.remove('empty');
      outcomeSlot.classList.add('filled');
      const val = outcomeSlot.querySelector('.pick-value');
      if (val) {
        let text = payload.outcome_pick;
        if (row.dataset.hasWager === '1' && row.dataset.wagerStatus === 'pending') {
          text += ` · ${row.dataset.wagerStake}HP`;
        }
        val.textContent = text;
      }
    }

    const statusSlot = row.querySelector('.status-slot');
    if (statusSlot && row.dataset.hasPred !== '1') {
      statusSlot.classList.remove('empty');
      statusSlot.classList.add('filled');
      const val = statusSlot.querySelector('.pick-value');
      if (val) val.textContent = resultSymbol(payload.result);
    }
  }

  function updateWagerRow(payload) {
    const row = document.querySelector(`.match-row[data-match-id="${payload.match_id}"]`);
    if (!row) return;

    if (payload.wager_cancelled) {
      row.dataset.hasWager = '0';
      delete row.dataset.wagerId;
      delete row.dataset.wagerPick;
      delete row.dataset.wagerStake;
      delete row.dataset.wagerStatus;
      const outcomeSlot = row.querySelector('.outcome-slot');
      if (outcomeSlot && row.dataset.hasOutcome === '1') {
        const val = outcomeSlot.querySelector('.pick-value');
        if (val) val.textContent = row.dataset.outcomePick;
      }
      return;
    }

    row.dataset.hasWager = '1';
    row.dataset.wagerId = String(payload.wager_id);
    row.dataset.wagerPick = payload.pick;
    row.dataset.wagerStake = String(payload.stake_hp);
    row.dataset.wagerStatus = payload.status;

    const outcomeSlot = row.querySelector('.outcome-slot');
    if (outcomeSlot) {
      outcomeSlot.classList.remove('empty');
      outcomeSlot.classList.add('filled');
      const val = outcomeSlot.querySelector('.pick-value');
      if (val) {
        const pick = row.dataset.outcomePick || payload.pick;
        val.textContent = payload.status === 'pending' ? `${pick} · ${payload.stake_hp}HP` : pick;
      }
    }
  }

  function updateWagerBalance(modal, wagerBalance) {
    if (!modal || !wagerBalance) return;
    modal.dataset.wagerAvailable = String(wagerBalance.available ?? 0);
    const hint = modal.querySelector('#outcome-modal-wager-balance-hint');
    if (hint) {
      const min = Number(modal.dataset.wagerMin || 1);
      const max = Math.min(
        Number(wagerBalance.available ?? 0),
        Number(modal.dataset.wagerMax || (wagerBalance.available ?? 0))
      );
      hint.innerHTML = `Tienes <strong>${wagerBalance.available ?? 0} HP disponibles</strong>. Si aciertas, duplicas lo apostado.`;
      const stakeInput = modal.querySelector('#outcome-modal-wager-stake');
      if (stakeInput) {
        stakeInput.min = String(min);
        stakeInput.max = String(Math.max(max, 0));
      }
    }
  }

  function updateOfficialRow(payload) {
    const row = document.querySelector(`.match-row[data-match-id="${payload.match_id}"]`);
    if (!row) return;

    row.dataset.officialHome = payload.home_score != null ? String(payload.home_score) : '';
    row.dataset.officialAway = payload.away_score != null ? String(payload.away_score) : '';
    row.dataset.finished = payload.finished ? '1' : '0';
    if (payload.predictions_open !== undefined) {
      row.dataset.open = payload.predictions_open ? '1' : '0';
    }
    if (payload.predictions_locked !== undefined) {
      row.dataset.started = payload.predictions_locked ? '1' : '0';
    }
    if (payload.match_parked !== undefined || payload.parked !== undefined) {
      row.dataset.parked = (payload.match_parked || payload.parked) ? '1' : '0';
    }
    if (payload.predictions_status) {
      row.classList.remove('status-open', 'status-closed', 'status-finished', 'status-in_progress');
      row.classList.add(`status-${payload.predictions_status}`);
    }
    row.classList.toggle('status-finished', !!(payload.finished || payload.parked));
    if (payload.finished || payload.parked) {
      row.classList.remove('status-open', 'status-closed', 'status-in_progress');
    }

    if (payload.predictions_status) {
      const badge = row.querySelector('.match-card-badge');
      if (badge) {
        badge.className = `match-card-badge match-card-badge--${payload.predictions_status}`;
        if (payload.finished || payload.parked) badge.textContent = 'Finalizado';
        else if (payload.predictions_open) badge.textContent = 'Abierto';
        else badge.textContent = 'En juego';
      }
      if (window.HF?.syncStartButton) {
        window.HF.syncStartButton(row, payload.predictions_open, payload.parked || payload.match_parked, payload.finished);
      }
      if (window.HF?.syncParkButton) {
        window.HF.syncParkButton(row, payload.predictions_open, payload.parked || payload.match_parked, payload.finished);
      }
    }

    const officialSlot = row.querySelector('.official-slot');
    if (officialSlot) {
      if (payload.finished && payload.official_label) {
        officialSlot.classList.remove('empty');
        officialSlot.classList.add('filled');
        const val = officialSlot.querySelector('.pick-value');
        if (val) val.textContent = payload.official_label;
      } else {
        officialSlot.classList.remove('filled');
        officialSlot.classList.add('empty');
        const val = officialSlot.querySelector('.pick-value');
        if (val) val.textContent = '—';
      }
    }

    if (payload.result && row.dataset.predHome) {
      const statusSlot = row.querySelector('.status-slot');
      if (statusSlot) {
        statusSlot.classList.remove('empty');
        statusSlot.classList.add('filled');
        const val = statusSlot.querySelector('.pick-value');
        if (val) val.textContent = resultSymbol(payload.result);
      }
    }
  }

  function updateMatchAdminRow(payload) {
    updateOfficialRow(payload);
    if (payload.reposition_carousel && window.hfMatchesCarousel?.repositionPending) {
      window.hfMatchesCarousel.repositionPending();
    }
    if (window.HF?.syncModalAdminButtons) {
      window.HF.syncModalAdminButtons(payload);
    }
  }

  window.HF = {
    toast,
    postForm,
    updateNavPoints,
    updateChampionStats,
    updateMatchRow,
    updateOutcomeRow,
    updateWagerRow,
    updateWagerBalance,
    updateOfficialRow,
    updateMatchAdminRow,
    resultSymbol,
    matchPredictionsOpen,
    syncMatchOpenState,
  };
})();
