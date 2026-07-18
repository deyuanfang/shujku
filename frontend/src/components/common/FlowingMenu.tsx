import { useRef, useEffect, useState } from 'react';
import { gsap } from 'gsap';
import './FlowingMenu.css';

interface MenuItem {
  link: string;
  text: string;
  image?: string;
  icon?: React.ReactNode;
}

interface Props {
  items: MenuItem[];
  speed?: number;
  textColor?: string;
  bgColor?: string;
  marqueeBgColor?: string;
  marqueeTextColor?: string;
  borderColor?: string;
  onItemClick?: (index: number, item: MenuItem) => void;
  activeIndex?: number | null;
}

export default function FlowingMenu({
  items = [], speed = 15, textColor = '#9ca3af',
  bgColor = 'transparent', marqueeBgColor = '#6366f1',
  marqueeTextColor = '#fff', borderColor = 'rgba(255,255,255,0.04)',
  onItemClick, activeIndex,
}: Props) {
  return (
    <div className="menu-wrap" style={{ backgroundColor: bgColor }}>
      <nav className="menu">
        {items.map((item, idx) => (
          <MenuItem
            key={idx}
            {...item}
            speed={speed}
            textColor={activeIndex === idx ? '#818cf8' : textColor}
            marqueeBgColor={marqueeBgColor}
            marqueeTextColor={marqueeTextColor}
            borderColor={borderColor}
            onClick={() => onItemClick?.(idx, item)}
          />
        ))}
      </nav>
    </div>
  );
}

function MenuItem({
  link, text, image, icon, speed, textColor,
  marqueeBgColor, marqueeTextColor, borderColor, onClick,
}: any) {
  const itemRef = useRef<HTMLDivElement>(null);
  const marqueeRef = useRef<HTMLDivElement>(null);
  const marqueeInnerRef = useRef<HTMLDivElement>(null);
  const animationRef = useRef<gsap.core.Tween | null>(null);
  const [repetitions, setRepetitions] = useState(4);

  const animationDefaults = { duration: 0.5, ease: 'expo' };

  const findClosestEdge = (mx: number, my: number, w: number, h: number) => {
    const topDist = (mx - w / 2) ** 2 + (my - 0) ** 2;
    const bottomDist = (mx - w / 2) ** 2 + (my - h) ** 2;
    return topDist < bottomDist ? 'top' : 'bottom';
  };

  useEffect(() => {
    const calc = () => {
      if (!marqueeInnerRef.current) return;
      const part = marqueeInnerRef.current.querySelector('.marquee__part');
      if (!part) return;
      const w = (part as HTMLElement).offsetWidth;
      const vw = window.innerWidth;
      setRepetitions(Math.max(3, Math.ceil(vw / w) + 1));
    };
    calc();
    window.addEventListener('resize', calc);
    return () => window.removeEventListener('resize', calc);
  }, [text, image]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (!marqueeInnerRef.current) return;
      const part = marqueeInnerRef.current.querySelector('.marquee__part');
      if (!part) return;
      const w = (part as HTMLElement).offsetWidth;
      if (!w) return;
      if (animationRef.current) animationRef.current.kill();
      animationRef.current = gsap.to(marqueeInnerRef.current, {
        x: -w, duration: speed, ease: 'none', repeat: -1,
      });
    }, 100);
    return () => { clearTimeout(timer); animationRef.current?.kill(); };
  }, [text, image, repetitions, speed]);

  const handleMouseEnter = (ev: React.MouseEvent) => {
    if (!itemRef.current || !marqueeRef.current || !marqueeInnerRef.current) return;
    const r = itemRef.current.getBoundingClientRect();
    const edge = findClosestEdge(ev.clientX - r.left, ev.clientY - r.top, r.width, r.height);
    gsap.timeline({ defaults: animationDefaults })
      .set(marqueeRef.current, { y: edge === 'top' ? '-101%' : '101%' }, 0)
      .set(marqueeInnerRef.current, { y: edge === 'top' ? '101%' : '-101%' }, 0)
      .to([marqueeRef.current, marqueeInnerRef.current], { y: '0%' }, 0);
  };

  const handleMouseLeave = (ev: React.MouseEvent) => {
    if (!itemRef.current || !marqueeRef.current || !marqueeInnerRef.current) return;
    const r = itemRef.current.getBoundingClientRect();
    const edge = findClosestEdge(ev.clientX - r.left, ev.clientY - r.top, r.width, r.height);
    gsap.timeline({ defaults: animationDefaults })
      .to(marqueeRef.current, { y: edge === 'top' ? '-101%' : '101%' }, 0)
      .to(marqueeInnerRef.current, { y: edge === 'top' ? '101%' : '-101%' }, 0);
  };

  return (
    <div className="menu__item" ref={itemRef} style={{ borderColor }}>
      <a className="menu__item-link" href={link} onClick={(e) => { e.preventDefault(); onClick?.(); }}
        onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave}
        style={{ color: textColor }}>
        {icon && <span className="flex-shrink-0">{icon}</span>}
        {text}
      </a>
      <div className="marquee" ref={marqueeRef} style={{ backgroundColor: marqueeBgColor }}>
        <div className="marquee__inner-wrap">
          <div className="marquee__inner" ref={marqueeInnerRef} aria-hidden="true">
            {[...Array(repetitions)].map((_, idx) => (
              <div className="marquee__part" key={idx} style={{ color: marqueeTextColor }}>
                <span>{text}</span>
                {image && <div className="marquee__img" style={{ backgroundImage: `url(${image})` }} />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
