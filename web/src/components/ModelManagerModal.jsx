import React, { useState, useEffect } from 'react';
import { X, Cpu, HardDrive, Download, CheckCircle2, Cloud, Sparkles, RefreshCw, Key, AlertCircle, Shield, Zap, ToggleLeft, ToggleRight } from 'lucide-react';
import { fetchModelsStatus, triggerModelDownload, fetchSystemSettings, updateSystemSettings } from '../api';

export default function ModelManagerModal({ isOpen, onClose }) {
  const [data, setData] = useState(null);
  const [settingsData, setSettingsData] = useState(null);
  const [geminiApiKey, setGeminiApiKey] = useState('');
  const [onlyLocalAi, setOnlyLocalAi] = useState(false);
  const [hfToken, setHfToken] = useState('');
  const [downloadingModel, setDownloadingModel] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSavingKey, setIsSavingKey] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadStatus();
    }
  }, [isOpen]);

  const loadStatus = async () => {
    setIsLoading(true);
    try {
      const [modelRes, settingsRes] = await Promise.all([
        fetchModelsStatus(),
        fetchSystemSettings().catch(() => null)
      ]);
      setData(modelRes);
      if (settingsRes) {
        setSettingsData(settingsRes);
        setOnlyLocalAi(settingsRes.only_local_ai);
      }
    } catch (err) {
      console.error('Failed to load model/settings status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveGeminiKey = async () => {
    if (!geminiApiKey.trim()) return;
    setIsSavingKey(true);
    try {
      const updated = await updateSystemSettings({ gemini_api_key: geminiApiKey.trim() });
      setSettingsData(updated);
      setGeminiApiKey('');
      setStatusMessage('Google AI Studio API key securely saved to local .env file.');
      setTimeout(() => setStatusMessage(null), 4000);
    } catch (err) {
      setErrorMessage(`Failed to save API key: ${err.message}`);
    } finally {
      setIsSavingKey(false);
    }
  };

  const handleToggleLocalMode = async () => {
    const newVal = !onlyLocalAi;
    setOnlyLocalAi(newVal);
    try {
      const updated = await updateSystemSettings({ only_local_ai: newVal });
      setSettingsData(updated);
      setStatusMessage(newVal ? 'Master Switch: Local AI Only Mode Active.' : 'Master Switch: Cloud Free-Tier Waterfalls Active.');
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err) {
      setErrorMessage(`Failed to toggle local mode: ${err.message}`);
    }
  };

  const handleDownload = async (modelName) => {
    setDownloadingModel(modelName);
    setStatusMessage(`Initiated download/verification for ${modelName.toUpperCase()} in background...`);
    setErrorMessage(null);
    try {
      await triggerModelDownload(modelName, hfToken);
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts += 1;
        await loadStatus();
        if (attempts >= 5) {
          clearInterval(interval);
          setDownloadingModel(null);
          setStatusMessage(`Completed verification for ${modelName.toUpperCase()}.`);
          setTimeout(() => setStatusMessage(null), 4000);
        }
      }, 2000);
    } catch (err) {
      setErrorMessage(`Download error: ${err.message}`);
      setDownloadingModel(null);
    }
  };

  if (!isOpen) return null;

  const models = data?.models ? Object.values(data.models) : [];
  const hardware = data?.hardware || {};
  const quotas = settingsData?.quotas || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="glass-panel w-full max-w-4xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative max-h-[92vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center justify-between mb-4 border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center">
              <Cpu className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">AI Engine & Model Priority Manager</h2>
              <p className="text-xs text-slate-400">
                Hybrid Cloud Free-Tier Dispatcher, Local RTX 3070 VLM, & Quota Tracking
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleDownload('all')}
              disabled={!!downloadingModel}
              className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-1.5 rounded-lg text-xs transition"
            >
              <Download className="w-3.5 h-3.5" />
              Download All
            </button>
            <button
              onClick={loadStatus}
              disabled={isLoading}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-white bg-slate-800 px-2.5 py-1.5 rounded-lg border border-slate-700 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Status / Error alerts */}
        {statusMessage && (
          <div className="mb-4 bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs px-3.5 py-2.5 rounded-xl flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
            <span>{statusMessage}</span>
          </div>
        )}

        {errorMessage && (
          <div className="mb-4 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs px-3.5 py-2.5 rounded-xl flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {/* Master Switch: Only Use Local AI */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 mb-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${onlyLocalAi ? 'bg-amber-500/20 text-amber-400' : 'bg-teal-500/20 text-teal-400'}`}>
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-white">Master Local Mode Switch</h3>
                <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded font-bold ${
                  onlyLocalAi ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-teal-500/20 text-teal-300 border border-teal-500/40'
                }`}>
                  {onlyLocalAi ? '100% Offline Local AI' : 'Hybrid Cloud-Local Active'}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                {onlyLocalAi
                  ? 'All vision indexing, aesthetic scoring, and text structuring run exclusively on your local GPU (Qwen + SigLIP 2).'
                  : 'Utilizes Google AI Studio free tier quotas (Gemini Flash Lite & Gemma) with automatic local fallback.'}
              </p>
            </div>
          </div>

          <button
            onClick={handleToggleLocalMode}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition border ${
              onlyLocalAi
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 hover:bg-amber-500/30'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            {onlyLocalAi ? <ToggleRight className="w-4 h-4 text-amber-400" /> : <ToggleLeft className="w-4 h-4 text-slate-400" />}
            {onlyLocalAi ? 'Local Only Active' : 'Enable Local Only'}
          </button>
        </div>

        {/* Dedicated Local AI Pipeline Architecture */}
        <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 mb-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-teal-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Dedicated Local AI Pipeline Roles (Zero Bottlenecks)
              </h3>
            </div>
            <span className="text-[10px] font-mono bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded">
              Active VLM: Qwen 2.5 VL (3B)
            </span>
          </div>
          <p className="text-xs text-slate-400 mb-3">
            Hardware-optimized pipeline automatically dispatches models to specialized tasks for maximum throughput on your 8GB GPU:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-xl border bg-slate-900 border-teal-500/30 text-slate-300">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-xs text-teal-300">Qwen 2.5 VL 3B</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 font-mono">Vision</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Ultra-fast 256x256 batched vision captioning (~0.5s/item).
              </p>
            </div>

            <div className="p-3 rounded-xl border bg-slate-900 border-cyan-500/30 text-slate-300">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-xs text-cyan-300">SigLIP 2 (FP16)</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono">Aesthetics</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Pure zero-shot photographic aesthetic scoring & 768-dim embeddings.
              </p>
            </div>

            <div className="p-3 rounded-xl border bg-slate-900 border-purple-500/30 text-slate-300">
              <div className="flex items-center justify-between mb-1">
                <span className="font-bold text-xs text-purple-300">Qwen 3.5 9B</span>
                <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 font-mono">Text / Music</span>
              </div>
              <p className="text-[11px] text-slate-400">
                High-capacity reasoning for diary drafting and music prompts.
              </p>
            </div>
          </div>
        </div>

        {/* Google AI Studio API Key Configuration (Saved to .env) */}
        <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 mb-5">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Key className="w-4 h-4 text-teal-400" />
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                Google AI Studio API Key (Free Tier Waterfalls)
              </h3>
            </div>
            {settingsData?.has_gemini_api_key && (
              <span className="text-[10px] font-mono bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded">
                Active Key: {settingsData.masked_gemini_api_key}
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400 mb-3">
            Enter your free Google AI Studio API key. Saved into your local untracked <code className="text-teal-300">.env</code> file (never pushed to Git).
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={geminiApiKey}
              onChange={(e) => setGeminiApiKey(e.target.value)}
              placeholder={settingsData?.has_gemini_api_key ? "Enter new key to replace..." : "AIzaSy..."}
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
            />
            <button
              onClick={handleSaveGeminiKey}
              disabled={isSavingKey || !geminiApiKey.trim()}
              className="bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-1.5 rounded-lg text-xs transition"
            >
              {isSavingKey ? 'Saving...' : 'Save to .env'}
            </button>
          </div>
        </div>


        {/* Quota Pools Real-Time Dashboard */}
        {Object.keys(quotas).length > 0 && (
          <div className="mb-5">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-cyan-400" />
              Model Priority Quota Tracker & Headroom
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-xs">
              {Object.values(quotas).map((q) => (
                <div key={q.name} className="bg-slate-950 p-2.5 rounded-lg border border-slate-800/80 font-mono">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-bold text-white text-[11px] truncate">{q.name}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded ${
                      q.is_local ? 'bg-purple-500/20 text-purple-300' : 'bg-cyan-500/20 text-cyan-300'
                    }`}>
                      {q.is_local ? 'Local' : 'Cloud'}
                    </span>
                  </div>
                  <div className="text-[10px] text-slate-400 space-y-0.5">
                    <div>RPM: <span className="text-teal-300 font-bold">{q.current_rpm}</span> / {q.rpm_limit}</div>
                    <div>Daily Calls: <span className="text-teal-300 font-bold">{q.daily_count}</span> / {q.rpd_limit}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Hardware Status Banner */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5 text-xs font-mono">
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
            <span className="text-slate-400 block text-[10px]">EXECUTION HARDWARE</span>
            <strong className="text-teal-400">{hardware.device || 'CUDA (RTX 3070)'}</strong>
          </div>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
            <span className="text-slate-400 block text-[10px]">VRAM ALLOCATED</span>
            <strong className="text-cyan-400">{hardware.vram_stats?.allocated_gb || '0.00'} GB</strong>
          </div>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800">
            <span className="text-slate-400 block text-[10px]">VRAM RESERVED</span>
            <strong className="text-purple-400">{hardware.vram_stats?.reserved_gb || '0.00'} GB</strong>
          </div>
        </div>

        {/* Hugging Face Token Input */}
        <div className="bg-slate-950/80 p-3 rounded-xl border border-slate-800 mb-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Key className="w-4 h-4 text-amber-400 shrink-0" />
            <div>
              <p className="text-xs font-semibold text-white">Hugging Face API Key (Optional)</p>
              <p className="text-[11px] text-slate-400">Used for downloading gated weights</p>
            </div>
          </div>
          <input
            type="password"
            value={hfToken}
            onChange={(e) => setHfToken(e.target.value)}
            placeholder="hf_..."
            className="w-full sm:w-64 bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
          />
        </div>

        {/* Model Cards List */}
        <div className="space-y-3">
          {models.map((m) => (
            <div
              key={m.name}
              className="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-bold text-white uppercase tracking-wide">{m.name}</h3>
                  {m.is_cached ? (
                    <span className="flex items-center gap-1 text-[10px] bg-teal-500/10 text-teal-400 border border-teal-500/30 px-2 py-0.5 rounded-full font-mono font-semibold">
                      <CheckCircle2 className="w-3 h-3" /> Cached Locally
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-[10px] bg-sky-500/10 text-sky-400 border border-sky-500/30 px-2 py-0.5 rounded-full font-mono font-semibold">
                      <Cloud className="w-3 h-3" /> Free API / Fallback Ready
                    </span>
                  )}
                  <span className="text-[10px] font-mono text-cyan-300/90 bg-cyan-950/40 border border-cyan-800/40 px-2 py-0.5 rounded">
                    {m.execution_mode}
                  </span>
                </div>
                <p className="text-xs text-slate-400">{m.description}</p>
                <p className="text-[11px] font-mono text-slate-500">
                  Repo: <span className="text-slate-400">{m.repo_id}</span> • RAM: <span className="text-slate-300">{m.ram_gb} GB</span> • Peak VRAM: <span className="text-slate-300">{m.vram_gb} GB</span>
                </p>
                {m.cached_path && (
                  <p className="text-[10px] font-mono text-teal-400/80 truncate max-w-lg" title={m.cached_path}>
                    📂 Location: {m.cached_path}
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleDownload(m.name)}
                  disabled={downloadingModel === m.name}
                  className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 border border-slate-700 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition"
                >
                  <Download className={`w-3.5 h-3.5 text-teal-400 ${downloadingModel === m.name ? 'animate-bounce' : ''}`} />
                  {downloadingModel === m.name ? 'Pre-fetching...' : m.is_cached ? 'Re-verify' : 'Download Weights'}
                </button>
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end pt-4 mt-4 border-t border-slate-800">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-lg text-xs font-semibold bg-teal-500 hover:bg-teal-400 text-slate-950 transition shadow-lg shadow-teal-500/20"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
