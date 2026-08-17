import React, { useState, useRef } from 'react';
import { Upload, FolderPlus, Image as ImageIcon, Video, Star, Tag, Clock, Cpu, Sparkles, CheckCircle2, RotateCw } from 'lucide-react';
import AssetDetailModal from './AssetDetailModal';

export default function AssetGallery({
  project,
  assets,
  onUploadFiles,
  onIndexDirectory,
  onIndexPending,
  onAssetUpdated,
  isLoading
}) {
  const fileInputRef = useRef(null);
  const [dirPath, setDirPath] = useState('');
  const [isIndexingDir, setIsIndexingDir] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [isBatchIndexing, setIsBatchIndexing] = useState(false);

  const unindexedCount = assets.filter((a) => !a.is_indexed).length;

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
    if (!isoString) return 'Unknown';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
      {/* Header & Controls */}
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <ImageIcon className="w-4 h-4 text-teal-400" />
              Media Asset Pool ({assets.length})
            </h2>
            {unindexedCount > 0 && (
              <span className="text-[11px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded-full font-bold">
                {unindexedCount} Pending AI Analysis
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400">
            Step 1: Choose files or folder • Step 2: Click "Index Media" to run the AI Model Waterfall
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap w-full lg:w-auto">
          {/* Index Pending Button */}
          {assets.length > 0 && (
            <button
              onClick={handleRunBatchIndexing}
              disabled={isLoading || isBatchIndexing}
              className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 disabled:opacity-50 text-slate-950 px-4 py-1.5 rounded-lg text-xs font-bold transition shadow-md shadow-teal-500/20"
              title="Run AI vision indexing on unindexed media using Google AI Studio & local fallback"
            >
              <Sparkles className={`w-3.5 h-3.5 ${isBatchIndexing ? 'animate-spin' : ''}`} />
              {isBatchIndexing
                ? 'AI Indexing in Progress...'
                : unindexedCount > 0
                ? `Index Media (${unindexedCount} files)`
                : 'Re-Index All Media'}
            </button>
          )}

          {/* File Upload Button */}
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
            className="flex items-center justify-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition"
          >
            <Upload className="w-3.5 h-3.5 text-teal-400" />
            Upload Files
          </button>

          {/* Directory Ingestion Form */}
          <form onSubmit={handleIndexDirSubmit} className="flex items-center gap-1">
            <input
              type="text"
              placeholder="C:/Photos/TripFolder"
              value={dirPath}
              onChange={(e) => setDirPath(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 w-40 font-mono"
            />
            <button
              type="submit"
              disabled={isIndexingDir || !dirPath.trim()}
              className="bg-slate-800 hover:bg-slate-700 text-teal-300 border border-slate-700 p-1.5 rounded-lg transition"
              title="Stage local folder"
            >
              <FolderPlus className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      </div>

      {/* Asset Grid */}
      {assets.length === 0 ? (
        <div
          onClick={() => fileInputRef.current?.click()}
          className="border-2 border-dashed border-slate-800 hover:border-slate-700 rounded-xl p-8 text-center cursor-pointer transition bg-slate-950/40"
        >
          <Upload className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <p className="text-sm font-semibold text-slate-300">No media chosen yet</p>
          <p className="text-xs text-slate-500 mt-1">
            Step 1: Choose photos & videos or enter a folder path above to stage your vacation media.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 max-h-96 overflow-y-auto pr-1">
          {assets.map((asset) => {
            const isVideo = asset.media_type === 'video';
            const qualityColor =
              asset.quality_score >= 8.0
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                : asset.quality_score >= 6.0
                ? 'bg-teal-500/20 text-teal-300 border-teal-500/40'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/40';

            const thumbUrl = `http://localhost:8000/api/projects/${project.id}/assets/${asset.id}/thumbnail`;

            return (
              <div
                key={asset.id}
                onClick={() => setSelectedAsset(asset)}
                className="group relative rounded-xl overflow-hidden bg-slate-900 border border-slate-800 hover:border-teal-500/60 transition-all cursor-pointer flex flex-col hover:shadow-lg hover:shadow-teal-500/10"
              >
                {/* Media Preview Thumbnail */}
                <div className="h-28 w-full bg-slate-950 relative flex items-center justify-center overflow-hidden">
                  <img
                    src={thumbUrl}
                    alt={asset.caption || asset.file_path}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                    loading="lazy"
                    onError={(e) => {
                      e.target.style.display = 'none';
                    }}
                  />

                  {isVideo && (
                    <div className="absolute inset-0 bg-black/30 flex items-center justify-center pointer-events-none">
                      <div className="w-7 h-7 rounded-full bg-black/60 backdrop-blur-sm flex items-center justify-center text-white">
                        <Video className="w-3.5 h-3.5 text-cyan-400" />
                      </div>
                    </div>
                  )}

                  {/* Quality Score Badge */}
                  {asset.is_indexed && (
                    <div
                      className={`absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold border flex items-center gap-0.5 shadow ${qualityColor}`}
                    >
                      <Star className="w-2.5 h-2.5 fill-current" />
                      {asset.quality_score?.toFixed(1)}
                    </div>
                  )}

                  {/* Pending Indexing Badge */}
                  {!asset.is_indexed && (
                    <div className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-amber-500/90 text-slate-950 shadow uppercase">
                      Unindexed
                    </div>
                  )}

                  {/* Media Type & Duration Tag */}
                  <div className="absolute bottom-1.5 left-1.5 px-1.5 py-0.5 rounded bg-black/75 backdrop-blur-sm text-[9px] font-mono text-slate-300 uppercase">
                    {isVideo ? `${asset.duration_sec?.toFixed(0)}s video` : 'photo'}
                  </div>
                </div>

                {/* Info Card */}
                <div className="p-2.5 flex-1 flex flex-col justify-between bg-slate-900/90 text-left">
                  <div>
                    <p className="text-xs font-semibold text-slate-200 line-clamp-2 leading-tight" title={asset.caption || asset.file_path}>
                      {asset.caption || asset.file_path.split(/[\\/]/).pop()}
                    </p>
                    
                    {/* Model Attribution Chip */}
                    <div className="mt-1 flex items-center gap-1 text-[9px] font-mono text-slate-400 truncate">
                      <Cpu className="w-2.5 h-2.5 text-teal-400 shrink-0" />
                      <span className="truncate text-teal-300">
                        {asset.indexed_by_model || (asset.is_indexed ? 'AI Indexed' : 'Pending')}
                      </span>
                    </div>
                  </div>

                  <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-500 font-mono">
                    <span className="truncate">{formatTime(asset.capture_time).split(' ')[0]}</span>
                    <span className="text-teal-400 group-hover:underline text-[9px]">Inspect →</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Asset Detail & AI Editor Modal */}
      <AssetDetailModal
        isOpen={!!selectedAsset}
        onClose={() => setSelectedAsset(null)}
        project={project}
        asset={selectedAsset}
        onAssetUpdated={(updated) => {
          setSelectedAsset(updated);
          if (onAssetUpdated) onAssetUpdated(updated);
        }}
      />
    </div>
  );
}
