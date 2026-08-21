// TiltedCard — vanilla port of the React Bits component.
//
// The original uses `motion/react` springs. There is no React or bundler here,
// so the springs are integrated manually in a rAF loop with the same constants
// (damping 30, stiffness 100, mass 2) — the motion feels the same without the
// dependency. imageSrc is optional: with no image the card renders its overlay
// content over a plain surface, which is how it is used on the landing page.

const SPRING = { damping: 30, stiffness: 100, mass: 2 };
const CAPTION_SPRING = { damping: 30, stiffness: 350, mass: 1 };

class Spring {
  constructor(value, cfg) {
    this.value = value; this.target = value; this.v = 0; this.cfg = cfg;
  }
  set(t) { this.target = t; }
  step(dt) {
    const { damping, stiffness, mass } = this.cfg;
    const f = -stiffness * (this.value - this.target);
    const d = -damping * this.v;
    const a = (f + d) / mass;
    this.v += a * dt;
    this.value += this.v * dt;
    return this.value;
  }
  get settled() {
    return Math.abs(this.value - this.target) < 0.001 && Math.abs(this.v) < 0.001;
  }
}

const DEFAULTS = {
  imageSrc: null,
  altText: 'Tilted card image',
  captionText: '',
  containerHeight: '300px',
  containerWidth: '100%',
  imageHeight: '300px',
  imageWidth: '300px',
  scaleOnHover: 1.1,
  rotateAmplitude: 14,
  showMobileWarning: true,
  showTooltip: true,
  overlayContent: null,     // HTML string or Node
  displayOverlayContent: false,
  href: null,               // vanilla addition: makes the whole card a link
  className: '',
};

export class TiltedCard {
  constructor(mount, options = {}) {
    this.o = { ...DEFAULTS, ...options };
    this.reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.rotX = new Spring(0, SPRING);
    this.rotY = new Spring(0, SPRING);
    this.scale = new Spring(1, SPRING);
    this.opacity = new Spring(0, SPRING);
    this.capRot = new Spring(0, CAPTION_SPRING);
    this.lastY = 0;
    this.raf = 0;
    this.px = 0; this.py = 0;
    this._build(mount);
  }

  _build(mount) {
    const o = this.o;
    const fig = document.createElement(o.href ? 'a' : 'figure');
    if (o.href) { fig.href = o.href; fig.style.textDecoration = 'none'; fig.style.color = 'inherit'; }
    fig.className = ('tilted-card-figure ' + (o.className || '')).trim();
    fig.style.height = o.containerHeight;
    fig.style.width = o.containerWidth;
    this.fig = fig;

    if (o.showMobileWarning) {
      const w = document.createElement('div');
      w.className = 'tilted-card-mobile-alert';
      w.textContent = 'This effect is not optimized for mobile. Check on desktop.';
      fig.appendChild(w);
    }

    const inner = document.createElement('div');
    inner.className = 'tilted-card-inner';
    inner.style.width = o.imageWidth;
    inner.style.height = o.imageHeight;
    this.inner = inner;

    if (o.imageSrc) {
      const img = document.createElement('img');
      img.src = o.imageSrc; img.alt = o.altText;
      img.className = 'tilted-card-img';
      img.style.width = o.imageWidth; img.style.height = o.imageHeight;
      inner.appendChild(img);
    }

    if (o.displayOverlayContent && o.overlayContent) {
      const ov = document.createElement('div');
      ov.className = 'tilted-card-overlay';
      ov.style.width = o.imageWidth; ov.style.height = o.imageHeight;
      if (typeof o.overlayContent === 'string') ov.innerHTML = o.overlayContent;
      else ov.appendChild(o.overlayContent);
      inner.appendChild(ov);
    }
    fig.appendChild(inner);

    if (o.showTooltip && o.captionText) {
      const cap = document.createElement('figcaption');
      cap.className = 'tilted-card-caption';
      cap.textContent = o.captionText;
      this.cap = cap;
      fig.appendChild(cap);
    }

    mount.appendChild(fig);

    if (!this.reduce) {
      this._onMove = (e) => this._handleMouse(e);
      this._onEnter = () => { this.scale.set(o.scaleOnHover); this.opacity.set(1); this._start(); };
      this._onLeave = () => {
        this.opacity.set(0); this.scale.set(1);
        this.rotX.set(0); this.rotY.set(0); this.capRot.set(0); this._start();
      };
      fig.addEventListener('mousemove', this._onMove);
      fig.addEventListener('mouseenter', this._onEnter);
      fig.addEventListener('mouseleave', this._onLeave);
    }
  }

  _handleMouse(e) {
    const rect = this.fig.getBoundingClientRect();
    const offsetX = e.clientX - rect.left - rect.width / 2;
    const offsetY = e.clientY - rect.top - rect.height / 2;
    this.rotX.set((offsetY / (rect.height / 2)) * -this.o.rotateAmplitude);
    this.rotY.set((offsetX / (rect.width / 2)) * this.o.rotateAmplitude);
    this.px = e.clientX - rect.left;
    this.py = e.clientY - rect.top;
    const velocityY = offsetY - this.lastY;
    this.capRot.set(-velocityY * 0.6);
    this.lastY = offsetY;
    this._start();
  }

  _start() {
    if (this.raf) return;
    this.last = performance.now();
    const tick = (now) => {
      const dt = Math.min(0.032, (now - this.last) / 1000);
      this.last = now;
      const rx = this.rotX.step(dt), ry = this.rotY.step(dt), sc = this.scale.step(dt);
      const op = this.opacity.step(dt), cr = this.capRot.step(dt);
      this.inner.style.transform =
        `rotateX(${rx}deg) rotateY(${ry}deg) scale(${sc})`;
      if (this.cap) {
        this.cap.style.opacity = String(Math.max(0, op));
        this.cap.style.transform = `translate(${this.px}px, ${this.py}px) rotate(${cr}deg)`;
      }
      const settled = this.rotX.settled && this.rotY.settled && this.scale.settled &&
                      this.opacity.settled && this.capRot.settled;
      this.raf = settled ? 0 : requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  destroy() {
    if (this.raf) cancelAnimationFrame(this.raf);
    if (this._onMove) {
      this.fig.removeEventListener('mousemove', this._onMove);
      this.fig.removeEventListener('mouseenter', this._onEnter);
      this.fig.removeEventListener('mouseleave', this._onLeave);
    }
    this.fig.remove();
  }
}

window.TiltedCard = TiltedCard;
export default TiltedCard;
