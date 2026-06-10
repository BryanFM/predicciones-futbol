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

  function teamFlagMarkup(team, flagUrl) {
    if (flagUrl) {
      return `<img src="${flagUrl}" alt="" class="team-flag sm" loading="lazy" width="28" height="21">`;
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

  function updateOfficialRow(payload) {
    const row = document.querySelector(`.match-row[data-match-id="${payload.match_id}"]`);
    if (!row) return;

    row.dataset.officialHome = payload.home_score != null ? String(payload.home_score) : '';
    row.dataset.officialAway = payload.away_score != null ? String(payload.away_score) : '';
    row.dataset.finished = payload.finished ? '1' : '0';
    if (payload.predictions_open !== undefined) {
      row.dataset.open = payload.predictions_open ? '1' : '0';
    }
    row.classList.toggle('status-finished', !!payload.finished);
    if (payload.finished) {
      row.classList.remove('status-open', 'status-closed');
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

  window.HF = {
    toast,
    postForm,
    updateNavPoints,
    updateChampionStats,
    updateMatchRow,
    updateOfficialRow,
    resultSymbol,
  };
})();
