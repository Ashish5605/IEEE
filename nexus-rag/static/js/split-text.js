// SplitText — vanilla equivalent of the React Bits component.
//
// The original depends on GSAP core, GSAP's SplitText plugin and @gsap/react.
// None of that is available here (no bundler, no React), so this implements the
// same effect and the same prop surface directly: split the text, then stagger
// each piece from `from` to `to` when it scrolls into view.
//
// Uses the Web Animations API rather than GSAP — the effect is a staggered
// transform/opacity tween, which WAAPI does natively and on the compositor.

const EASE_MAP = {
  'power1.out': 'cubic-bezier(0.25, 0.46, 0.45, 0.94)',
  'power2.out': 'cubic-bezier(0.22, 0.61, 0.36, 1)',
  'power3.out': 'cubic-bezier(0.165, 0.84, 0.44, 1)',
  'power4.out': 'cubic-bezier(0.23, 1, 0.32, 1)',
  'back.out':   'cubic-bezier(0.34, 1.56, 0.64, 1)',
  'expo.out':   'cubic-bezier(0.19, 1, 0.22, 1)',
};

const DEFAULTS = {
  text: '',
  delay: 50,               // ms between pieces
  duration: 1.25,          // seconds per piece
  ease: 'power3.out',
  splitType: 'chars',      // 'chars' | 'words' | 'lines'
  from: { opacity: 0, y: 40 },
  to: { opacity: 1, y: 0 },
  threshold: 0.1,
  rootMargin: '-100px',
  textAlign: 'center',
  onLetterAnimationComplete: null,
};

function toTransform(state) {
  const parts = [];
  if (state.y !== undefined) parts.push(`translateY(${state.y}px)`);
  if (state.x !== undefined) parts.push(`translateX(${state.x}px)`);
  if (state.scale !== undefined) parts.push(`scale(${state.scale})`);
  if (state.rotate !== undefined) parts.push(`rotate(${state.rotate}deg)`);
  return parts.length ? parts.join(' ') : 'none';
}

export class SplitText {
  constructor(el, options = {}) {
    this.el = el;
    this.o = { ...DEFAULTS, ...options };
    this.done = false;
    this._split();
    this._observe();
  }

  _split() {
    const o = this.o;
    const text = o.text || this.el.textContent || '';
    this.el.textContent = '';
    this.el.style.textAlign = o.textAlign;
    this.pieces = [];

    // Split into words first so wrapping stays natural; chars nest inside.
    const words = String(text).split(/(\s+)/);
    for (const w of words) {
      if (/^\s+$/.test(w)) { this.el.appendChild(document.createTextNode(w)); continue; }
      const wordSpan = document.createElement('span');
      wordSpan.className = 'split-word';
      wordSpan.style.display = 'inline-block';
      wordSpan.style.whiteSpace = 'pre';

      if (o.splitType.includes('chars')) {
        for (const ch of Array.from(w)) {
          const c = document.createElement('span');
          c.className = 'split-char';
          c.style.display = 'inline-block';
          c.style.willChange = 'transform, opacity';
          c.textContent = ch;
          wordSpan.appendChild(c);
          this.pieces.push(c);
        }
      } else {
        wordSpan.style.willChange = 'transform, opacity';
        wordSpan.textContent = w;
        this.pieces.push(wordSpan);
      }
      this.el.appendChild(wordSpan);
    }

    // Park every piece at the `from` state until it plays.
    for (const p of this.pieces) {
      p.style.opacity = String(o.from.opacity ?? 1);
      p.style.transform = toTransform(o.from);
    }
  }

  _observe() {
    const o = this.o;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { this.play(true); return; }
    this.io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { this.play(); this.io.disconnect(); }
    }, { threshold: o.threshold, rootMargin: o.rootMargin });
    this.io.observe(this.el);
  }

  play(instant = false) {
    if (this.done) return;
    this.done = true;
    const o = this.o;
    const easing = EASE_MAP[o.ease] || o.ease || 'ease-out';
    const durMs = instant ? 0 : o.duration * 1000;

    this.pieces.forEach((p, i) => {
      const delay = instant ? 0 : i * o.delay;
      const anim = p.animate(
        [
          { opacity: o.from.opacity ?? 1, transform: toTransform(o.from) },
          { opacity: o.to.opacity ?? 1, transform: toTransform(o.to) },
        ],
        { duration: durMs, delay, easing, fill: 'forwards' }
      );
      if (i === this.pieces.length - 1 && typeof o.onLetterAnimationComplete === 'function') {
        anim.addEventListener('finish', () => o.onLetterAnimationComplete());
      }
    });
  }

  destroy() { if (this.io) this.io.disconnect(); }
}

window.SplitText = SplitText;
export default SplitText;
