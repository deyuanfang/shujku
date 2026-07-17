import { useState, useEffect } from 'react';
import { Settings, Key, Database, Palette, Save, CheckCircle } from 'lucide-react';
import { showToast } from '../components/common/Toast';
import api from '../services/api';

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('claude-sonnet-4-20250514');
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    // Load current settings from backend
    api.get('/settings').then(({ data }) => {
      if (data?.llm_api_key) setApiKey(data.llm_api_key);
      if (data?.llm_model) setModel(data.llm_model);
      if (data?.auto_analyze !== undefined) setAutoAnalyze(data.auto_analyze);
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/settings', {
        llm_api_key: apiKey || '',
        llm_model: model,
        auto_analyze: autoAnalyze,
        language: 'zh-CN',
        theme: 'dark',
      });
      setSaved(true);
      showToast('success', '设置已保存', '所有设置已成功保存到本地');
      setTimeout(() => setSaved(false), 2000);
    } catch (err: any) {
      showToast('error', '保存失败', err.message || '请检查后端服务是否运行');
    }
    setSaving(false);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <h1 className="text-2xl font-bold text-white">系统设置</h1>

      {/* LLM Configuration */}
      <div className="glass-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-primary-600/20 flex items-center justify-center">
            <Key size={18} className="text-primary-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">AI 分析设置</h2>
            <p className="text-xs text-gray-500">配置 Claude API 以启用智能分析</p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Claude API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-ant-api03-..."
              className="input-field font-mono text-sm"
            />
            <p className="text-xs text-gray-600 mt-1">
              用于 AI 摘要、实体提取和深度分析。API Key 仅保存在本地数据库中。
            </p>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1.5">默认模型</label>
            <select value={model} onChange={(e) => setModel(e.target.value)} className="input-field">
              <option value="claude-sonnet-4-20250514">Claude Sonnet 4 (推荐)</option>
              <option value="claude-opus-4-20250514">Claude Opus 4 (深度分析)</option>
              <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5 (快速经济)</option>
            </select>
          </div>

          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm text-gray-300">自动分析</p>
              <p className="text-xs text-gray-500">上传内容后自动调用 AI 进行分析</p>
            </div>
            <button
              onClick={() => setAutoAnalyze(!autoAnalyze)}
              className={`relative w-11 h-6 rounded-full transition-all ${
                autoAnalyze ? 'bg-primary-600' : 'bg-gray-700'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                autoAnalyze ? 'translate-x-5' : 'translate-x-0'
              }`} />
            </button>
          </div>
        </div>
      </div>

      {/* Storage */}
      <div className="glass-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-emerald-600/20 flex items-center justify-center">
            <Database size={18} className="text-emerald-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">存储设置</h2>
            <p className="text-xs text-gray-500">数据库和文件存储位置</p>
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">数据存储路径</label>
            <input type="text" value="./data" disabled className="input-field opacity-60 cursor-not-allowed" />
            <p className="text-xs text-gray-600 mt-1">所有数据均存储在本地的 SQLite 数据库中</p>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="bg-gray-800/30 rounded-lg p-3">
              <p className="text-lg font-bold text-gray-200">SQLite</p>
              <p className="text-[10px] text-gray-500">数据库引擎</p>
            </div>
            <div className="bg-gray-800/30 rounded-lg p-3">
              <p className="text-lg font-bold text-gray-200">FTS5</p>
              <p className="text-[10px] text-gray-500">全文检索</p>
            </div>
            <div className="bg-gray-800/30 rounded-lg p-3">
              <p className="text-lg font-bold text-gray-200">SHA-256</p>
              <p className="text-[10px] text-gray-500">内容去重</p>
            </div>
          </div>
        </div>
      </div>

      {/* Appearance */}
      <div className="glass-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-pink-600/20 flex items-center justify-center">
            <Palette size={18} className="text-pink-400" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white">界面设置</h2>
            <p className="text-xs text-gray-500">语言和主题偏好</p>
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">语言</label>
            <select defaultValue="zh-CN" className="input-field">
              <option value="zh-CN">简体中文</option>
              <option value="en">English</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">主题</label>
            <select defaultValue="dark" className="input-field">
              <option value="dark">深色模式</option>
              <option value="light">浅色模式</option>
              <option value="system">跟随系统</option>
            </select>
          </div>
        </div>
      </div>

      {/* Save button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-primary flex items-center gap-2 px-6"
        >
          {saved ? <CheckCircle size={16} /> : <Save size={16} />}
          {saved ? '已保存 ✓' : saving ? '保存中...' : '保存所有设置'}
        </button>
      </div>
    </div>
  );
}
