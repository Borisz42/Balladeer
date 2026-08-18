import React, { useState, useMemo } from 'react';
import {
  X,
  FolderKanban,
  Search,
  Plus,
  Trash2,
  Edit2,
  Check,
  Calendar,
  Layers,
  ArrowRight,
  AlertTriangle,
  CheckSquare,
  Square,
  Sparkles
} from 'lucide-react';

export default function ProjectManagerModal({
  isOpen,
  onClose,
  projects,
  currentProjectId,
  onSelectProject,
  onOpenNewProject,
  onRenameProject,
  onDeleteProject,
  onBatchDeleteProjects
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [editingProjectId, setEditingProjectId] = useState(null);
  const [editTitleText, setEditTitleText] = useState('');
  const [selectedProjectIds, setSelectedProjectIds] = useState(new Set());
  
  // Confirmation state for deleting
  const [deleteTarget, setDeleteTarget] = useState(null); // { type: 'single', project: p } | { type: 'batch', count: n }
  const [isDeleting, setIsDeleting] = useState(false);

  // Filter projects by search
  const filteredProjects = useMemo(() => {
    if (!searchQuery.trim()) return projects;
    const q = searchQuery.toLowerCase();
    return projects.filter(
      (p) =>
        p.title?.toLowerCase().includes(q) ||
        p.narrative_text?.toLowerCase().includes(q) ||
        p.id?.toLowerCase().includes(q)
    );
  }, [projects, searchQuery]);

  if (!isOpen) return null;

  const handleStartRename = (project, e) => {
    e?.stopPropagation();
    setEditingProjectId(project.id);
    setEditTitleText(project.title);
  };

  const handleSaveRename = async (projectId, e) => {
    e?.stopPropagation();
    if (!editTitleText.trim()) return;
    try {
      await onRenameProject(projectId, editTitleText.trim());
      setEditingProjectId(null);
    } catch (err) {
      alert('Failed to rename project: ' + err.message);
    }
  };

  const handleCancelRename = (e) => {
    e?.stopPropagation();
    setEditingProjectId(null);
    setEditTitleText('');
  };

  const toggleSelectProject = (projectId, e) => {
    e?.stopPropagation();
    const next = new Set(selectedProjectIds);
    if (next.has(projectId)) {
      next.delete(projectId);
    } else {
      next.add(projectId);
    }
    setSelectedProjectIds(next);
  };

  const toggleSelectAll = () => {
    if (selectedProjectIds.size === filteredProjects.length && filteredProjects.length > 0) {
      setSelectedProjectIds(new Set());
    } else {
      setSelectedProjectIds(new Set(filteredProjects.map((p) => p.id)));
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      if (deleteTarget.type === 'single') {
        await onDeleteProject(deleteTarget.project.id);
        const next = new Set(selectedProjectIds);
        next.delete(deleteTarget.project.id);
        setSelectedProjectIds(next);
      } else if (deleteTarget.type === 'batch') {
        await onBatchDeleteProjects(Array.from(selectedProjectIds));
        setSelectedProjectIds(new Set());
      }
      setDeleteTarget(null);
    } catch (err) {
      alert('Failed to delete: ' + err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const formatTimestamp = (ts) => {
    if (!ts) return 'Unknown date';
    try {
      const d = new Date(ts);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return ts;
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">Completed</span>;
      case 'ready':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-teal-500/10 text-teal-400 border border-teal-500/30">Ready</span>;
      case 'rendering':
      case 'solving':
      case 'generating_music':
      case 'indexing':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 animate-pulse">Processing</span>;
      case 'error':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30">Error</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700">Created</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="glass-panel w-full max-w-4xl max-h-[88vh] rounded-2xl bg-slate-900/95 border border-slate-800 shadow-2xl flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/80 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 flex items-center justify-center text-teal-400 shadow-sm">
              <FolderKanban className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">Project Manager</h2>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                  {projects.length} {projects.length === 1 ? 'project' : 'projects'}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Rename, switch between, or clean up testing projects
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                onClose();
                onOpenNewProject();
              }}
              className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 font-semibold px-3 py-1.5 rounded-lg text-xs transition shadow-sm"
            >
              <Plus className="w-3.5 h-3.5" />
              New Project
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search & Bulk Toolbar */}
        <div className="px-6 py-3 border-b border-slate-800/80 bg-slate-950/40 flex items-center justify-between gap-4 flex-wrap shrink-0">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search projects by title or narrative text..."
              className="w-full pl-9 pr-4 py-1.5 bg-slate-900 border border-slate-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500/50"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs"
              >
                Clear
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            {filteredProjects.length > 0 && (
              <button
                onClick={toggleSelectAll}
                className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded hover:bg-slate-800 transition"
              >
                {selectedProjectIds.size === filteredProjects.length && filteredProjects.length > 0 ? (
                  <CheckSquare className="w-4 h-4 text-teal-400" />
                ) : (
                  <Square className="w-4 h-4 text-slate-500" />
                )}
                <span>Select All ({filteredProjects.length})</span>
              </button>
            )}

            {selectedProjectIds.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-teal-400">
                  {selectedProjectIds.size} selected
                </span>
                <button
                  onClick={() => setDeleteTarget({ type: 'batch', count: selectedProjectIds.size })}
                  className="flex items-center gap-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 px-3 py-1.5 rounded-lg text-xs font-semibold transition"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete Selected ({selectedProjectIds.size})
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Project List Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-2.5">
          {filteredProjects.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <div className="w-12 h-12 rounded-xl bg-slate-800 text-slate-500 flex items-center justify-center mx-auto">
                <FolderKanban className="w-6 h-6" />
              </div>
              <p className="text-sm font-medium text-slate-400">
                {searchQuery ? 'No projects matching your search' : 'No projects found'}
              </p>
              <button
                onClick={() => {
                  onClose();
                  onOpenNewProject();
                }}
                className="inline-flex items-center gap-1.5 text-xs text-teal-400 hover:text-teal-300 font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                Create a new project
              </button>
            </div>
          ) : (
            filteredProjects.map((p) => {
              const isActive = p.id === currentProjectId;
              const isSelected = selectedProjectIds.has(p.id);
              const isEditing = editingProjectId === p.id;

              return (
                <div
                  key={p.id}
                  onClick={() => {
                    if (!isEditing && !isActive) {
                      onSelectProject(p.id);
                      onClose();
                    }
                  }}
                  className={`group rounded-xl border p-4 transition-all flex items-center justify-between gap-4 cursor-pointer ${
                    isActive
                      ? 'bg-teal-500/5 border-teal-500/40 shadow-sm'
                      : isSelected
                      ? 'bg-slate-800/80 border-slate-700'
                      : 'bg-slate-900/60 border-slate-800 hover:bg-slate-800/50 hover:border-slate-700'
                  }`}
                >
                  {/* Left: Checkbox + Title + Metadata */}
                  <div className="flex items-center gap-3.5 min-w-0 flex-1">
                    <button
                      onClick={(e) => toggleSelectProject(p.id, e)}
                      className="text-slate-400 hover:text-white p-1 -m-1 rounded transition"
                      title={isSelected ? 'Deselect project' : 'Select project'}
                    >
                      {isSelected ? (
                        <CheckSquare className="w-4 h-4 text-teal-400" />
                      ) : (
                        <Square className="w-4 h-4 text-slate-600 group-hover:text-slate-400" />
                      )}
                    </button>

                    <div className="min-w-0 flex-1">
                      {isEditing ? (
                        <div
                          className="flex items-center gap-2"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="text"
                            autoFocus
                            value={editTitleText}
                            onChange={(e) => setEditTitleText(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveRename(p.id, e);
                              if (e.key === 'Escape') handleCancelRename(e);
                            }}
                            className="bg-slate-950 border border-teal-500/50 rounded-lg px-2.5 py-1 text-sm font-semibold text-white focus:outline-none flex-1"
                          />
                          <button
                            onClick={(e) => handleSaveRename(p.id, e)}
                            className="p-1.5 rounded-lg bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 border border-teal-500/40"
                            title="Save title"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={handleCancelRename}
                            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white border border-slate-700"
                            title="Cancel"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-sm font-bold text-white truncate max-w-md group-hover:text-teal-300 transition">
                            {p.title}
                          </h3>
                          {isActive && (
                            <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-teal-500/20 text-teal-300 text-[10px] font-semibold border border-teal-500/40">
                              <span className="w-1.5 h-1.5 rounded-full bg-teal-400 animate-pulse"></span>
                              Active
                            </span>
                          )}
                          {getStatusBadge(p.status)}
                        </div>
                      )}

                      <div className="flex items-center gap-3 mt-1 text-[11px] text-slate-400 font-mono">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3 text-slate-500" />
                          {formatTimestamp(p.created_at)}
                        </span>
                        <span className="text-slate-600">•</span>
                        <span className="text-slate-500">{p.id}</span>
                      </div>
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div
                    className="flex items-center gap-1.5 shrink-0"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {!isEditing && (
                      <button
                        onClick={(e) => handleStartRename(p, e)}
                        className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700 transition"
                        title="Rename project"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    )}

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget({ type: 'single', project: p });
                      }}
                      className="p-2 rounded-lg bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 border border-slate-700 hover:border-rose-500/30 transition"
                      title="Delete project"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>

                    {!isActive && (
                      <button
                        onClick={() => {
                          onSelectProject(p.id);
                          onClose();
                        }}
                        className="flex items-center gap-1 bg-slate-800 hover:bg-teal-500/20 text-slate-300 hover:text-teal-300 border border-slate-700 hover:border-teal-500/30 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition ml-1"
                        title="Switch to this project"
                      >
                        <span>Open</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between text-xs text-slate-400 shrink-0">
          <div className="flex items-center gap-2">
            <span>Tip: Click on a project to open it, or use the pencil icon to rename it in place.</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-medium text-xs transition"
          >
            Done
          </button>
        </div>
      </div>

      {/* Confirmation Modal for Delete */}
      {deleteTarget && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4 bg-slate-950/90 backdrop-blur-md animate-in fade-in duration-150">
          <div className="glass-panel w-full max-w-md rounded-2xl bg-slate-900 border border-rose-500/30 shadow-2xl p-6 space-y-4">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">
                  {deleteTarget.type === 'single' ? 'Delete Project' : 'Delete Selected Projects'}
                </h3>
                <p className="text-xs text-slate-400">This action cannot be undone</p>
              </div>
            </div>

            <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-xs text-slate-300 leading-relaxed">
              {deleteTarget.type === 'single' ? (
                <>
                  Are you sure you want to permanently delete{' '}
                  <span className="font-bold text-white">"{deleteTarget.project.title}"</span>?
                  <br />
                  <span className="text-slate-400 mt-1 block">
                    All associated media indexes, audio tracks, timeline slices, and rendered video outputs will be deleted.
                  </span>
                </>
              ) : (
                <>
                  Are you sure you want to permanently delete all{' '}
                  <span className="font-bold text-white">{deleteTarget.count} selected projects</span>?
                  <br />
                  <span className="text-slate-400 mt-1 block">
                    All associated media indexes, uploaded assets, and rendered video files will be permanently erased.
                  </span>
                </>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setDeleteTarget(null)}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition shadow-lg shadow-rose-600/20"
              >
                <Trash2 className="w-3.5 h-3.5" />
                {isDeleting ? 'Deleting...' : 'Confirm Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
