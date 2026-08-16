import React, { useState, useEffect } from 'react';
import { X, Cpu, HardDrive, Download, CheckCircle2, Cloud, Sparkles, RefreshCw, Key, AlertCircle } from 'lucide-react';
import { fetchModelsStatus, triggerModelDownload } from '../api';

export default function ModelManagerModal({ isOpen, onClose }) {
  const [data, setData] = useState(null);
  const [hfToken, setHfToken] = useState('');
  const [downloadingModel, setDownloadingModel] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadStatus();
    }
  }, [isOpen]);

  const loadStatus = async () => {
    setIsLoading(true);
    try {
      const res = await fetchModelsStatus();
      setData(res);
    } catch (err) {
      console.error('Failed to load model status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = async (modelName) => {
    setDownloadingModel(modelName);
    setStatusMessage(`Initiated download/verification for ${modelName.toUpperCase()} in background...`);
    setErrorMessage(null);
    try {
      await triggerModelDownload(modelName, hfToken);
      // Poll a few times
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="glass-panel w-full max-w-3xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative max-h-[90vh] overflow-y-auto">
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
              <h2 className="text-lg font-bold text-white">AI Models & Hardware Staging Manager</h2>
              <p className="text-xs text-slate-400">
                RTX 3070 8GB VRAM Budget & Local Weight Management
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
              <p className="text-[11px] text-slate-400">Used for free cloud inference or downloading gated model weights</p>
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
