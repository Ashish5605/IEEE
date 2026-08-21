// GradualBlur — vanilla port of the React Bits component (by Ansh Dhanani).
// Stacks N absolutely-positioned layers, each with a masked backdrop-filter at
// increasing blur strength, producing a progressive blur ramp rather than a
// single hard blur edge. No dependencies in the original; none here.

const DEFAULT_CONFIG = {
  position: 'bottom',
  strength: 2,
  height: '6rem',
  width: null,
  divCount: 5,
  exponential: false,
  zIndex: 1000,
  animated: false,
  duration: '0.3s',
  easing: 'ease-out',
  opacity: 1,
  curve: 'linear',
  target: 'parent',   // 'parent' | 'page'
  className: '',
};

const PRESETS = {
  top: { position: 'top', height: '6rem' },
  bottom: { position: 'bottom', height: '6rem' },
  left: { position: 'left', height: '6rem' },
  right: { position: 'right', height: '6rem' },
  subtle: { height: '4rem', strength: 1, opacity: 0.8, divCount: 3 },
  intense: { height: '10rem', strength: 4, divCount: 8, exponential: true },
  smooth: { height: '8rem', curve: 'bezier', divCount: 10 },
  sharp: { height: '5rem', curve: 'linear', divCount: 4 },
  header: { position: 'top', height: '8rem', curve: 'ease-out' },
  footer: { position: 'bottom', height: '8rem', curve: 'ease-out' },
  'page-header': { position: 'top', height: '10rem', target: 'page', strength: 3 },
  'page-footer': { position: 'bottom', height: '10rem', target: 'page', strength: 3 },
};

const CURVE_FUNCTIONS = {
  linear: (p) => p,
  bezier: (p) => p * p * (3 - 2 * p),
  'ease-in': (p) => p * p,
  'ease-out': (p) => 1 - Math.pow(1 - p, 2),
  'ease-in-out': (p) => (p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2),
};

const getGradientDirection = (position) =>
  ({ top: 'to top', bottom: 'to bottom', left: 'to left', right: 'to right' }[position] || 'to bottom');

export class GradualBlur {
  constructor(mount, options = {}) {
    const preset = options.preset && PRESETS[options.preset] ? PRESETS[options.preset] : {};
    this.config = { ...DEFAULT_CONFIG, ...preset, ...options };
    this.mount = mount;
    this._build();
  }

  _build() {
    const c = this.config;
    const isVertical = ['top', 'bottom'].includes(c.position);
    const isPage = c.target === 'page';

    const container = document.createElement('div');
    container.className = `gradual-blur ${isPage ? 'gradual-blur-page' : 'gradual-blur-parent'} ${c.className}`.trim();
    container.setAttribute('aria-hidden', 'true');
    Object.assign(container.style, {
      position: isPage ? 'fixed' : 'absolute',
      pointerEvents: 'none',
      opacity: '1',
      zIndex: String(isPage ? c.zIndex + 100 : c.zIndex),
    });

    if (isVertical) {
      container.style.height = c.height;
      container.style.width = c.width || '100%';
      container.style.left = '0';
      container.style.right = '0';
      container.style[c.position] = '0';
    } else {
      container.style.width = c.width || c.height;
      container.style.height = '100%';
      container.style.top = '0';
      container.style.bottom = '0';
      container.style[c.position] = '0';
    }

    const inner = document.createElement('div');
    inner.className = 'gradual-blur-inner';
    Object.assign(inner.style, { position: 'relative', width: '100%', height: '100%' });

    const increment = 100 / c.divCount;
    const curveFunc = CURVE_FUNCTIONS[c.curve] || CURVE_FUNCTIONS.linear;
    const direction = getGradientDirection(c.position);

    for (let i = 1; i <= c.divCount; i++) {
      const progress = curveFunc(i / c.divCount);
      const blurValue = c.exponential
        ? Math.pow(2, progress * 4) * 0.0625 * c.strength
        : 0.0625 * (progress * c.divCount + 1) * c.strength;

      const p1 = Math.round((increment * i - increment) * 10) / 10;
      const p2 = Math.round(increment * i * 10) / 10;
      const p3 = Math.round((increment * i + increment) * 10) / 10;
      const p4 = Math.round((increment * i + increment * 2) * 10) / 10;

      let gradient = `transparent ${p1}%, black ${p2}%`;
      if (p3 <= 100) gradient += `, black ${p3}%`;
      if (p4 <= 100) gradient += `, transparent ${p4}%`;

      const div = document.createElement('div');
      const mask = `linear-gradient(${direction}, ${gradient})`;
      Object.assign(div.style, {
        position: 'absolute',
        inset: '0',
        maskImage: mask,
        WebkitMaskImage: mask,
        backdropFilter: `blur(${blurValue.toFixed(3)}rem)`,
        WebkitBackdropFilter: `blur(${blurValue.toFixed(3)}rem)`,
        opacity: String(c.opacity),
      });
      inner.appendChild(div);
    }

    container.appendChild(inner);
    (isPage ? document.body : this.mount).appendChild(container);
    this.el = container;
  }

  /**
   * Fade the whole ramp in/out. A bottom page-blur signals "there is more
   * below"; at the end of the document that is a lie and it just obscures the
   * footer, so callers fade it out there.
   */
  setVisible(v) {
    if (!this.el) return;
    this.el.style.transition = 'opacity 260ms ease-out';
    this.el.style.opacity = v ? '1' : '0';
  }

  /** Auto-hide near the end of the page scroll. */
  autoHideAtEnd(threshold = 140) {
    const update = () => {
      const doc = document.documentElement;
      const remaining = doc.scrollHeight - window.innerHeight - window.scrollY;
      this.setVisible(remaining > threshold);
    };
    this._onScroll = update;
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
    return this;
  }

  destroy() {
    if (this._onScroll) {
      window.removeEventListener('scroll', this._onScroll);
      window.removeEventListener('resize', this._onScroll);
    }
    if (this.el) this.el.remove();
  }
}

GradualBlur.PRESETS = PRESETS;
window.GradualBlur = GradualBlur;
export default GradualBlur;
