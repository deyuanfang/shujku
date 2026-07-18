import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trees, GitGraph, Maximize2, Minimize2, RotateCcw, Brain } from 'lucide-react';
import TreeView from '../components/visualization/TreeView';
import GalaxyView from '../components/visualization/GalaxyView';
import { fetchTreeData, fetchGalaxyData } from '../services/api';
import api from '../services/api';
import type { TreeNode, GalaxyNode, GalaxyEdge } from '../types';

type ViewMode = 'tree' | 'galaxy' | 'knowledge';

export default function KnowledgeGraphPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('tree');
  const [isLoading, setIsLoading] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [treeData, setTreeData] = useState<TreeNode | null>(null);
  const [galaxyNodes, setGalaxyNodes] = useState<GalaxyNode[]>([]);
  const [galaxyEdges, setGalaxyEdges] = useState<GalaxyEdge[]>([]);
  const navigate = useNavigate();

  useEffect(() => { loadData(); }, [viewMode]);

  async function loadData() {
    setIsLoading(true);
    try {
      if (viewMode === 'tree') {
        const data = await fetchTreeData(); setTreeData(data.tree);
      } else if (viewMode === 'knowledge') {
        const { data } = await api.get('/visualization/knowledge-tree');
        setTreeData(data.tree);
      } else {
        const data = await fetchGalaxyData();
        setGalaxyNodes(data.galaxy.nodes); setGalaxyEdges(data.galaxy.edges);
      }
    } catch (err) { console.error(err); }
    setIsLoading(false);
  }

  const handleNodeClick = (node: any) => {
    if (node.type === 'document' && node.id && node.id !== 'root') navigate(`/documents/${node.id}`);
  };

  const modes = [
    { key: 'tree' as ViewMode, icon: Trees, label: '分类树' },
    { key: 'knowledge' as ViewMode, icon: Brain, label: '知识树' },
    { key: 'galaxy' as ViewMode, icon: GitGraph, label: '星空' },
  ];

  return (
    <div className={isFullscreen ? 'fixed inset-0 z-50 bg-gray-950 p-6 space-y-4' : 'space-y-4 h-[calc(100vh-6rem)]'}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-white">知识图谱</h1>
          <div className="flex bg-gray-800/50 rounded-lg p-0.5">
            {modes.map(m => (
              <button key={m.key} onClick={() => setViewMode(m.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-all ${
                  viewMode === m.key ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-gray-300'}`}>
                <m.icon size={15} /> {m.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={loadData} className="btn-ghost p-2"><RotateCcw size={16} /></button>
          <button onClick={() => setIsFullscreen(!isFullscreen)} className="btn-ghost p-2">
            {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </div>

      <div className="flex-1 relative" style={{ height: isFullscreen ? 'calc(100vh - 120px)' : 'calc(100vh - 15rem)' }}>
        {isLoading ? (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-950/50 z-10 rounded-xl">
            <div className="w-8 h-8 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : viewMode === 'galaxy' ? (
          <GalaxyView nodes={galaxyNodes} edges={galaxyEdges} onNodeClick={(n) => n.type === 'document' && n.refId && navigate(`/documents/${n.refId}`)} />
        ) : (
          <TreeView data={treeData} onNodeClick={handleNodeClick} />
        )}
      </div>
    </div>
  );
}
