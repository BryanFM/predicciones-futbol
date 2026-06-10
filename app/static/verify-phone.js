(function () {
  const PREFIX = '+51';
  const localInput = document.getElementById('phone-local-input');
  const fullInput = document.getElementById('phone-full-input');
  const confirmPhoneInput = document.getElementById('confirm-phone-input');
  const sendForm = document.getElementById('verify-send-form');

  if (!localInput || !fullInput) return;

  function toLocalDigits(raw) {
    if (!raw) return '';
    let digits = String(raw).replace(/\D/g, '');
    if (digits.startsWith('51') && digits.length >= 11) {
      digits = digits.slice(2);
    }
    if (digits.startsWith('0') && digits.length === 10) {
      digits = digits.slice(1);
    }
    return digits.slice(0, 9);
  }

  function fullPhone() {
    return PREFIX + localInput.value.replace(/\D/g, '').slice(0, 9);
  }

  function syncFullPhone() {
    const full = fullPhone();
    fullInput.value = full;
    if (confirmPhoneInput) confirmPhoneInput.value = full;
  }

  const initial = localInput.dataset.initial || fullInput.value || '';
  localInput.value = toLocalDigits(initial);
  syncFullPhone();

  localInput.addEventListener('input', () => {
    localInput.value = localInput.value.replace(/\D/g, '').slice(0, 9);
    syncFullPhone();
  });

  if (sendForm) {
    sendForm.addEventListener('submit', () => {
      syncFullPhone();
    });
  }
})();
