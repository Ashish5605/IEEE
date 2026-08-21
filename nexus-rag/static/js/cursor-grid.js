// CursorGrid — vanilla port of the React Bits component.
// A lattice whose cells light up near the pointer, hold, then fade. Canvas 2D,
// no dependencies in the original and none here.
//
// One deviation: the original binds pointer events to its own canvas. Used as a
// full-page background the canvas must be pointer-events:none so it doesn't eat
// clicks, which would leave it deaf. So listeners go on a configurable target
// (default: window) and coordinates are mapped through the canvas rect.

const FALLOFF_CURVES = {
  linear: (t) => t,
  smooth: (t) => t * t * (3 - 2 * t),
  sharp:  (t) => t * t * t,
};

const hexToRgb = (hex) => {
  const h = hex.replace('#', '');
  const v = h.length === 3 ? h.split('').map((c) => c + c).join('') : h;
  const num = parseInt(v.slice(0, 6), 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
};

const DEFAULTS = {
  cellSize: 70,
  color: '#D946EF',
  radius: 140,
  falloff: 'smooth',
  holdTime: 400,
  fadeDuration: 800,
  lineWidth: 1.2,
  maxOpacity: 1,
  fillOpacity: 0,
  gridOpacity: 0,
  cellRadius: 0,
  clickPulse: true,
  pulseSpeed: 600,
  listenTarget: null,   // vanilla addition; defaults to window
};

export class CursorGrid {
  constructor(container, options = {}) {
    this.container = container;
    this.p = { ...DEFAULTS, ...options };
    this.destroyed = false;

    const canvas = document.createElement('canvas');
    canvas.className = 'cursor-grid__canvas';
    canvas.style.cssText = 'display:block;width:100%;height:100%';
    container.appendChild(canvas);
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);

    this.cols = 0; this.rows = 0; this.offX = 0; this.offY = 0;
    this.alphas = new Float32Array(0);
    this.touched = new Float64Array(0);
    this.w = 0; this.h = 0;
    this.pulses = [];
    this.raf = 0; this.running = false; this.lastFrame = 0;

    this._draw = this._draw.bind(this);
    this._rebuild();

    this.ro = new ResizeObserver(() => { this._rebuild(); this._wake(); });
    this.ro.observe(container);

    const target = this.p.listenTarget || window;
    this.target = target;
    this._onMove = (e) => { const [x, y] = this._toLocal(e); this._energize(x, y); this._wake(); };
    this._onDown = (e) => {
      if (!this.p.clickPulse) return;
      const [x, y] = this._toLocal(e);
      this.pulses.push({ x, y, t0: performance.now() });
      this._wake();
    };
    target.addEventListener('pointermove', this._onMove, { passive: true });
    target.addEventListener('pointerdown', this._onDown, { passive: true });

    this._wake();
  }

  setOptions(patch = {}) {
    const needsRebuild = patch.cellSize !== undefined && patch.cellSize !== this.p.cellSize;
    Object.assign(this.p, patch);
    if (needsRebuild) this._rebuild();
    this._wake();
  }

  _rebuild() {
    const p = this.p;
    this.w = this.container.offsetWidth;
    this.h = this.container.offsetHeight;
    this.canvas.width = Math.max(1, Math.round(this.w * this.dpr));
    this.canvas.height = Math.max(1, Math.round(this.h * this.dpr));
    this.canvas.style.width = `${this.w}px`;
    this.canvas.style.height = `${this.h}px`;
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this.cols = Math.ceil(this.w / p.cellSize) + 1;
    this.rows = Math.ceil(this.h / p.cellSize) + 1;
    // Centre the lattice so edge cells crop evenly on both sides.
    this.offX = (this.w - this.cols * p.cellSize) / 2;
    this.offY = (this.h - this.rows * p.cellSize) / 2;
    this.alphas = new Float32Array(this.cols * this.rows);
    this.touched = new Float64Array(this.cols * this.rows);
  }

  _toLocal(e) {
    const rect = this.canvas.getBoundingClientRect();
    return [e.clientX - rect.left, e.clientY - rect.top];
  }

  _cellCenter(i) {
    const p = this.p;
    return [
      this.offX + (i % this.cols) * p.cellSize + p.cellSize / 2,
      this.offY + Math.floor(i / this.cols) * p.cellSize + p.cellSize / 2,
    ];
  }

  // Light every cell whose centre falls inside the radius, with the configured
  // falloff mapping distance to brightness.
  _energize(x, y, boost) {
    const p = this.p;
    const r = Math.max(p.radius, 1);
    const ease = FALLOFF_CURVES[p.falloff] ?? FALLOFF_CURVES.linear;
    const now = performance.now();
    const minCol = Math.max(0, Math.floor((x - r - this.offX) / p.cellSize));
    const maxCol = Math.min(this.cols - 1, Math.floor((x + r - this.offX) / p.cellSize));
    const minRow = Math.max(0, Math.floor((y - r - this.offY) / p.cellSize));
    const maxRow = Math.min(this.rows - 1, Math.floor((y + r - this.offY) / p.cellSize));
    for (let cRow = minRow; cRow <= maxRow; cRow++) {
      for (let cCol = minCol; cCol <= maxCol; cCol++) {
        const i = cRow * this.cols + cCol;
        const [cx, cy] = this._cellCenter(i);
        const dist = Math.hypot(cx - x, cy - y);
        if (dist > r) continue;
        const level = ease(1 - dist / r) * p.maxOpacity * (boost ?? 1);
        if (level > this.alphas[i]) { this.alphas[i] = level; this.touched[i] = now; }
        else if (level > 0) { this.touched[i] = now; }
      }
    }
  }

  _draw(now) {
    if (this.destroyed) return;
    const p = this.p, ctx = this.ctx;
    const dt = Math.min(now - this.lastFrame, 50);
    this.lastFrame = now;
    ctx.clearRect(0, 0, this.w, this.h);
    const [cr, cg, cb] = hexToRgb(p.color);

    if (p.gridOpacity > 0) {
      ctx.strokeStyle = `rgba(${cr}, ${cg}, ${cb}, ${p.gridOpacity})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let c = 0; c <= this.cols; c++) {
        const x = Math.round(this.offX + c * p.cellSize) + 0.5;
        ctx.moveTo(x, 0); ctx.lineTo(x, this.h);
      }
      for (let r = 0; r <= this.rows; r++) {
        const y = Math.round(this.offY + r * p.cellSize) + 0.5;
        ctx.moveTo(0, y); ctx.lineTo(this.w, y);
      }
      ctx.stroke();
    }

    // Expanding click pulses hand energy to cells as the ring passes.
    for (let pi = this.pulses.length - 1; pi >= 0; pi--) {
      const pulse = this.pulses[pi];
      const age = (now - pulse.t0) / 1000;
      const ringR = age * p.pulseSpeed;
      if (ringR > Math.hypot(this.w, this.h)) { this.pulses.splice(pi, 1); continue; }
      const band = p.cellSize;
      const minCol = Math.max(0, Math.floor((pulse.x - ringR - band - this.offX) / p.cellSize));
      const maxCol = Math.min(this.cols - 1, Math.floor((pulse.x + ringR + band - this.offX) / p.cellSize));
      const minRow = Math.max(0, Math.floor((pulse.y - ringR - band - this.offY) / p.cellSize));
      const maxRow = Math.min(this.rows - 1, Math.floor((pulse.y + ringR + band - this.offY) / p.cellSize));
      for (let cRow = minRow; cRow <= maxRow; cRow++) {
        for (let cCol = minCol; cCol <= maxCol; cCol++) {
          const i = cRow * this.cols + cCol;
          const [cx, cy] = this._cellCenter(i);
          const dist = Math.hypot(cx - pulse.x, cy - pulse.y);
          if (Math.abs(dist - ringR) < band / 2 && p.maxOpacity > this.alphas[i]) {
            this.alphas[i] = p.maxOpacity; this.touched[i] = now;
          }
        }
      }
    }

    let anyVisible = this.pulses.length > 0;
    const fadeStep = dt / Math.max(p.fadeDuration, 16);
    const half = p.cellSize / 2;

    for (let i = 0; i < this.alphas.length; i++) {
      let a = this.alphas[i];
      if (a <= 0) continue;
      if (now - this.touched[i] > p.holdTime) {
        a = Math.max(0, a - fadeStep);
        this.alphas[i] = a;
        if (a <= 0) continue;
      }
      anyVisible = true;

      const [cx, cy] = this._cellCenter(i);
      const gradient = ctx.createRadialGradient(cx, cy, half * 0.1, cx, cy, p.cellSize);
      gradient.addColorStop(0, `rgba(${cr}, ${cg}, ${cb}, ${a})`);
      gradient.addColorStop(1, `rgba(${cr}, ${cg}, ${cb}, 0)`);

      const x = cx - half + 0.5, y = cy - half + 0.5, s = p.cellSize - 1;
      ctx.beginPath();
      if (p.cellRadius > 0) ctx.roundRect(x, y, s, s, p.cellRadius);
      else ctx.rect(x, y, s, s);

      if (p.fillOpacity > 0) {
        ctx.fillStyle = `rgba(${cr}, ${cg}, ${cb}, ${a * p.fillOpacity})`;
        ctx.fill();
      }
      ctx.strokeStyle = gradient;
      ctx.lineWidth = p.lineWidth;
      ctx.stroke();
    }

    // Sleeps when nothing is lit — no idle rAF burn.
    if (anyVisible) {
      this.raf = requestAnimationFrame(this._draw);
    } else {
      this.running = false;
      if (p.gridOpacity <= 0) ctx.clearRect(0, 0, this.w, this.h);
    }
  }

  _wake() {
    if (this.running || this.destroyed) return;
    this.running = true;
    this.lastFrame = performance.now();
    this.raf = requestAnimationFrame(this._draw);
  }

  destroy() {
    this.destroyed = true;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.ro.disconnect();
    this.target.removeEventListener('pointermove', this._onMove);
    this.target.removeEventListener('pointerdown', this._onDown);
    this.canvas.remove();
  }
}

window.CursorGrid = CursorGrid;
export default CursorGrid;
