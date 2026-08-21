// Vector Sky — the signature element.
// Every indexed chunk is a star, positioned by its real PCA coordinates from
// /api/semantic_map. On query submit, lines draw outward from the query point to
// each retrieved chunk, forming a constellation, then settle back to idle drift.
//
// Canvas 2D rather than WebGL: this is points and lines, so the GPU pipeline buys
// nothing, and 2D stays crisp on HiDPI with a fraction of the cost.

const TAU = Math.PI * 2;

export class VectorSky {
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.points = [];
    this.hits = new Set();
    this.queryPoint = null;
    this.constellation = 0;      // 0 = idle, ramps to 1 while forming
    this.forming = false;
    this.raf = 0;
    this.t0 = performance.now();
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);

    this.colors = {
      star: opts.star || '#7A7E88',
      retrieval: opts.retrieval || '#4FD6C4',
      signal: opts.signal || '#FF9F5B',
    };
    this.dim = opts.dim || 1;    // overall opacity multiplier

    this.reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    this._resize = this._resize.bind(this);
    this._frame = this._frame.bind(this);
    this.ro = new ResizeObserver(this._resize);
    this.ro.observe(canvas.parentElement || canvas);
    this._resize();

    this.io = new IntersectionObserver(([e]) => {
      this.visible = e.isIntersecting;
      this.visible ? this.start() : this.stop();
    }, { threshold: 0 });
    this.io.observe(canvas);
    this.visible = true;
    this.screen = [];
    this.scoreById = {};
    this._bindHover();
    this.start();
  }

  /**
   * Stars cluster tightly when their chunks are semantically close, so a single
   * dot can be several sources stacked. Hover reports every star under the
   * pointer, not just the nearest one.
   */
  _bindHover() {
    const HIT = 14;
    this.canvas.style.pointerEvents = 'auto';

    this.tip = document.createElement('div');
    this.tip.className = 'sky-tip';
    this.tip.hidden = true;
    (this.canvas.parentElement || document.body).appendChild(this.tip);

    this._onHover = (e) => {
      if (!this.screen || !this.screen.length) { this.tip.hidden = true; return; }
      const rect = this.canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const under = this.screen
        .map((s) => ({ ...s, d: Math.hypot(s.x - mx, s.y - my) }))
        .filter((s) => s.d <= HIT)
        .sort((a, b) => a.d - b.d);

      if (!under.length) { this.tip.hidden = true; return; }

      const seen = new Set();
      const rows = [];
      for (const u of under) {
        const key = u.p.id;
        if (seen.has(key)) continue;
        seen.add(key);
        const score = this.scoreById[u.p.id];
        const page = u.p.page ? ` · p.${u.p.page}` : '';
        rows.push(`<div class="sky-tip__row"><span>${u.p.source}</span>` +
                  `<em>${score !== undefined ? score : ''}${page}</em></div>`);
      }
      this.tip.innerHTML =
        (rows.length > 1 ? `<div class="sky-tip__count">${rows.length} sources here</div>` : '') + rows.join('');
      this.tip.hidden = false;
      // Keep the tip inside the panel.
      const tw = this.tip.offsetWidth || 200;
      this.tip.style.left = Math.max(4, Math.min(mx + 12, rect.width - tw - 4)) + 'px';
      this.tip.style.top = Math.max(4, my + 14) + 'px';
    };
    this._onLeave = () => { this.tip.hidden = true; };
    this.canvas.addEventListener('pointermove', this._onHover);
    this.canvas.addEventListener('pointerleave', this._onLeave);
  }

  _resize() {
    const host = this.canvas.parentElement || this.canvas;
    const w = Math.max(1, host.clientWidth);
    const h = Math.max(1, host.clientHeight);
    this.w = w; this.h = h;
    this.canvas.width = Math.floor(w * this.dpr);
    this.canvas.height = Math.floor(h * this.dpr);
    this.canvas.style.width = w + 'px';
    this.canvas.style.height = h + 'px';
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
  }

  setPoints(points) {
    // Each star keeps a random phase so the field drifts organically rather than
    // pulsing in lockstep.
    this.points = (points || []).map((p, i) => ({
      id: p.id,
      source: p.source,
      x: p.x,
      y: p.y,
      phase: (i * 2.399963) % TAU,   // golden-angle spread
      speed: 0.35 + ((i * 37) % 40) / 100,
      mag: 0.8 + ((i * 17) % 45) / 100,
    }));
  }

  setDim(dim) { this.dim = dim; }

  /** scores: optional array parallel to retrievedIds, for the hover tooltip. */
  showConstellation(retrievedIds, queryPoint, grounded = true, scores = null) {
    this.hits = new Set(retrievedIds || []);
    this.scoreById = {};
    if (scores && retrievedIds) retrievedIds.forEach((id, i) => { this.scoreById[id] = scores[i]; });
    this.queryPoint = queryPoint || null;
    // A failed search still shows where it looked, but must never render those
    // near-misses in the retrieval colour — that would claim a grounded answer.
    this.grounded = grounded !== false;
    if (this.reduce) { this.constellation = 1; this.forming = false; this._draw(performance.now()); return; }
    this.constellation = 0;
    this.forming = true;
    this.formStart = performance.now();
    this.start();
  }

  clearConstellation() {
    this.hits = new Set();
    this.queryPoint = null;
    this.constellation = 0;
    this.forming = false;
    this.grounded = true;
  }

  _px(x) { return 26 + x * (this.w - 52); }
  _py(y) { return 22 + (1 - y) * (this.h - 44); }

  _draw(now) {
    const { ctx, w, h } = this;
    const t = (now - this.t0) / 1000;
    ctx.clearRect(0, 0, w, h);
    if (!this.points.length) return;

    const drift = this.reduce ? 0 : 1;
    const glob = this.dim;

    // Constellation lines first, so stars sit on top of them.
    if (this.queryPoint && this.constellation > 0) {
      const qx = this._px(this.queryPoint.x);
      const qy = this._py(this.queryPoint.y);
      ctx.lineWidth = 1;
      for (const p of this.points) {
        if (!this.hits.has(p.id)) continue;
        const dx = Math.sin(t * p.speed + p.phase) * 2.2 * drift;
        const dy = Math.cos(t * p.speed * 0.8 + p.phase) * 2.2 * drift;
        const sx = this._px(p.x) + dx;
        const sy = this._py(p.y) + dy;
        // Each line grows from the query point outward.
        const ex = qx + (sx - qx) * this.constellation;
        const ey = qy + (sy - qy) * this.constellation;
        ctx.strokeStyle = this.colors.signal;
        ctx.globalAlpha = (this.grounded ? 0.62 : 0.16) * this.constellation * glob;
        if (!this.grounded) ctx.setLineDash([2, 3]); else ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(qx, qy);
        ctx.lineTo(ex, ey);
        ctx.stroke();
      }
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    // Stars. Screen positions are recorded as they are drawn so the pointer can
    // hit-test them — canvas has no DOM nodes to hover.
    this.screen = [];
    for (const p of this.points) {
      const dx = Math.sin(t * p.speed + p.phase) * 2.2 * drift;
      const dy = Math.cos(t * p.speed * 0.8 + p.phase) * 2.2 * drift;
      const x = this._px(p.x) + dx;
      const y = this._py(p.y) + dy;
      const hit = this.hits.has(p.id);
      if (hit) this.screen.push({ p, x: this._px(p.x) + (this.reduce ? 0 : Math.sin(t * p.speed + p.phase) * 2.2),
                                     y: this._py(1 - p.y) + (this.reduce ? 0 : Math.cos(t * p.speed * 0.8 + p.phase) * 2.2) });
      if (!hit) continue;

      if (hit && !this.grounded) {
        // Considered, rejected: a faint ring in the star colour, no fill glow.
        ctx.strokeStyle = this.colors.star;
        ctx.globalAlpha = 0.5 * glob;
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.arc(x, y, 5, 0, TAU); ctx.stroke();
        ctx.fillStyle = this.colors.star;
        ctx.globalAlpha = 0.85 * glob;
        ctx.beginPath(); ctx.arc(x, y, 2.1, 0, TAU); ctx.fill();
      } else if (hit) {
        const grow = Math.max(0.05, 0.6 + 0.4 * this.constellation);
        ctx.fillStyle = this.colors.retrieval;
        ctx.globalAlpha = (0.18 + 0.22 * this.constellation) * glob;
        ctx.beginPath(); ctx.arc(x, y, 13 * grow, 0, TAU); ctx.fill();
        ctx.globalAlpha = (0.4 + 0.4 * this.constellation) * glob;
        ctx.beginPath(); ctx.arc(x, y, 6.5 * grow, 0, TAU); ctx.fill();
        ctx.globalAlpha = glob;
        ctx.beginPath(); ctx.arc(x, y, 3 * grow, 0, TAU); ctx.fill();
      }
      // Un-retrieved chunks are deliberately not drawn: a field of grey dots
      // reads as visual noise, not information.
    }

    // The query itself.
    if (this.queryPoint && this.constellation > 0) {
      const qx = this._px(this.queryPoint.x);
      const qy = this._py(this.queryPoint.y);
      ctx.fillStyle = this.colors.signal;
      ctx.globalAlpha = 0.18 * this.constellation * glob;
      ctx.beginPath(); ctx.arc(qx, qy, 18, 0, TAU); ctx.fill();
      ctx.globalAlpha = 0.3 * this.constellation * glob;
      ctx.beginPath(); ctx.arc(qx, qy, 8, 0, TAU); ctx.fill();
      ctx.globalAlpha = glob;
      ctx.beginPath(); ctx.arc(qx, qy, 3.2, 0, TAU); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  _frame(now) {
    if (this.stopped) return;
    this.raf = requestAnimationFrame(this._frame);
    if (this.forming) {
      // rAF hands us the frame-start timestamp, which can predate the
      // performance.now() captured in showConstellation. Without a lower clamp
      // k goes negative, the cubic amplifies it, and radii turn negative.
      const k = Math.max(0, Math.min(1, (now - this.formStart) / 900));
      // ease-out cubic: lines shoot out then settle
      this.constellation = 1 - Math.pow(1 - k, 3);
      if (k >= 1) this.forming = false;
    }
    this._draw(now);
  }

  start() {
    if (this.stopped) return;
    if (this.raf === 0 && this.visible) this.raf = requestAnimationFrame(this._frame);
  }

  stop() {
    if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
  }

  destroy() {
    this.stopped = true;
    this.stop();
    this.ro.disconnect();
    this.io.disconnect();
    if (this._onHover) {
      this.canvas.removeEventListener('pointermove', this._onHover);
      this.canvas.removeEventListener('pointerleave', this._onLeave);
    }
    if (this.tip) this.tip.remove();
  }
}

export default VectorSky;
