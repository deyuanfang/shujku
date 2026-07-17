import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { TreeNode } from '../../types';

interface Props {
  data: TreeNode | null;
  onNodeClick?: (node: TreeNode) => void;
  height?: number;
}

export default function TreeView({ data, onNodeClick, height = 600 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const width = svgRef.current.clientWidth || 900;
    const h = height;
    const margin = { top: 30, right: 120, bottom: 30, left: 40 };

    const hierarchy = d3.hierarchy(data, (d: any) => d.children);
    const treeLayout = d3.tree<TreeNode>()
      .size([h - margin.top - margin.bottom, width - margin.left - margin.right]);
    const root = treeLayout(hierarchy);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Links with curved paths
    g.selectAll('.tree-link')
      .data(root.links())
      .enter()
      .append('path')
      .attr('class', 'tree-link')
      .attr('fill', 'none')
      .attr('stroke', '#374151')
      .attr('stroke-width', 1.5)
      .attr('d', (d: any) => {
        const sx = d.source.y;
        const sy = d.source.x;
        const tx = d.target.y;
        const ty = d.target.x;
        return `M${sx},${sy}C${(sx + tx) / 2},${sy} ${(sx + tx) / 2},${ty} ${tx},${ty}`;
      });

    // Node groups
    const nodeGroup = g.selectAll('.tree-node')
      .data(root.descendants())
      .enter()
      .append('g')
      .attr('class', 'tree-node')
      .attr('transform', (d: any) => `translate(${d.y},${d.x})`)
      .style('cursor', 'pointer')
      .on('click', (_e: any, d: any) => {
        if (d.data.type === 'document') {
          onNodeClick?.(d.data);
        }
      });

    // Glow circles for categories
    nodeGroup
      .filter((d: any) => d.data.type === 'category')
      .append('circle')
      .attr('r', (d: any) => 12 + (d.data.count || 2) * 1.5)
      .attr('fill', (d: any) => d.data.color || '#6366f1')
      .attr('opacity', 0.15);

    // Main circles
    nodeGroup
      .append('circle')
      .attr('r', (d: any) => {
        if (d.data.type === 'category') return 6 + (d.data.count || 2) * 1;
        return 4.5;
      })
      .attr('fill', (d: any) => d.data.color || '#6366f1')
      .attr('stroke', (d: any) => d.data.color || '#818cf8')
      .attr('stroke-width', (d: any) => d.data.type === 'category' ? 2.5 : 1.5)
      .attr('class', 'tree-circle');

    // Labels
    nodeGroup
      .append('text')
      .attr('dy', (d: any) => (d.children && d.children.length > 0 ? -18 : 16))
      .attr('dx', (d: any) => (d.children && d.children.length > 0 ? 0 : 8))
      .attr('text-anchor', (d: any) => (d.children && d.children.length > 0 ? 'middle' : 'start'))
      .text((d: any) => {
        let label = d.data.label || '';
        if (d.data.type === 'category' && d.data.count) {
          label += ` (${d.data.count})`;
        }
        return label.length > 20 ? label.slice(0, 19) + '…' : label;
      })
      .attr('fill', (d: any) => d.data.type === 'category' ? '#e5e7eb' : '#9ca3af')
      .attr('font-size', (d: any) => d.data.type === 'category' ? '13px' : '11px')
      .attr('font-weight', (d: any) => d.data.type === 'category' ? '600' : '400')
      .attr('font-family', 'Inter, Noto Sans SC, sans-serif')
      .style('pointer-events', 'none');

    // Tooltips
    nodeGroup.append('title').text((d: any) => {
      if (d.data.type === 'category') return `${d.data.label}\n${d.data.count || 0} 篇文档`;
      return `${d.data.label}\n${d.data.content_type || 'unknown'}\n${d.data.word_count || 0} 字`;
    });

    // Add subtle hover animation
    nodeGroup
      .on('mouseenter', function () {
        d3.select(this).select('.tree-circle')
          .transition().duration(200)
          .attr('r', (d: any) => {
            if (d.data.type === 'category') return 8 + (d.data.count || 2) * 1.2;
            return 6;
          })
          .attr('stroke-width', 3);
      })
      .on('mouseleave', function () {
        d3.select(this).select('.tree-circle')
          .transition().duration(200)
          .attr('r', (d: any) => {
            if (d.data.type === 'category') return 6 + (d.data.count || 2) * 1;
            return 4.5;
          })
          .attr('stroke-width', (d: any) => d.data.type === 'category' ? 2.5 : 1.5);
      });

  }, [data, height]);

  return (
    <svg ref={svgRef} className="w-full" style={{ height, minHeight: 400 }} />
  );
}
