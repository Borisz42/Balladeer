import React, { useState, useRef } from 'react';
import { Upload, FolderPlus, Image as ImageIcon, Video, Star, Tag, Clock, Cpu, Sparkles, CheckCircle2, RotateCw } from 'lucide-react';

export default function AssetGallery({
  project,
  assets = [],
  selectedAsset,
  onSelectAsset,
  onUploadFiles,
  onIndexDirectory,
  onIndexPending,
  onAssetUpdated,
  onOpenDiary,
  isLoading
}) {
  const fileInputRef = useRef(null);
  const [dirPath, setDirPath] = useState('');
  const [isIndexingDir, setIsIndexingDir] = useState(false);
  const [isBatchIndexing, setIsBatchIndexing] = useState(false);

  const safeAssets = Array.isArray(assets) ? assets : [];
  const unindexedCount = safeAssets.filter((a) => a && !a.is_indexed).length;

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUploadFiles(Array.from(e.target.files));
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleIndexDirSubmit = async (e) => {
    e.preventDefault();
    if (!dirPath.trim()) return;
    setIsIndexingDir(true);
    try {
      await onIndexDirectory(dirPath);
      setDirPath('');
    } catch (err) {
      alert('Failed to stage directory: ' + err.message);
    } finally {
      setIsIndexingDir(false);
    }
  };

  const handleRunBatchIndexing = async () => {
    if (!onIndexPending) return;
    setIsBatchIndexing(true);
    try {
      await onIndexPending();
    } catch (err) {
      alert('Batch indexing failed: ' + err.message);
    } finally {
      setIsBatchIndexing(false);
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return '';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString();
    } catch {
      return '';
    }
  };

  const getFileName = (asset) => {
    if (asset.caption && asset.caption.trim()) return asset.caption;
    if (asset.file_path && typeof asset.file_path === 'string') {
      return asset.file_path.split(/[\\/]/).pop() || asset.file_path;
    }
    return asset.id || 'Media File';
  };

  return (
    <div className="glass-panel rounded-2xl p-4 border border-slate-800 h-full flex flex-col overflow-hidden">
      {/* Header & Controls */}
      <div className="flex flex-col gap-2.5 mb-3 pb-2 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <div className="w-6 h-6 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center shrink-0">
              <ImageIcon className="w-3.5 h-3.5" />
            </div>
            <h2 className="text-xs font-bold text-white uppercase tracking-wider truncate">
              Source Media ({safeAssets.length})
            </h2>
            {unindexedCount > 0 && (
              <span className="text-[9px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40 px-1.5 py-0.2 rounded-full font-bold">
                {unindexedCount} new
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            {safeAssets.length > 0 && (
              <button
                onClick={handleRunBatchIndexing}
                disabled={isLoading || isBatchIndexing}
                className="flex items-center gap-1 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 disabled:opacity-50 text-slate-950 px-2.5 py-1 rounded-lg text-[11px] font-bold transition shadow-sm"
                title="Run AI vision indexing on media"
              >
                <Sparkles className={`w-3 h-3 ${isBatchIndexing ? 'animate-spin' : ''}`} />
                <span>{isBatchIndexing ? 'Indexing...' : unindexedCount > 0 ? `Index (${unindexedCount})` : 'Re-Index'}</span>
              </button>
            )}

            <input
              type="file"
              multiple
              accept="image/*,video/*"
              ref={fileInputRef}
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || isBatchIndexing}
              className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-2 py-1 rounded-lg text-[11px] font-semibold transition"
              title="Upload media files"
            >
              <Upload className="w-3 h-3 text-teal-400" />
              <span>Upload</span>
            </button>
          </div>
        </div>

        {/* Directory Ingestion Form */}
        <form onSubmit={handleIndexDirSubmit} className="flex items-center gap-1.5">
          <input
            type="text"
            placeholder="Folder: C:/Photos/Trip..."
            value={dirPath}
            onChange={(e) => setDirPath(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-2 py-1 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
          />
          <button
            type="submit"
            disabled={isIndexingDir || !dirPath.trim()}
            className="bg-slate-800 hover:bg-slate-700 text-teal-300 border border-slate-700 px-2 py-1 rounded-lg text-[11px] font-semibold transition shrink-0"
            title="Import folder"
          >
            <FolderPlus className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>

      {/* Travel Log Approval Banner (Auto-Draft Mode) */}
      {project?.config_override?.travel_log_mode === 'auto_draft' &&
        !project?.config_override?.travel_log_approved &&
        safeAssets.some((a) => a.is_indexed) && (
          <div className="mb-2 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-between gap-2 shrink-0">
            <div className="flex items-center gap-1.5 min-w-0">
              <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="text-[11px] text-amber-200 truncate">
                AI indexed media. Review travel log to score relevance.
              </span>
            </div>
            {onOpenDiary && (
              <button
                type="button"
                onClick={onOpenDiary}
                className="px-2.5 py-1 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-[10px] transition shrink-0 shadow-sm"
              >
                Review Itinerary
              </button>
            )}
          </div>
        )}

      {/* Asset Grid */}
      <div className="flex-1 overflow-y-auto pr-1">
        {safeAssets.length === 0 ? (
          <div
            onClick={() => fileInputRef.current?.click()}
            className="h-full border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-xl p-4 text-center cursor-pointer transition bg-slate-950/40 flex flex-col items-center justify-center"
          >
            <Upload className="w-6 h-6 text-slate-600 mb-1" />
            <p className="text-xs font-semibold text-slate-300">No media added</p>
            <p className="text-[10px] text-slate-500 mt-0.5">
              Click to choose files or stage a local folder above.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(110px,1fr))] gap-2">
            {safeAssets.map((asset) => {
              if (!asset) return null;
              const isVideo = asset.media_type === 'video';
              const isSelected = selectedAsset?.id === asset.id;
              const qScore = typeof asset.quality_score === 'number' ? asset.quality_score : 7.0;
              const qualityColor =
                qScore >= 8.0
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : qScore >= 6.0
                  ? 'bg-teal-500/20 text-teal-300 border-teal-500/40'
                  : 'bg-amber-500/20 text-amber-300 border-amber-500/40';

              const thumbUrl = `http://localhost:8000/api/projects/${project?.id}/assets/${asset.id}/thumbnail`;
              const titleText = getFileName(asset);

              return (
                <div
                  key={asset.id}
                  onClick={() => onSelectAsset && onSelectAsset(asset)}
                  className={`group relative rounded-xl overflow-hidden bg-slate-900 border transition-all cursor-pointer flex flex-col ${
                    isSelected
                      ? 'border-teal-400 ring-2 ring-teal-400/40 shadow-lg shadow-teal-500/10 scale-[1.02]'
                      : 'border-slate-800 hover:border-slate-600'
                  }`}
                >
                  {/* Media Preview Thumbnail */}
                  <div className="aspect-[4/3] w-full bg-slate-950 relative flex items-center justify-center overflow-hidden">
                    <img
                      src={thumbUrl}
                      alt={titleText}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      loading="lazy"
                      onError={(e) => {
                        e.target.style.display = 'none';
                      }}
                    />

                    {isVideo && (
                      <div className="absolute inset-0 bg-black/30 flex items-center justify-center pointer-events-none">
                        <div className="w-5 h-5 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center text-white">
                          <Video className="w-3 h-3 text-cyan-400" />
                        </div>
                      </div>
                    )}

                    {/* Quality Score Badge */}
                    {asset.is_indexed && (
                      <div className="absolute top-1 right-1">
                        <div
                          className={`px-1 py-0.2 rounded text-[8px] font-mono font-bold border flex items-center gap-0.5 shadow ${qualityColor}`}
                        >
                          <Star className="w-2 h-2 fill-current" />
                          {qScore.toFixed(1)}
                        </div>
                      </div>
                    )}

                    {/* Unindexed Tag */}
                    {!asset.is_indexed && (
                      <div className="absolute top-1 right-1 px-1 py-0.2 rounded text-[8px] font-mono font-bold bg-amber-500/90 text-slate-950 uppercase shadow">
                        Pending
                      </div>
                    )}

                    {/* Media Type & Duration Tag */}
                    <div className="absolute bottom-1 left-1 px-1 py-0.2 rounded bg-black/75 backdrop-blur-sm text-[8px] font-mono text-slate-300 uppercase">
                      {isVideo ? `${(asset.duration_sec || 0).toFixed(0)}s` : 'photo'}
                    </div>
                  </div>

                  {/* Info Card */}
                  <div className="p-1.5 flex-1 flex flex-col justify-between bg-slate-900/90 text-left">
                    <p className="text-[10px] font-semibold text-slate-200 line-clamp-1 leading-tight" title={titleText}>
                      {titleText}
                    </p>
                    <div className="mt-1 flex items-center justify-between text-[8px] text-slate-500 font-mono">
                      <span>{formatTime(asset.capture_time)}</span>
                      <span className="text-teal-400 font-semibold">{isSelected ? 'Active' : 'Inspect'}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
