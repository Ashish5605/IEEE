// SpecularButton — vanilla port of the React Bits component.
// A rounded-rect SDF drawn in a canvas that overhangs the button, lighting the
// rim like a specular highlight. The light angle steers toward the pointer and
// falls back to a slow sweep. React refs/effects become a class; the shader,
// the pointer maths and the easing constants are unchanged.
import { Renderer, Program, Mesh, Triangle, Color } from 'https://esm.sh/ogl@1.0.11';

const PAD = 20;

const VERT = `#version 300 es
in vec2 position;
void main() { gl_Position = vec4(position, 0.0, 1.0); }
`;

const FRAG = `#version 300 es
precision highp float;

uniform vec2 uCenter;
uniform vec2 uHalfSize;
uniform float uRadius;
uniform float uAngle;
uniform float uPx;
uniform vec3 uLineColor;
uniform vec3 uBaseColor;
uniform float uIntensity;
uniform float uShineSize;
uniform float uShineFade;
uniform float uThickness;
uniform float uBaseWidth;

out vec4 fragColor;

float sdRoundedRect(vec2 p, vec2 b, float r) {
  vec2 q = abs(p) - b + r;
  return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}
float shapeSDF(vec2 p) { return sdRoundedRect(p, uHalfSize, uRadius); }
float gaussianLine(float d, float sigma) {
  float x = d / (sigma + 1e-6);
  float k = mix(1.0, 1.6, smoothstep(0.0, 1.5, x));
  return exp(-k * x * x);
}

void main() {
  vec2 p = gl_FragCoord.xy - uCenter;
  float d = shapeSDF(p);
  vec2 L = vec2(cos(uAngle), sin(uAngle));

  float base = (1.0 - smoothstep(0.0, uBaseWidth, abs(d))) * 0.45;

  vec2 nEll = normalize(p / (uHalfSize * uHalfSize) + 1e-6);
  float phi = acos(clamp(abs(dot(nEll, L)), 0.0, 1.0));
  float rim = 1.0 - smoothstep(uShineSize - uShineFade, uShineSize + uShineFade + 1e-4, phi);
  float line = gaussianLine(d, uThickness);
  float edgeClamp = 1.0 - smoothstep(0.5 * uPx, 3.0 * uPx, abs(d));
  float hi = line * rim * edgeClamp * uIntensity;

  vec3 col = uBaseColor * base + uLineColor * hi;
  float a = clamp(base + hi, 0.0, 1.0);
  fragColor = vec4(col, a);
}
`;

const DEFAULTS = {
  radius: 18, lineColor: '#ffffff', baseColor: '#525252', intensity: 1,
  shineSize: 10, shineFade: 40, thickness: 1, speed: 0.35,
  followMouse: true, proximity: 250, autoAnimate: false,
};

/**
 * Attaches the effect to an existing <button>. The original renders its own
 * element; here the button already exists in the markup with its handlers, so
 * this decorates it rather than replacing it.
 */
export class SpecularButton {
  constructor(button, options = {}) {
    this.btn = button;
    this.p = { ...DEFAULTS, ...options };
    this.destroyed = false;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    this._init();
  }

