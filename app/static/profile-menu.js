(function () {
  'use strict';

  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var root = document.documentElement;
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      localStorage.setItem('hf-theme', next);
    });
  }

  var profile = document.getElementById('profile-menu');
  if (!profile) return;

  var trigger = profile.querySelector('.profile-trigger');
  var backdrop = profile.querySelector('.profile-menu-backdrop');
  var canHover = window.matchMedia('(hover: hover) and (min-width: 769px)').matches;

  function setProfileOpen(open) {
    profile.classList.toggle('open', open);
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    var mobile = window.matchMedia('(max-width: 768px)').matches;
    document.body.classList.toggle('profile-menu-open', open && mobile);
    if (backdrop) backdrop.setAttribute('aria-hidden', open ? 'false' : 'true');
  }

  trigger.addEventListener('click', function (e) {
    e.stopPropagation();
    setProfileOpen(!profile.classList.contains('open'));
  });

  if (backdrop) {
    backdrop.addEventListener('click', function () {
      setProfileOpen(false);
    });
  }

  if (canHover) {
    var closeTimer;
    profile.addEventListener('mouseenter', function () {
      clearTimeout(closeTimer);
      setProfileOpen(true);
    });
    profile.addEventListener('mouseleave', function () {
      closeTimer = setTimeout(function () {
        setProfileOpen(false);
      }, 150);
    });
  }

  document.addEventListener('click', function (e) {
    if (!profile.contains(e.target)) {
      setProfileOpen(false);
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && profile.classList.contains('open')) {
      setProfileOpen(false);
    }
  });
})();
