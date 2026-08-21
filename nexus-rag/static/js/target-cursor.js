// TargetCursor — vanilla port of the React Bits component.
// A spinning bracket cursor that snaps around any `.cursor-target` element.
// The original is already imperative GSAP inside useEffect; only the refs and
// effect wiring are replaced. gsap loads from a CDN (no bundler here).
import { gsap } from 'https://esm.sh/gsap@3.13.0';

// position:fixed is relative to the viewport UNLESS an ancestor creates a
// containing block (transform/filter/perspective/contain). Then the cursor's
// translate no longer maps to viewport coords, so measure and compensate.
const getContainingBlock = (element) => {
  let node = element?.parentElement;
  while (node && node !== document.documentElement) {
    const s = getComputedStyle(node);
    if (s.transform !== 'none' || s.perspective !== 'none' || s.filter !== 'none' ||
        s.willChange.includes('transform') || s.willChange.includes('perspective') ||
        s.willChange.includes('filter') || /paint|layout|strict|content/.test(s.contain)) {
      return node;
    }
    node = node.parentElement;
  }
  return null;
};

const getContainingBlockOffset = (block) => {
  if (!block) return { x: 0, y: 0 };
  const r = block.getBoundingClientRect();
  return { x: r.left + block.clientLeft, y: r.top + block.clientTop };
};

const DEFAULTS = {
  targetSelector: '.cursor-target',
  spinDuration: 2,
  hideDefaultCursor: true,
  hoverDuration: 0.2,
  parallaxOn: true,
  cursorColor: '#ffffff',
  cursorColorOnTarget: null,
};

const CONST = { borderWidth: 3, cornerSize: 12 };

export class TargetCursor {
  constructor(options = {}) {
    this.o = { ...DEFAULTS, ...options };

    const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const small = window.innerWidth <= 768;
    const ua = (navigator.userAgent || navigator.vendor || '').toLowerCase();
    const mobileUA = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(ua);
    this.isMobile = (hasTouch && small) || mobileUA;
    // A pointer-driven flourish is meaningless without a pointer, and hiding the
    // system cursor is hostile to anyone who asked for reduced motion.
    this.reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (this.isMobile || this.reduce) return;

    this._build();
    this._init();
  }

  _build() {
    const wrap = document.createElement('div');
    wrap.className = 'target-cursor-wrapper';
    wrap.setAttribute('aria-hidden', 'true');
    const dot = document.createElement('div');
    dot.className = 'target-cursor-dot';
    wrap.appendChild(dot);
    for (const c of ['corner-tl', 'corner-tr', 'corner-br', 'corner-bl']) {
      const el = document.createElement('div');
      el.className = `target-cursor-corner ${c}`;
      wrap.appendChild(el);
    }
    document.body.appendChild(wrap);
    this.cursor = wrap;
    this.dot = dot;
    this.corners = wrap.querySelectorAll('.target-cursor-corner');
  }

  _moveCursor(x, y) {
    const { x: ox, y: oy } = getContainingBlockOffset(this.containingBlock);
    gsap.to(this.cursor, { x: x - ox, y: y - oy, duration: 0.1, ease: 'power3.out' });
  }

  _createSpin() {
    if (this.spinTl) this.spinTl.kill();
    this.spinTl = gsap.timeline({ repeat: -1 })
      .to(this.cursor, { rotation: '+=360', duration: this.o.spinDuration, ease: 'none' });
  }

