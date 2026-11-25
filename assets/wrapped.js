// Story navigation: tap left third = back, elsewhere = forward; arrow keys; swipe.
(function () {
  const story = document.querySelector('.story');
  const stats = document.getElementById('stats');
  if (!story) return;
  const slides = [...story.querySelectorAll('.slide')];
  const bar = story.querySelector('.progress');
  bar.innerHTML = slides.map(() => '<i></i>').join('');
  const ticks = [...bar.children];
  let i = 0;

  function show(n) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    slides.forEach((s, k) => s.classList.toggle('active', k === i));
    ticks.forEach((t, k) => { t.className = k < i ? 'done' : k === i ? 'now' : ''; });
  }
  function openStats() {
    document.body.classList.add('show-stats');
    stats.hidden = false;
    window.scrollTo(0, 0);
    if (location.hash !== '#stats') history.replaceState(null, '', '#stats');
  }
  function replay() {
    document.body.classList.remove('show-stats');
    stats.hidden = true;
    history.replaceState(null, '', location.pathname);
    show(0);
  }

  document.addEventListener('click', (ev) => {
    const act = ev.target.closest('[data-action]');
    if (act) {
      ev.preventDefault();
      act.dataset.action === 'stats' ? openStats() : replay();
      return;
    }
    if (document.body.classList.contains('show-stats') || !story.contains(ev.target)) return;
    const r = story.getBoundingClientRect();
    show(ev.clientX - r.left < r.width / 3 ? i - 1 : i + 1);
  });
  document.addEventListener('keydown', (ev) => {
    if (document.body.classList.contains('show-stats')) return;
    if (ev.key === 'ArrowRight' || ev.key === ' ') { ev.preventDefault(); show(i + 1); }
    if (ev.key === 'ArrowLeft') show(i - 1);
    if (ev.key === 'Escape') openStats();
  });
  let x0 = null;
  story.addEventListener('touchstart', (ev) => { x0 = ev.touches[0].clientX; }, { passive: true });
  story.addEventListener('touchend', (ev) => {
    if (x0 === null) return;
    const dx = ev.changedTouches[0].clientX - x0;
    x0 = null;
    if (Math.abs(dx) > 50) { ev.preventDefault(); show(dx < 0 ? i + 1 : i - 1); }
  });

  const deep = /^#slide-(\d+)$/.exec(location.hash);  // e.g. #slide-3 opens the third slide
  show(deep ? +deep[1] - 1 : 0);
  if (location.hash === '#stats') openStats();
})();
