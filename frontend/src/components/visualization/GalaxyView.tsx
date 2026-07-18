import { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import type { GalaxyNode, GalaxyEdge } from '../../types';

interface Props {
  nodes: GalaxyNode[];
  edges: GalaxyEdge[];
  onNodeClick?: (node: GalaxyNode) => void;
  height?: number;
}

export default function GalaxyView({ nodes, edges, onNodeClick, height = 600 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredNode, setHoveredNode] = useState<GalaxyNode | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth || 800;
    const h = height;

    // Background
    svg.append('rect')
      .attr('width', width)
      .attr('height', h)
      .attr('fill', '#030712');

    // Stars background
    const starsGroup = svg.append('g').attr('class', 'stars');
    for (let i = 0; i < 100; i++) {
      starsGroup.append('circle')
        .attr('cx', Math.random() * width)
        .attr('cy', Math.random() * h)
        .attr('r', Math.random() * 1.8 + 0.2)
        .attr('fill', '#6b7280')
        .attr('opacity', Math.random() * 0.6 + 0.1)
        .attr('class', 'star-particle');
    }

    // Animate stars twinkle
    function twinkleStars() {
      starsGroup.selectAll('.star-particle')
        .transition()
        .duration(2000 + Math.random() * 3000)
        .attr('opacity', () => Math.random() * 0.6 + 0.1)
        .on('end', twinkleStars);
    }
    twinkleStars();

    const mainGroup = svg.append('g');

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        mainGroup.attr('transform', event.transform);
      });

    svg.call(zoom);
    // Initial zoom to fit
    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, h / 2).scale(0.8).translate(-width / 2, -h / 2));

    // Defs for gradients
    const defs = mainGroup.append('defs');

    // Glow filter
    const filter = defs.append('filter').attr('id', 'glow');
    filter.append('feGaussianBlur').attr('stdDeviation', '3').attr('result', 'coloredBlur');
    const feMerge = filter.append('feMerge');
    feMerge.append('feMergeNode').attr('in', 'coloredBlur');
    feMerge.append('feMergeNode').attr('in', 'SourceGraphic');

    // Star glow gradient
    ['#6366f1', '#ec4899', '#f59e0b', '#10b981', '#3b82f6'].forEach((color, i) => {
      const grad = defs.append('radialGradient').attr('id', `star-glow-${i}`);
      grad.append('stop').attr('offset', '0%').attr('stop-color', color).attr('stop-opacity', 0.5);
      grad.append('stop').attr('offset', '100%').attr('stop-color', color).attr('stop-opacity', 0);
    });

    // Force simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(edges as any)
        .id((d: any) => d.id)
        .distance((e: any) => 120 / (e.weight || 0.5))
        .strength(0.3))
      .force('charge', d3.forceManyBody().strength((d: any) => {
        switch (d.type) {
          case 'category': return -800;
          case 'document': return -120;
          case 'entity': return -60;
          default: return -200;
        }
      }))
      .force('center', d3.forceCenter(width / 2, h / 2))
      .force('collision', d3.forceCollide().radius((d: any) => (d.radius || 10) + 8))
      // Cluster force: documents orbit their category star
      .force('cluster', (() => {
        const centers: Record<string, { x: number; y: number }> = {};
        function force(alpha: number) {
          for (const d of nodes as any[]) {
            if (d.type === 'document' && d.clusterId && centers[d.clusterId]) {
              const c = centers[d.clusterId];
              d.x += (c.x - d.x) * alpha * 0.03;
              d.y += (c.y - d.y) * alpha * 0.03;
            }
          }
        }
        force.initialize = (ns: any[]) => {
          // Place categories in a circle
          const cats = ns.filter((d: any) => d.type === 'category');
          const cx = width / 2, cy = h / 2;
          const radius = Math.min(width, h) * 0.3;
          cats.forEach((cat: any, i: number) => {
            const angle = (2 * Math.PI * i) / Math.max(cats.length, 1) - Math.PI / 2;
            cat.fx = cx + Math.cos(angle) * radius;
            cat.fy = cy + Math.sin(angle) * radius;
            centers[cat.clusterId || cat.refId] = { x: cat.fx, y: cat.fy };
          });
        };
        return force;
      })());

    // Draw links
    const link = mainGroup.append('g')
      .selectAll('line')
      .data(edges)
      .enter()
      .append('line')
      .attr('stroke', '#1f2937')
      .attr('stroke-opacity', 0.5)
      .attr('stroke-width', (d: any) => Math.max(0.5, (d.weight || 0.3) * 3))
      .attr('stroke-dasharray', (d: any) => d.type === 'related_to' ? '4,4' : 'none');

    // Draw nodes
    const node = mainGroup.append('g')
      .selectAll('g')
      .data(nodes)
      .enter()
      .append('g')
      .attr('class', 'galaxy-node')
      .style('cursor', 'pointer')
      .on('click', (_e: any, d: any) => onNodeClick?.(d))
      .on('mouseenter', (event: any, d: any) => {
        setHoveredNode(d);
        setTooltipPos({ x: event.pageX, y: event.pageY });
      })
      .on('mouseleave', () => setHoveredNode(null))
      .call(d3.drag<SVGGElement, any>()
        .on('start', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x; d.fy = d.y;
        })
        .on('drag', (event: any, d: any) => { d.fx = event.x; d.fy = event.y; })
        .on('end', (event: any, d: any) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null; d.fy = null;
        }) as any);

    // Glow for categories
    node.filter((d: any) => d.type === 'category')
      .append('circle')
      .attr('r', (d: any) => (d.radius || 30) * 2.5)
      .attr('fill', (d: any, i: number) => `url(#star-glow-${i % 5})`);

    // Main circle
    node.append('circle')
      .attr('r', (d: any) => d.radius || 10)
      .attr('fill', (d: any) => d.color || '#6366f1')
      .attr('stroke', (d: any) => {
        const c = d.color || '#6366f1';
        return c;
      })
      .attr('stroke-width', (d: any) => d.type === 'category' ? 3 : 1.5)
      .attr('filter', (d: any) => d.type === 'category' ? 'url(#glow)' : '')
      .attr('opacity', 0.9);

    // Orbit ring for categories
    node.filter((d: any) => d.type === 'category')
      .append('circle')
      .attr('r', (d: any) => (d.radius || 30) * 2)
      .attr('fill', 'none')
      .attr('stroke', (d: any) => d.color || '#6366f1')
      .attr('stroke-width', 0.5)
      .attr('stroke-opacity', 0.2)
      .attr('stroke-dasharray', '3,3');

    // Labels
    node.append('text')
      .attr('dy', (d: any) => (d.radius || 10) + 14)
      .attr('text-anchor', 'middle')
      .text((d: any) => {
        const label = d.label || '';
        return label.length > 12 ? label.slice(0, 11) + '…' : label;
      })
      .attr('fill', (d: any) => d.type === 'category' ? '#e5e7eb' : '#9ca3af')
      .attr('font-size', (d: any) => d.type === 'category' ? '13px' : '11px')
      .attr('font-weight', (d: any) => d.type === 'category' ? '600' : '400')
      .attr('font-family', 'Inter, Noto Sans SC, sans-serif')
      .style('pointer-events', 'none');

    // Tooltips
    node.append('title').text((d: any) => {
      const parts = [d.label];
      if (d.type === 'category') parts.push(`${d.radius > 30 ? '主要分类' : '子分类'}`);
      if (d.type === 'entity') parts.push(`类型: ${d.entityType || '未知'}`);
      if (d.importance) parts.push(`重要度: ${(d.importance * 100).toFixed(0)}%`);
      return parts.join('\n');
    });

    // Simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y);
      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`);
    });

    // Cool down and stop
    // Keep simulation alive with gentle reheating for continuous orbit animation
    simulation.alpha(0.8).restart();
    const reheatInterval = setInterval(() => {
      if (simulation.alpha() < 0.02) {
        simulation.alpha(0.05).restart();
      }
    }, 3000);

    return () => {
      simulation.stop();
      clearInterval(reheatInterval);
    };
  }, [nodes, edges, height]);

  return (
    <div className="galaxy-bg rounded-xl border border-gray-800/50 overflow-hidden relative" style={{ height }}>
      <svg ref={svgRef} className="w-full h-full" />

      {/* Tooltip */}
      {hoveredNode && (
        <div
          className="absolute z-20 glass-panel px-3 py-2 text-xs pointer-events-none"
          style={{
            left: Math.min(tooltipPos.x + 12, window.innerWidth - 200),
            top: Math.min(tooltipPos.y - 10, window.innerHeight - 100),
          }}
        >
          <p className="font-medium text-gray-200">{hoveredNode.label}</p>
          <p className="text-gray-500 mt-0.5">
            {hoveredNode.type === 'category' ? '📁 分类' :
             hoveredNode.type === 'entity' ? `🏷 ${hoveredNode.entityType || '实体'}` :
             '📄 文档'}
            {hoveredNode.importance > 0 && ` · 重要度 ${(hoveredNode.importance * 100).toFixed(0)}%`}
          </p>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 right-3 flex items-center gap-3 text-[10px] text-gray-600 bg-gray-950/80 px-3 py-1.5 rounded-lg">
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-primary-500"/>分类</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-gray-400"/>文档</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400"/>实体</span>
      </div>
    </div>
  );
}