  _init() {
    const o = this.o;
    this.originalCursor = document.body.style.cursor;
    if (o.hideDefaultCursor) document.body.style.cursor = 'none';

    this.containingBlock = getContainingBlock(this.cursor);
    const getOffset = () => getContainingBlockOffset(this.containingBlock);

    this.activeTarget = null;
    this.currentLeaveHandler = null;
    this.resumeTimeout = null;
    this.targetCorners = null;
    this.strength = { current: 0 };

    const init = getOffset();
    gsap.set(this.cursor, {
      xPercent: -50, yPercent: -50,
      x: window.innerWidth / 2 - init.x,
      y: window.innerHeight / 2 - init.y,
    });
    this._createSpin();

    // Runs on gsap's ticker while a target is hovered — eases the corners
    // toward the target rect, with parallax if enabled.
    this.tickerFn = () => {
      if (!this.targetCorners || !this.cursor) return;
      const s = this.strength.current;
      if (s === 0) return;
      const cx = gsap.getProperty(this.cursor, 'x');
      const cy = gsap.getProperty(this.cursor, 'y');
      Array.from(this.corners).forEach((corner, i) => {
        const curX = gsap.getProperty(corner, 'x');
        const curY = gsap.getProperty(corner, 'y');
        const tX = this.targetCorners[i].x - cx;
        const tY = this.targetCorners[i].y - cy;
        const finalX = curX + (tX - curX) * s;
        const finalY = curY + (tY - curY) * s;
        const duration = s >= 0.99 ? (o.parallaxOn ? 0.2 : 0) : 0.05;
        gsap.to(corner, {
          x: finalX, y: finalY, duration,
          ease: duration === 0 ? 'none' : 'power1.out', overwrite: 'auto',
        });
      });
    };

    this._onMove = (e) => this._moveCursor(e.clientX, e.clientY);
    window.addEventListener('mousemove', this._onMove);

    this._onScroll = () => {
      if (!this.activeTarget) return;
      const { x: ox, y: oy } = getOffset();
      const mx = gsap.getProperty(this.cursor, 'x') + ox;
      const my = gsap.getProperty(this.cursor, 'y') + oy;
      const under = document.elementFromPoint(mx, my);
      const still = under && (under === this.activeTarget || under.closest(o.targetSelector) === this.activeTarget);
      if (!still && this.currentLeaveHandler) this.currentLeaveHandler();
    };
    window.addEventListener('scroll', this._onScroll, { passive: true });

    this._onDown = () => {
      gsap.to(this.dot, { scale: 0.7, duration: 0.3 });
      gsap.to(this.cursor, { scale: 0.9, duration: 0.2 });
    };
    this._onUp = () => {
      gsap.to(this.dot, { scale: 1, duration: 0.3 });
      gsap.to(this.cursor, { scale: 1, duration: 0.2 });
    };
    window.addEventListener('mousedown', this._onDown);
    window.addEventListener('mouseup', this._onUp);

    this._onOver = (e) => this._enter(e, getOffset);
    window.addEventListener('mouseover', this._onOver, { passive: true });

    this._onResize = () => { this.containingBlock = getContainingBlock(this.cursor); };
    window.addEventListener('resize', this._onResize);
  }

  _enter(e, getOffset) {
    const o = this.o;
    let current = e.target, found = null;
    while (current && current !== document.body) {
      if (current.matches && current.matches(o.targetSelector)) { found = current; break; }
      current = current.parentElement;
    }
    if (!found || this.activeTarget === found) return;
    if (this.activeTarget) this._cleanupTarget(this.activeTarget);
    if (this.resumeTimeout) { clearTimeout(this.resumeTimeout); this.resumeTimeout = null; }

    this.activeTarget = found;
    const corners = Array.from(this.corners);
    corners.forEach((c) => gsap.killTweensOf(c, 'x,y'));

    gsap.killTweensOf(this.cursor, 'rotation');
    if (this.spinTl) this.spinTl.pause();
    gsap.set(this.cursor, { rotation: 0 });

    if (o.cursorColorOnTarget) {
      gsap.to(corners, { borderColor: o.cursorColorOnTarget, duration: 0.15, ease: 'power2.out' });
      gsap.to(this.dot, { backgroundColor: o.cursorColorOnTarget, duration: 0.15, ease: 'power2.out' });
    }

    const rect = found.getBoundingClientRect();
    const { borderWidth: bw, cornerSize: cs } = CONST;
    const { x: ox, y: oy } = getOffset();
    const cx = gsap.getProperty(this.cursor, 'x');
    const cy = gsap.getProperty(this.cursor, 'y');

    this.targetCorners = [
      { x: rect.left - bw - ox,            y: rect.top - bw - oy },
      { x: rect.right + bw - cs - ox,      y: rect.top - bw - oy },
      { x: rect.right + bw - cs - ox,      y: rect.bottom + bw - cs - oy },
      { x: rect.left - bw - ox,            y: rect.bottom + bw - cs - oy },
    ];

    gsap.ticker.add(this.tickerFn);
    gsap.to(this.strength, { current: 1, duration: o.hoverDuration, ease: 'power2.out' });

    corners.forEach((corner, i) => {
      gsap.to(corner, {
        x: this.targetCorners[i].x - cx,
        y: this.targetCorners[i].y - cy,
        duration: 0.2, ease: 'power2.out',
      });
    });

    const leaveHandler = () => this._leave(found);
    this.currentLeaveHandler = leaveHandler;
    found.addEventListener('mouseleave', leaveHandler);
  }

