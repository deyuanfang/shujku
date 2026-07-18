import { useRef, useEffect } from 'react';

interface Props {
  glitchColors?: string[];
  glitchSpeed?: number;
  centerVignette?: boolean;
  outerVignette?: boolean;
  smooth?: boolean;
  characters?: string;
  className?: string;
}

export default function LetterGlitch({
  glitchColors = ['#1e1b4b', '#6366f1', '#818cf8'],
  className = '',
  glitchSpeed = 50,
  centerVignette = true,
  outerVignette = true,
  smooth = true,
  characters = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%&*+-/=<>[]{};:.,',
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationRef = useRef<number | null>(null);
  const letters = useRef<any[]>([]);
  const grid = useRef({ columns: 0, rows: 0 });
  const context = useRef<CanvasRenderingContext2D | null>(null);
  const lastGlitchTime = useRef(Date.now());

  const lettersAndSymbols = Array.from(characters);
  const fontSize = 15;
  const charWidth = 9.5;
  const charHeight = 19;

  const getRandomChar = () => lettersAndSymbols[Math.floor(Math.random() * lettersAndSymbols.length)];
  const getRandomColor = () => glitchColors[Math.floor(Math.random() * glitchColors.length)];

  const hexToRgb = (hex: string) => {
    const h = hex.replace(/^#?([a-f\d])([a-f\d])([a-f\d])$/i, (_, r, g, b) => r + r + g + g + b + b);
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(h);
    return m ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) } : null;
  };

  const interpolateColor = (start: any, end: any, factor: number) =>
    `rgb(${Math.round(start.r + (end.r - start.r) * factor)},${Math.round(start.g + (end.g - start.g) * factor)},${Math.round(start.b + (end.b - start.b) * factor)})`;

  const calculateGrid = (w: number, h: number) => ({ columns: Math.ceil(w / charWidth), rows: Math.ceil(h / charHeight) });

  const initializeLetters = (columns: number, rows: number) => {
    grid.current = { columns, rows };
    letters.current = Array.from({ length: columns * rows }, () => ({
      char: getRandomChar(), color: getRandomColor(),
      targetColor: getRandomColor(), colorProgress: 1,
    }));
  };

  const resizeCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const rect = parent.getBoundingClientRect();
    canvas.width = rect.width * dpr; canvas.height = rect.height * dpr;
    canvas.style.width = `${rect.width}px`; canvas.style.height = `${rect.height}px`;
    if (context.current) context.current.setTransform(dpr, 0, 0, dpr, 0, 0);
    const { columns, rows } = calculateGrid(rect.width, rect.height);
    initializeLetters(columns, rows);
    drawLetters();
  };

  const drawLetters = () => {
    if (!context.current || letters.current.length === 0) return;
    const ctx = context.current;
    const { width, height } = canvasRef.current!.getBoundingClientRect();
    ctx.clearRect(0, 0, width, height);
    ctx.font = `${fontSize}px monospace`;
    ctx.textBaseline = 'top';
    letters.current.forEach((l, i) => {
      const x = (i % grid.current.columns) * charWidth;
      const y = Math.floor(i / grid.current.columns) * charHeight;
      ctx.fillStyle = l.color;
      ctx.fillText(l.char, x, y);
    });
  };

  const updateLetters = () => {
    if (!letters.current.length) return;
    const count = Math.max(1, Math.floor(letters.current.length * 0.05));
    for (let i = 0; i < count; i++) {
      const idx = Math.floor(Math.random() * letters.current.length);
      if (!letters.current[idx]) continue;
      letters.current[idx].char = getRandomChar();
      letters.current[idx].targetColor = getRandomColor();
      letters.current[idx].colorProgress = smooth ? 0 : 1;
      if (!smooth) letters.current[idx].color = letters.current[idx].targetColor;
    }
  };

  const handleSmoothTransitions = () => {
    let needsRedraw = false;
    letters.current.forEach(l => {
      if (l.colorProgress < 1) {
        l.colorProgress += 0.05;
        if (l.colorProgress > 1) l.colorProgress = 1;
        const s = hexToRgb(l.color), e = hexToRgb(l.targetColor);
        if (s && e) { l.color = interpolateColor(s, e, l.colorProgress); needsRedraw = true; }
      }
    });
    if (needsRedraw) drawLetters();
  };

  const animate = () => {
    const now = Date.now();
    if (now - lastGlitchTime.current >= glitchSpeed) {
      updateLetters(); drawLetters(); lastGlitchTime.current = now;
    }
    if (smooth) handleSmoothTransitions();
    animationRef.current = requestAnimationFrame(animate);
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    context.current = canvas.getContext('2d');
    resizeCanvas(); animate();
    let resizeTimer: any;
    const handleResize = () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (animationRef.current) cancelAnimationFrame(animationRef.current);
        resizeCanvas(); animate();
      }, 100);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
      window.removeEventListener('resize', handleResize);
    };
  }, [glitchSpeed, smooth]);

  return (
    <div style={{ position: 'fixed', inset: 0, width: '100vw', height: '100vh', backgroundColor: '#060610', overflow: 'hidden', zIndex: 0 }} className={className}>
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%', opacity: 0.5 }} />
      {outerVignette && <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(circle, rgba(6,6,16,0) 50%, rgba(6,6,16,1) 100%)' }} />}
      {centerVignette && <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(circle, rgba(6,6,16,0.9) 0%, rgba(6,6,16,0) 70%)' }} />}
    </div>
  );
}
