import { useState, useEffect } from 'react';
import { Settings, Key, Database, Palette, Save, CheckCircle, Cpu, Sparkles } from 'lucide-react';
import { showToast } from '../components/common/Toast';
import api from '../services/api';

const PROVIDER_MODELS: Record<string, string[]> = {
  anthropic: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  ollama: ['llama3', 'qwen2', 'mistral'],
};

export default function SettingsPage() {
  const [provider, setProvider] = useState('anthropic');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('claude-sonnet-4-20250514');
  const [ollamaUrl, setOllamaUrl] = useState('http://localhost:11434');
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    api.get('/settings').then(({ data }) => {
      if (data?.llm_api_key) setApiKey(data.llm_api_key);
      if (data?.llm_model) setModel(data.llm_model);
      if (data?.auto_analyze !== undefined) setAutoAnalyze(data.auto_analyze);
      if (data?.llm_provider) setProvider(data.llm_provider);
      if (data?.ollama_url) setOllamaUrl(data.ollama_url);
    }).catch(() => {});
  }, []);

  const handleProviderChange = (p: string) => { setProvider(p); setModel(PROVIDER_MODELS[p]?.[0] || ''); };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/settings', { llm_provider: provider, llm_api_key: apiKey || '', llm_model: model, auto_analyze: autoAnalyze, ollama_url: provider === 'ollama' ? ollamaUrl : '', language: 'zh-CN', theme: 'dark' });
      setSaved(true); showToast('success', '设置已保存'); setTimeout(() => setSaved(false), 2000);
    } catch (err: any) { showToast('error', '保存失败', err.message); }
    setSaving(false);
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      await api.post('/organize/configure', null, { params: { provider, api_key: apiKey, model, base_url: provider === 'ollama' ? ollamaUrl : '' } });
      showToast('success', '连接成功', `${provider}/${model} 可用`);
    } catch (err: any) { showToast('error', '连接失败'); }
    setTesting(false);
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in">
      <h1 className="text-2xl font-bold text-white">系统设置</h1>

      {/* AI Provider */}
      <div className="glass-panel p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-primary-600/20 flex items-center justify-center"><Cpu size={18} className="text-primary-400" /></div>
          <div><h2 className="text-lg font-semibold text-white">AI 模型配置</h2><p className="text-xs text-gray-500">选择 AI 提供商和模型</p></div>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">AI 提供商</label>
            <div className="grid grid-cols-4 gap-2">
              {[{ key: 'anthropic', label: 'Anthropic', sub: 'Claude' }, { key: 'openai', label: 'OpenAI', sub: 'GPT' }, { key: 'deepseek', label: 'DeepSeek', sub: '深度求索' }, { key: 'ollama', label: 'Ollama', sub: '本地模型' }].map((p) => (
                <button key={p.key} onClick={() => handleProviderChange(p.key)} className={`p-3 rounded-xl border text-center transition-all ${provider === p.key ? 'border-primary-500 bg-primary-600/10 text-primary-400' : 'border-gray-700/50 bg-gray-800/30 text-gray-400 hover:border-gray-600'}`}>
                  <div className="text-sm font-medium">{p.label}</div><div className="text-[10px] opacity-60">{p.sub}</div>
                </button>
              ))}
            </div>
          </div>
          {provider !== 'ollama' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">API Key</label>
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder={provider === 'anthropic' ? 'sk-ant-api03-...' : 'sk-...'} className="input-field font-mono text-sm" />
            </div>
          )}
          {provider === 'ollama' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1.5">Ollama 服务地址</label>
              <input type="text" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} className="input-field" />
              <p className="text-xs text-gray-600 mt-1">确保已安装并启动 Ollama，运行: ollama pull llama3</p>
            </div>
          )}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">模型</label>
            <select value={model} onChange={(e) => setModel(e.target.value)} className="input-field">
              {(PROVIDER_MODELS[provider] || ['']).map((m) => (<option key={m} value={m}>{m}</option>))}
            </select>
          </div>
          <button onClick={handleTest} disabled={testing} className="btn-secondary text-sm py-2 w-full flex items-center justify-center gap-2"><Sparkles size={14} /> {testing ? '测试中...' : '测试连接'}</button>
          <div className="flex items-center justify-between py-2">
            <div><p className="text-sm text-gray-300">自动整理</p><p className="text-xs text-gray-500">数据整理大师自动分析并归类新内容</p></div>
            <button onClick={() => setAutoAnalyze(!autoAnalyze)} className={`relative w-11 h-6 rounded-full transition-all ${autoAnalyze ? 'bg-primary-600' : 'bg-gray-700'}`}><span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${autoAnalyze ? 'translate-x-5' : 'translate-x-0'}`} /></button>
          </div>
        </div>
      </div>

      {/* Storage */}
      <div className="glass-panel p-6">
        <div className="flex items-center gap-3 mb-4"><div className="w-8 h-8 rounded-lg bg-emerald-600/20 flex items-center justify-center"><Database size={18} className="text-emerald-400" /></div><div><h2 className="text-lg font-semibold text-white">存储设置</h2></div></div>
        <input type="text" value="./data (SQLite)" disabled className="input-field opacity-60 cursor-not-allowed" />
      </div>

      {/* Save */}
      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving} className="btn-primary flex items-center gap-2 px-6">
          {saved ? <CheckCircle size={16} /> : <Save size={16} />}
          {saved ? '已保存' : saving ? '保存中...' : '保存设置'}
        </button>
      </div>
    </div>
  );
}