  _leave(target) {
    const o = this.o;
    gsap.ticker.remove(this.tickerFn);
    this.targetCorners = null;
    gsap.set(this.strength, { current: 0, overwrite: true });
    this.activeTarget = null;

    if (o.cursorColorOnTarget) {
      gsap.to(Array.from(this.corners), { borderColor: o.cursorColor, duration: 0.15, ease: 'power2.out' });
      gsap.to(this.dot, { backgroundColor: o.cursorColor, duration: 0.15, ease: 'power2.out' });
    }

    const corners = Array.from(this.corners);
    gsap.killTweensOf(corners, 'x,y');
    const cs = CONST.cornerSize;
    const rest = [
      { x: -cs * 1.5, y: -cs * 1.5 }, { x: cs * 0.5, y: -cs * 1.5 },
      { x: cs * 0.5, y: cs * 0.5 },   { x: -cs * 1.5, y: cs * 0.5 },
    ];
    const tl = gsap.timeline();
    corners.forEach((corner, i) => {
      tl.to(corner, { x: rest[i].x, y: rest[i].y, duration: 0.3, ease: 'power3.out' }, 0);
    });

    // Resume the spin from wherever the rotation stopped, so it doesn't snap.
    this.resumeTimeout = setTimeout(() => {
      if (!this.activeTarget && this.cursor && this.spinTl) {
        const rot = gsap.getProperty(this.cursor, 'rotation');
        const norm = rot % 360;
        this.spinTl.kill();
        this._createSpin();
        gsap.to(this.cursor, {
          rotation: norm + 360,
          duration: o.spinDuration * (1 - norm / 360),
          ease: 'none',
          onComplete: () => this.spinTl && this.spinTl.restart(),
        });
      }
      this.resumeTimeout = null;
    }, 50);

    this._cleanupTarget(target);
  }

  _cleanupTarget(target) {
    if (this.currentLeaveHandler) target.removeEventListener('mouseleave', this.currentLeaveHandler);
    this.currentLeaveHandler = null;
  }

  destroy() {
    if (this.isMobile || this.reduce || !this.cursor) return;
    if (this.tickerFn) gsap.ticker.remove(this.tickerFn);
    window.removeEventListener('mousemove', this._onMove);
    window.removeEventListener('mouseover', this._onOver);
    window.removeEventListener('scroll', this._onScroll);
    window.removeEventListener('resize', this._onResize);
    window.removeEventListener('mousedown', this._onDown);
    window.removeEventListener('mouseup', this._onUp);
    if (this.activeTarget) this._cleanupTarget(this.activeTarget);
    if (this.spinTl) this.spinTl.kill();
    document.body.style.cursor = this.originalCursor;
    this.cursor.remove();
  }
}

window.TargetCursor = TargetCursor;
export default TargetCursor;
