// Theme switch. Dark is the default; the choice persists per browser.
// Tokens live in CSS under [data-theme="light"]; this only flips the attribute.
(function () {
  const KEY = 'nexora-theme';
  let stored = null;
  try { stored = localStorage.getItem(KEY); } catch (e) { /* private mode */ }
  if (stored === 'light') document.documentElement.setAttribute('data-theme', 'light');

  window.NexoraTheme = {
    get() {
      return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    },
    set(mode) {
      const root = document.documentElement;
      // Suppress the global transition on first paint so the page does not
      // visibly cross-fade on load.
      root.classList.add('theme-animating');
      if (mode === 'light') root.setAttribute('data-theme', 'light');
      else root.removeAttribute('data-theme');
      try { localStorage.setItem(KEY, mode); } catch (e) {}
      window.dispatchEvent(new CustomEvent('themechange', { detail: { mode } }));
      setTimeout(() => root.classList.remove('theme-animating'), 480);
    },
    toggle() { this.set(this.get() === 'light' ? 'dark' : 'light'); },
    mount(btn) {
      if (!btn) return;
      const paint = () => {
        const light = this.get() === 'light';
        btn.innerHTML = `<span class="material-symbols-outlined" style="font-size:17px">${light ? 'dark_mode' : 'light_mode'}</span>`;
        btn.setAttribute('aria-label', light ? 'Switch to dark theme' : 'Switch to light theme');
        btn.title = btn.getAttribute('aria-label');
      };
      btn.addEventListener('click', () => { this.toggle(); paint(); });
      paint();
    },
  };
})();
