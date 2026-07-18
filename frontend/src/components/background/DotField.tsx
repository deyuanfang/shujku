import { useEffect, useRef, memo } from 'react';
import './DotField.css';

const TWO_PI = Math.PI * 2;

const DotField = memo(({
  dotRadius = 1.0, dotSpacing = 30, cursorRadius = 350, bulgeStrength = 40,
  glowRadius = 100, sparkle = false, waveAmplitude = 0.3,
  gradientFrom = 'rgba(99, 102, 241, 0.12)', gradientTo = 'rgba(139, 92, 246, 0.06)',
  glowColor = '#0f0f23', ...rest
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glowRef = useRef<SVGCircleElement>(null);
  const dotsRef = useRef<any[]>([]);
  const mouseRef = useRef({ x: -9999, y: -9999, prevX: -9999, prevY: -9999, speed: 0 });
  const rafRef = useRef<number | null>(null);
  const sizeRef = useRef({ w: 0, h: 0, offsetX: 0, offsetY: 0 });
  const glowOpacity = useRef(0);
  const engagement = useRef(0);
  const propsRef = useRef<any>({});
  propsRef.current = { dotRadius, dotSpacing, cursorRadius, bulgeStrength, sparkle, waveAmplitude, gradientFrom, gradientTo };
  const glowIdRef = useRef(`df-${Math.random().toString(36).slice(2, 7)}`);
  const frameCount = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const glowEl = glowRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let resizeTimer: any;
    let speedTimer: any;
    let disposed = false;

    function resize() { clearTimeout(resizeTimer); resizeTimer = setTimeout(doResize, 150); }

    function doResize() {
      if (disposed || !canvas) return;
      const parent = canvas.parentElement;
      if (!parent) return;
      const rect = parent.getBoundingClientRect();
      const w = rect.width || window.innerWidth;
      const h = rect.height || window.innerHeight;
      if (w < 10 || h < 10) return;
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      sizeRef.current = { w, h, offsetX: rect.left + window.scrollX, offsetY: rect.top + window.scrollY };
      buildDots(w, h);
    }

    function buildDots(w: number, h: number) {
      const p = propsRef.current;
      const step = p.dotRadius + p.dotSpacing;
      const cols = Math.floor(w / step) || 1;
      const rows = Math.floor(h / step) || 1;
      const padX = (w % step) / 2;
      const padY = (h % step) / 2;
      const dots = new Array(rows * cols);
      let idx = 0;
      for (let row = 0; row < rows; row++) {
        for (let col = 0; col < cols; col++) {
          const ax = padX + col * step + step / 2;
          const ay = padY + row * step + step / 2;
          dots[idx++] = { ax, ay, sx: ax, sy: ay, x: ax, y: ay };
        }
      }
      dotsRef.current = dots;
    }

    function onMouseMove(e: MouseEvent) {
      const s = sizeRef.current;
      mouseRef.current.x = e.pageX - s.offsetX;
      mouseRef.current.y = e.pageY - s.offsetY;
    }

    function onVisibility() {
      if (document.hidden) {
        if (rafRef.current) { cancelAnimationFrame(rafRef.current); rafRef.current = null; }
      } else if (!rafRef.current && !disposed) {
        rafRef.current = requestAnimationFrame(tick);
      }
    }

    function tick() {
      if (disposed) return;
      frameCount.current++;
      const dots = dotsRef.current;
      const m = mouseRef.current;
      const { w, h } = sizeRef.current;
      if (w === 0 || h === 0) { rafRef.current = requestAnimationFrame(tick); return; }
      const p = propsRef.current;
      const len = dots.length;
      const t = frameCount.current * 0.02;

      // Engagement
      const dx = m.prevX - m.x, dy = m.prevY - m.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      m.speed += (dist - m.speed) * 0.5;
      if (m.speed < 0.001) m.speed = 0;
      m.prevX = m.x; m.prevY = m.y;
      const te = Math.min(m.speed / 5, 1);
      engagement.current += (te - engagement.current) * 0.06;
      if (engagement.current < 0.001) engagement.current = 0;
      const eng = engagement.current;

      glowOpacity.current += (eng - glowOpacity.current) * 0.08;
      if (glowEl) { glowEl.setAttribute('cx', String(m.x)); glowEl.setAttribute('cy', String(m.y)); glowEl.style.opacity = String(glowOpacity.current); }

      ctx.clearRect(0, 0, w, h);
      const grad = ctx.createLinearGradient(0, 0, w, h);
      grad.addColorStop(0, p.gradientFrom); grad.addColorStop(1, p.gradientTo);
      ctx.fillStyle = grad;
      const cr = p.cursorRadius, crSq = cr * cr, rad = p.dotRadius / 2;

      ctx.beginPath();
      for (let i = 0; i < len; i++) {
        const d = dots[i];
        const ddx = m.x - d.ax, ddy = m.y - d.ay;
        const distSq = ddx * ddx + ddy * ddy;

        if (distSq < crSq && eng > 0.01) {
          const dist = Math.sqrt(distSq);
          const tf = 1 - dist / cr;
          const push = tf * tf * p.bulgeStrength * eng;
          const angle = Math.atan2(ddy, ddx);
          d.sx += (d.ax - Math.cos(angle) * push - d.sx) * 0.15;
          d.sy += (d.ay - Math.sin(angle) * push - d.sy) * 0.15;
        } else {
          d.sx += (d.ax - d.sx) * 0.08;
          d.sy += (d.ay - d.sy) * 0.08;
        }

        let drawX = d.sx, drawY = d.sy;
        if (p.waveAmplitude > 0) {
          drawY += Math.sin(d.ax * 0.02 + t) * p.waveAmplitude;
        }
        ctx.moveTo(drawX + rad, drawY);
        ctx.arc(drawX, drawY, rad, 0, TWO_PI);
      }
      ctx.fill();
      rafRef.current = requestAnimationFrame(tick);
    }

    doResize();
    window.addEventListener('resize', resize);
    window.addEventListener('mousemove', onMouseMove, { passive: true });
    document.addEventListener('visibilitychange', onVisibility);
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      disposed = true;
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      clearTimeout(resizeTimer); clearInterval(speedTimer);
      window.removeEventListener('resize', resize);
      window.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, []);

  return (
    <div className="dot-field-container" {...rest}>
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
        <defs>
          <radialGradient id={glowIdRef.current}>
            <stop offset="0%" stopColor={glowColor} /><stop offset="100%" stopColor="transparent" />
          </radialGradient>
        </defs>
        <circle ref={glowRef} cx="-9999" cy="-9999" r={glowRadius} fill={`url(#${glowIdRef.current})`} style={{ opacity: 0 }} />
      </svg>
    </div>
  );
});

DotField.displayName = 'DotField';
export default DotField;
