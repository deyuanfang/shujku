import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Stepper, { Step } from '../components/common/Stepper';
import { Sparkles, Wrench, CheckCircle, ArrowRight, Upload, Cpu, Loader2, Smartphone } from 'lucide-react';
import api from '../services/api';
import { showToast } from '../components/common/Toast';

export default function SetupWizardPage() {
  const navigate = useNavigate();
  const [tools, setTools] = useState<any[]>([]);
  const [checking, setChecking] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [aiProvider, setAiProvider] = useState('anthropic');
  const [apiKey, setApiKey] = useState('');
  const [testResult, setTestResult] = useState('');

  useEffect(() => { checkTools(); }, []);

  async function checkTools() {
    setChecking(true);
    try {
      const { data } = await api.get('/system/setup/check');
      setTools(data.tools || []);
    } catch { setTools([]); }
    setChecking(false);
  }

  async function installMissing() {
    setInstalling(true);
    try {
      await api.post('/system/setup/install');
      await checkTools();
      showToast('success', '安装完成');
    } catch (err: any) {
      showToast('error', '安装失败', err.message);
    }
    setInstalling(false);
  }

  async function testAI() {
    setTestResult('testing');
    try {
      await api.post('/organize/configure', null, { params: { provider: aiProvider, api_key: apiKey } });
      setTestResult('ok');
    } catch { setTestResult('fail'); }
  }

  const missingCount = tools.filter(t => !t.installed).length;
  const pythonMissing = tools.filter(t => !t.installed && t.category === 'python');

  return (
    <div className="max-w-xl mx-auto pt-8 animate-fade-in">
      <Stepper
        initialStep={1}
        onFinalStepCompleted={() => { navigate('/'); showToast('success', '设置完成！开始使用 PersonalKB'); }}
        backButtonText="上一步"
        nextButtonText="下一步"
      >
        {/* Step 1: Welcome */}
        <Step>
          <div className="text-center py-4">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <Sparkles size={28} className="text-white" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">欢迎使用 PersonalKB</h2>
            <p className="text-gray-400 text-sm leading-relaxed">
              个人知识库管理系统 — 自动分析、分类、总结你的所有知识。
              接下来只需几步简单设置即可开始使用。
            </p>
            <div className="grid grid-cols-3 gap-3 mt-6 text-center">
              {[
                { icon: Upload, label: '多格式导入', desc: '文本/PDF/图片/视频' },
                { icon: Cpu, label: 'AI 整理', desc: '自动分类+摘要' },
                { icon: Smartphone, label: '手机同步', desc: '扫码即传' },
              ].map((f) => (
                <div key={f.label} className="bg-gray-800/30 rounded-xl p-3">
                  <f.icon size={20} className="mx-auto mb-1 text-primary-400" />
                  <p className="text-xs font-medium text-gray-300">{f.label}</p>
                  <p className="text-[10px] text-gray-600">{f.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </Step>

        {/* Step 2: Tool Check */}
        <Step>
          <div className="py-2">
            <div className="flex items-center gap-3 mb-4">
              <Wrench size={22} className="text-amber-400" />
              <div><h2 className="text-lg font-semibold text-white">环境检查</h2>
              <p className="text-xs text-gray-500">检测所需工具是否安装</p></div>
            </div>

            {checking ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={24} className="animate-spin text-primary-400" />
              </div>
            ) : (
              <>
                <div className="space-y-1.5 mb-4 max-h-48 overflow-y-auto">
                  {tools.map((t) => (
                    <div key={t.name} className="flex items-center justify-between px-3 py-2 rounded-lg bg-gray-800/30 text-sm">
                      <span className="text-gray-300">{t.name}</span>
                      <span className={`text-xs ${t.installed ? 'text-emerald-400' : 'text-red-400'}`}>
                        {t.installed ? <CheckCircle size={14} /> : '未安装'}
                      </span>
                    </div>
                  ))}
                </div>

                {missingCount > 0 && (
                  <div className="p-3 rounded-xl bg-amber-600/10 border border-amber-600/20 mb-3">
                    <p className="text-sm text-amber-400">{missingCount} 个工具未安装</p>
                    {pythonMissing.length > 0 && (
                      <button onClick={installMissing} disabled={installing}
                        className="btn-primary text-sm py-2 mt-2 w-full flex items-center justify-center gap-2">
                        {installing ? <Loader2 size={14} className="animate-spin"/> : <Wrench size={14}/>}
                        自动安装 Python 工具
                      </button>
                    )}
                  </div>
                )}

                {missingCount === 0 && (
                  <div className="p-4 rounded-xl bg-emerald-600/10 border border-emerald-600/20 text-center">
                    <CheckCircle size={24} className="mx-auto mb-2 text-emerald-400" />
                    <p className="text-sm text-emerald-400">所有工具已就绪</p>
                  </div>
                )}
              </>
            )}
          </div>
        </Step>

        {/* Step 3: AI Config */}
        <Step>
          <div className="py-2">
            <div className="flex items-center gap-3 mb-4">
              <Cpu size={22} className="text-violet-400" />
              <div><h2 className="text-lg font-semibold text-white">AI 模型配置</h2>
              <p className="text-xs text-gray-500">选择 AI 提供商（可跳过，后续在设置中配置）</p></div>
            </div>

            <div className="grid grid-cols-2 gap-2 mb-4">
              {[
                { key: 'anthropic', label: 'Anthropic Claude' },
                { key: 'openai', label: 'OpenAI GPT' },
                { key: 'deepseek', label: 'DeepSeek' },
                { key: 'ollama', label: 'Ollama 本地' },
              ].map((p) => (
                <button key={p.key} onClick={() => setAiProvider(p.key)}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    aiProvider === p.key ? 'border-primary-500 bg-primary-600/10' : 'border-gray-700/50 bg-gray-800/20'
                  }`}>
                  <p className="text-sm font-medium text-gray-200">{p.label}</p>
                </button>
              ))}
            </div>

            {aiProvider !== 'ollama' && (
              <input type="password" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                placeholder="输入 API Key (可选，稍后可配置)" className="input-field mb-3" />
            )}

            <button onClick={testAI} disabled={!apiKey || testResult === 'testing'}
              className="btn-secondary text-sm py-2 w-full flex items-center justify-center gap-2">
              {testResult === 'testing' ? <Loader2 size={14} className="animate-spin"/> :
               testResult === 'ok' ? <><CheckCircle size={14} className="text-emerald-400"/> 连接成功</> :
               testResult === 'fail' ? '连接失败，点击重试' : '测试连接'}
            </button>
          </div>
        </Step>

        {/* Step 4: Done */}
        <Step>
          <div className="text-center py-6">
            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
              <CheckCircle size={36} className="text-white" />
            </div>
            <h2 className="text-xl font-bold text-white mb-2">一切就绪！</h2>
            <p className="text-gray-400 text-sm leading-relaxed">
              你的 PersonalKB 已配置完成。上传第一篇文档、扫描手机二维码导入笔记，或直接搜索知识库。
            </p>
            <button onClick={() => { navigate('/'); showToast('success', '开始使用 PersonalKB！'); }}
              className="btn-primary mt-6 px-8 py-2.5 flex items-center gap-2 mx-auto">
              进入知识库 <ArrowRight size={16} />
            </button>
          </div>
        </Step>
      </Stepper>
    </div>
  );
}