  _init() {
    const btn = this.btn;
    btn.classList.add('specular-button');

    const fx = document.createElement('span');
    fx.className = 'specular-button__fx';
    fx.setAttribute('aria-hidden', 'true');
    btn.appendChild(fx);
    this.fx = fx;

    const dpr = window.devicePixelRatio || 1;
    this.dpr = dpr;
    const renderer = new Renderer({ alpha: true, premultipliedAlpha: true, antialias: true, dpr });
    this.renderer = renderer;
    const gl = renderer.gl;
    this.gl = gl;
    gl.clearColor(0, 0, 0, 0);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

    const geometry = new Triangle(gl);
    if (geometry.attributes.uv) delete geometry.attributes.uv;

    this.program = new Program(gl, {
      vertex: VERT, fragment: FRAG,
      uniforms: {
        uCenter: { value: [0, 0] }, uHalfSize: { value: [1, 1] },
        uRadius: { value: 0 }, uAngle: { value: 2.4 }, uPx: { value: dpr },
        uLineColor: { value: [1, 1, 1] }, uBaseColor: { value: [0.32, 0.32, 0.32] },
        uIntensity: { value: 1 }, uShineSize: { value: 0.17 },
        uShineFade: { value: 0.7 }, uThickness: { value: 1 }, uBaseWidth: { value: dpr },
      },
    });
    this.mesh = new Mesh(gl, { geometry, program: this.program });
    fx.appendChild(gl.canvas);

    this.size = { w: 1, h: 1 };
    this._resize = this._resize.bind(this);
    this.ro = new ResizeObserver(this._resize);
    this.ro.observe(btn);
    this._resize();

    this.pointerAngle = null;
    this.proximityT = 0;
    this._onPointerMove = (e) => {
      const rect = this.btn.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = Math.max(rect.left - e.clientX, 0, e.clientX - rect.right);
      const dy = Math.max(rect.top - e.clientY, 0, e.clientY - rect.bottom);
      const dist = Math.hypot(dx, dy);
      if (dist === 0) {
        const nx = (e.clientX - cx) / (rect.width / 2);
        const ny = (cy - e.clientY) / (rect.height / 2);
        this.pointerAngle = Math.atan2(2 / rect.height, -2 / rect.width) + nx * 0.3 + ny * 0.15;
      } else {
        this.pointerAngle = Math.atan2(cy - e.clientY, e.clientX - cx);
      }
      const t = Math.max(0, 1 - dist / Math.max(this.p.proximity, 1));
      this.proximityT = t * t * (3 - 2 * t);
    };
    window.addEventListener('pointermove', this._onPointerMove);

    this.angle = 2.4;
    this.idleAngle = 2.4;
    this.bright = 0;
    this.last = performance.now();
    this.lineC = new Color();
    this.baseC = new Color();
    this._update = this._update.bind(this);
    this.raf = requestAnimationFrame(this._update);
  }

  _resize() {
    // Fractional size + explicit centre keep the SDF pinned to the exact CSS
    // border rather than drifting a pixel from offsetWidth rounding.
    const rect = this.btn.getBoundingClientRect();
    const w = rect.width, h = rect.height;
    this.size.w = w; this.size.h = h;
    this.renderer.setSize(w + PAD * 2, h + PAD * 2);
    this.program.uniforms.uCenter.value = [(PAD + w / 2) * this.dpr, (PAD + h / 2) * this.dpr];
    this.program.uniforms.uHalfSize.value = [(w / 2) * this.dpr, (h / 2) * this.dpr];
  }

  _update(now) {
    if (this.destroyed) return;
    this.raf = requestAnimationFrame(this._update);
    const dt = Math.min((now - this.last) / 1000, 0.05);
    this.last = now;
    const p = this.p;

    this.idleAngle += p.speed * dt;
    const steer = p.followMouse && this.pointerAngle != null && (!p.autoAnimate || this.proximityT > 0);
    const target = steer ? this.pointerAngle : this.idleAngle;
    const diff = ((target - this.angle + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
    this.angle += diff * (1 - Math.exp(-dt * 7));

    const brightTarget = p.autoAnimate ? 1 : this.proximityT;
    this.bright += (brightTarget - this.bright) * (1 - Math.exp(-dt * 8));

    this.lineC.set(p.lineColor);
    this.baseC.set(p.baseColor);
    const u = this.program.uniforms;
    u.uAngle.value = this.angle;
    u.uRadius.value = Math.min(p.radius, Math.min(this.size.w, this.size.h) / 2) * this.dpr;
    u.uLineColor.value = [this.lineC.r, this.lineC.g, this.lineC.b];
    u.uBaseColor.value = [this.baseC.r, this.baseC.g, this.baseC.b];
    u.uIntensity.value = p.intensity * this.bright;
    u.uShineSize.value = (p.shineSize * Math.PI) / 180;
    u.uShineFade.value = (p.shineFade * Math.PI) / 180;
    u.uThickness.value = p.thickness * this.dpr;
    this.renderer.render({ scene: this.mesh });
  }

  setOptions(patch = {}) { Object.assign(this.p, patch); }

  destroy() {
    this.destroyed = true;
    if (this.raf) cancelAnimationFrame(this.raf);
    if (this.ro) this.ro.disconnect();
    if (this._onPointerMove) window.removeEventListener('pointermove', this._onPointerMove);
    if (this.fx) this.fx.remove();
    this.btn.classList.remove('specular-button');
  }
}

window.SpecularButton = SpecularButton;
export default SpecularButton;
