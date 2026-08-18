import React from 'react';
import {
  Music,
  Video,
  Plus,
  HardDrive,
  Cpu,
  RefreshCw,
  Power,
  Shield,
  ToggleLeft,
  ToggleRight,
  Key,
  BookOpen,
  Edit2,
  Trash2,
  FolderKanban
} from 'lucide-react';

export default function Header({
  projects,
  currentProject,
  onSelectProject,
  onOpenNewProject,
  onOpenDiary,
  onOpenProjectManager,
  onOpenRenameProject,
  onOpenDeleteProject,
  health,
  systemSettings,
  onToggleLocalAi,
  onRefresh,
  onOpenModelManager,
  onShutdown
}) {
  const vram = health?.vram_stats;
  const isCuda = health?.cuda_available;
  const isLocalOnly = systemSettings?.only_local_ai;
  const hasGeminiKey = systemSettings?.has_gemini_api_key;

  return (
    <header className="glass-panel sticky top-0 z-40 px-6 py-3 border-b border-slate-800/80 flex items-center justify-between">
      {/* Brand & Logo */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-teal-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-teal-500/20">
          <Music className="w-5 h-5 text-slate-950 font-bold" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-white">Balladeer</h1>
            <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/30">
              RTX 3070 AI Engine
            </span>
          </div>
          <p className="text-xs text-slate-400">Beat-Synced Story Montage Engine</p>
        </div>
      </div>

      {/* Project Selector & Actions */}
      <div className="flex items-center gap-2.5 flex-wrap">
        <div className="flex items-center gap-1.5 bg-slate-900/90 border border-slate-800 rounded-lg pl-3 pr-1.5 py-1">
          <label className="text-xs text-slate-400 font-medium shrink-0">Project:</label>
          <select
            value={currentProject?.id || ''}
            onChange={(e) => onSelectProject(e.target.value)}
            className="bg-transparent text-sm font-semibold text-white focus:outline-none cursor-pointer max-w-[180px] truncate"
          >
            {projects.length === 0 ? (
              <option value="">No projects</option>
            ) : (
              projects.map((p) => (
                <option key={p.id} value={p.id} className="bg-slate-900 text-white">
                  {p.title}
                </option>
              ))
            )}
          </select>

          {currentProject && (
            <div className="flex items-center gap-1 pl-1 border-l border-slate-800">
              <button
                onClick={onOpenRenameProject}
                className="p-1 rounded-md hover:bg-slate-800 text-slate-400 hover:text-teal-300 transition"
                title="Rename current project"
              >
                <Edit2 className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={onOpenDeleteProject}
                className="p-1 rounded-md hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 transition"
                title="Delete current project"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        <button
          onClick={onOpenProjectManager}
          className="flex items-center gap-1.5 bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 font-semibold px-3 py-1.5 rounded-lg text-xs transition"
          title="Manage all projects, batch remove test projects, or switch projects"
        >
          <FolderKanban className="w-3.5 h-3.5 text-teal-400" />
          <span>Projects</span>
          {projects.length > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-slate-900 text-[10px] text-slate-400 font-mono">
              {projects.length}
            </span>
          )}
        </button>

        {currentProject && (
          <button
            onClick={onOpenDiary}
            className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500/20 to-cyan-500/20 hover:from-teal-500/30 hover:to-cyan-500/30 text-teal-300 border border-teal-500/40 font-semibold px-3 py-1.5 rounded-lg text-xs transition shadow-sm"
            title="Edit day-by-day itinerary, dates, discard/restore days, and re-phrase with AI"
          >
            <BookOpen className="w-3.5 h-3.5 text-teal-400" />
            Trip Diary
          </button>
        )}

        <button
          onClick={onOpenNewProject}
          className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 font-semibold px-3.5 py-1.5 rounded-lg text-sm transition-all shadow-sm shadow-teal-500/30"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>

        {/* Master Switch: Only Use Local AI */}
        <button
          onClick={() => onToggleLocalAi && onToggleLocalAi(!isLocalOnly)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition border ${
            isLocalOnly
              ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 hover:bg-amber-500/30'
              : 'bg-slate-800/90 text-slate-300 border-slate-700 hover:bg-slate-700'
          }`}
          title={isLocalOnly ? "Exclusively executing on local RTX GPU (Qwen3.5-4B)" : "Click to force 100% offline local AI execution"}
        >
          <Shield className={`w-3.5 h-3.5 ${isLocalOnly ? 'text-amber-400' : 'text-teal-400'}`} />
          <span>{isLocalOnly ? 'Local AI Only' : 'Cloud Waterfall'}</span>
        </button>

        <button
          onClick={onOpenModelManager}
          className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold px-3 py-1.5 rounded-lg text-xs transition"
          title="Configure Google AI Studio API key and view live quota pools"
        >
          <Cpu className="w-3.5 h-3.5 text-teal-400" />
          <span>AI Models</span>
          {hasGeminiKey && !isLocalOnly && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          )}
        </button>

        <button
          onClick={onShutdown}
          className="flex items-center gap-1.5 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 border border-rose-800/60 font-semibold px-3 py-1.5 rounded-lg text-xs transition"
          title="Gracefully stop Balladeer server and release GPU memory"
        >
          <Power className="w-3.5 h-3.5 text-rose-400" />
          Shutdown
        </button>

        {/* Model Loading / Active GPU Status Indicator */}
        {health?.loading_model ? (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/50 text-xs font-mono animate-pulse shadow-sm shadow-amber-500/20">
            <RefreshCw className="w-3.5 h-3.5 animate-spin text-amber-400" />
            <span>Loading {health.loading_model} into GPU...</span>
          </div>
        ) : health?.loaded_models && health.loaded_models.length > 0 ? (
          <div
            className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/90 border border-teal-500/30 text-xs font-mono text-slate-300"
            title={`Active models in VRAM: ${health.loaded_models.join(', ')}`}
          >
            <span className="w-2 h-2 rounded-full bg-teal-400 shadow-sm shadow-teal-400"></span>
            <span className="text-slate-400 text-[11px]">GPU:</span>
            <span className="text-teal-300 font-bold truncate max-w-[180px]">{health.loaded_models.join(' + ')}</span>
          </div>
        ) : null}

        {/* Hardware Status Badge */}
        <div className="hidden xl:flex items-center gap-3 pl-3 border-l border-slate-800 text-xs font-mono">
          <div className="flex items-center gap-1.5 text-slate-300">
            <Cpu className={`w-3.5 h-3.5 ${isCuda ? 'text-teal-400' : 'text-amber-400'}`} />
            <span>{isCuda ? 'CUDA Staged' : 'CPU Mode'}</span>
          </div>
          {vram && isCuda && (
            <div className="flex items-center gap-1.5 text-slate-400">
              <HardDrive className="w-3.5 h-3.5 text-cyan-400" />
              <span>
                VRAM: <span className="text-teal-300 font-semibold">{vram.allocated_gb}</span> / {vram.total_gb} GB
              </span>
            </div>
          )}
          <button
            onClick={onRefresh}
            title="Refresh State"
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </header>
  );
}
