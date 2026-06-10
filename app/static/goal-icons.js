(function () {
  const MAX_ICONS = 5;
  const DEFAULT_HAMSTER = '/static/hamster.png';

  function createHamsterIcon(src, index) {
    const img = document.createElement('img');
    img.src = src || DEFAULT_HAMSTER;
    img.alt = '';
    img.className = 'goal-hamster';
    img.width = 32;
    img.height = 32;
    img.setAttribute('aria-hidden', 'true');
    if (index > 0) img.style.animationDelay = `${index * 40}ms`;
    return img;
  }

  function renderGoalIcons(container, rawValue, hamsterSrc) {
    if (!container) return;
    const n = Math.max(0, parseInt(rawValue, 10) || 0);
    const src = hamsterSrc || DEFAULT_HAMSTER;
    container.innerHTML = '';

    if (n === 0) {
      container.classList.add('empty');
      return;
    }
    container.classList.remove('empty');

    if (n > MAX_ICONS) {
      const img = createHamsterIcon(src, 0);
      img.classList.add('goal-hamster-lg');
      img.width = 40;
      img.height = 40;
      img.alt = 'Marcador alto';
      container.appendChild(img);
      return;
    }

    for (let i = 0; i < n; i++) {
      container.appendChild(createHamsterIcon(src, i));
    }
  }

  function bindGoalIcons(input, container, hamsterSrc) {
    if (!input || !container) return;
    const update = () => renderGoalIcons(container, input.value, hamsterSrc);
    input.addEventListener('input', update);
    input.addEventListener('change', update);
    update();
  }

  window.HFGoalIcons = { renderGoalIcons, bindGoalIcons, MAX_ICONS };
})();
