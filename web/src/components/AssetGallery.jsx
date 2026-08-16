import React, { useState, useRef } from 'react';
import { Upload, FolderPlus, Image as ImageIcon, Video, Star, Tag, Clock } from 'lucide-react';

export default function AssetGallery({
  project,
  assets,
  onUploadFiles,
  onIndexDirectory,
  isLoading
}) {
  const fileInputRef = useRef(null);
  const [dirPath, setDirPath] = useState('');
  const [isIndexingDir, setIsIndexingDir] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUploadFiles(Array.from(e.target.files));
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
      alert('Failed to index directory: ' + err.message);
    } finally {
      setIsIndexingDir(false);
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
      {/* Header & Upload Controls */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <ImageIcon className="w-4 h-4 text-teal-400" />
            Media Asset Pool ({assets.length})
          </h2>
          <p className="text-xs text-slate-400">
            Photos and video clips indexed with VLM quality scores & CLIP embeddings
          </p>
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto">
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
            disabled={isLoading}
            className="flex-1 md:flex-none flex items-center justify-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition"
          >
            <Upload className="w-3.5 h-3.5 text-teal-400" />
            Upload Files
          </button>

          {/* Directory Ingestion Form */}
          <form onSubmit={handleIndexDirSubmit} className="flex-1 md:flex-none flex items-center gap-1">
            <input
              type="text"
              placeholder="C:/Photos/TripFolder"
              value={dirPath}
              onChange={(e) => setDirPath(e.target.value)}
              className="bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 w-44 font-mono"
            />
            <button
              type="submit"
              disabled={isIndexingDir || !dirPath.trim()}
              className="bg-slate-800 hover:bg-slate-700 text-teal-300 border border-slate-700 p-1.5 rounded-lg transition"
              title="Index local directory"
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
          <p className="text-sm font-semibold text-slate-300">No media uploaded yet</p>
          <p className="text-xs text-slate-500 mt-1">
            Drag & drop your photos and videos, or enter a folder path above.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 max-h-80 overflow-y-auto pr-1">
          {assets.map((asset) => {
            const isVideo = asset.media_type === 'video';
            const qualityColor =
              asset.quality_score >= 8.0
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                : asset.quality_score >= 6.0
                ? 'bg-teal-500/20 text-teal-300 border-teal-500/40'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/40';

            return (
              <div
                key={asset.id}
                className="group relative rounded-xl overflow-hidden bg-slate-900 border border-slate-800 hover:border-slate-700 transition flex flex-col"
              >
                {/* Media Preview Box */}
                <div className="h-28 w-full bg-slate-950 relative flex items-center justify-center overflow-hidden">
                  {isVideo ? (
                    <div className="flex flex-col items-center justify-center text-slate-500">
                      <Video className="w-8 h-8 text-cyan-400/80 mb-1" />
                      <span className="text-[10px] font-mono">{asset.duration_sec?.toFixed(1)}s</span>
                    </div>
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-600">
                      <ImageIcon className="w-8 h-8 text-teal-400/60" />
                    </div>
                  )}

                  {/* Quality Score Badge */}
                  <div
                    className={`absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold border flex items-center gap-0.5 ${qualityColor}`}
                  >
                    <Star className="w-2.5 h-2.5 fill-current" />
                    {asset.quality_score?.toFixed(1)}
                  </div>

                  {/* Media Type Tag */}
                  <div className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-black/60 backdrop-blur-sm text-[9px] font-mono text-slate-300 uppercase">
                    {asset.media_type}
                  </div>
                </div>

                {/* Info Card */}
                <div className="p-2 flex-1 flex flex-col justify-between bg-slate-900/90 text-left">
                  <p className="text-xs font-semibold text-slate-200 truncate" title={asset.caption || asset.file_path}>
                    {asset.caption || asset.file_path.split(/[\\/]/).pop()}
                  </p>
                  
                  <div className="mt-1 flex items-center gap-1 text-[10px] text-slate-400 font-mono">
                    <Clock className="w-2.5 h-2.5" />
                    <span className="truncate">{formatTime(asset.capture_time)}</span>
                  </div>

                  {asset.tags && asset.tags.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {asset.tags.slice(0, 2).map((t, idx) => (
                        <span
                          key={idx}
                          className="text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-400"
                        >
                          #{t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
