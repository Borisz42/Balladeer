import React, { useState, useEffect } from 'react';
import { X, Star, Tag, Clock, Cpu, Save, RotateCw, CheckCircle2, AlertCircle, Image as ImageIcon, Video, Shield } from 'lucide-react';
import { updateAsset, reindexAsset } from '../api';

export default function AssetDetailModal({ isOpen, onClose, project, asset, onAssetUpdated }) {
  const [caption, setCaption] = useState('');
  const [tagsText, setTagsText] = useState('');
  const [qualityScore, setQualityScore] = useState(7.0);
  const [isActive, setIsActive] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    if (asset) {
      setCaption(asset.caption || '');
      setTagsText(asset.tags ? asset.tags.join(', ') : '');
      setQualityScore(asset.quality_score || 7.0);
      setIsActive(asset.is_active !== undefined ? asset.is_active : true);
      setStatusMessage(null);
      setErrorMessage(null);
    }
  }, [asset]);

  if (!isOpen || !asset) return null;

  const isVideo = asset.media_type === 'video';
  const fileUrl = `http://localhost:8000/api/projects/${project.id}/assets/${asset.id}/file`;
  const thumbUrl = `http://localhost:8000/api/projects/${project.id}/assets/${asset.id}/thumbnail`;

  const handleSave = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const parsedTags = tagsText
        .split(',')
        .map((t) => t.trim().replace(/^#/, ''))
        .filter(Boolean);

      const updated = await updateAsset(project.id, asset.id, {
        caption: caption.trim(),
        tags: parsedTags,
        quality_score: parseFloat(qualityScore),
        is_active: isActive
      });

      setStatusMessage('AI analysis and caption successfully updated in database.');
      if (onAssetUpdated) onAssetUpdated(updated);
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err) {
      setErrorMessage('Failed to save changes: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReindex = async () => {
    setIsReindexing(true);
    setErrorMessage(null);
    try {
      const updated = await reindexAsset(project.id, asset.id);
      setCaption(updated.caption || '');
      setTagsText(updated.tags ? updated.tags.join(', ') : '');
      setQualityScore(updated.quality_score || 7.0);
      setStatusMessage(`Re-indexed with ${updated.indexed_by_model || 'AI'}!`);
      if (onAssetUpdated) onAssetUpdated(updated);
      setTimeout(() => setStatusMessage(null), 4000);
    } catch (err) {
      setErrorMessage('Re-indexing failed: ' + err.message);
    } finally {
      setIsReindexing(false);
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4">
      <div className="glass-panel w-full max-w-4xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative max-h-[92vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Title */}
        <div className="flex items-center gap-3 mb-4 pb-3 border-b border-slate-800">
          <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center">
            {isVideo ? <Video className="w-4 h-4" /> : <ImageIcon className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Media Asset Inspector & AI Editor</h2>
            <p className="text-xs text-slate-400 truncate max-w-md font-mono">
              {asset.file_path.split(/[\\/]/).pop()}
            </p>
          </div>
        </div>

        {/* Feedback alerts */}
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

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Large Media Preview */}
          <div className="lg:col-span-6 flex flex-col space-y-3">
            <div className="w-full h-72 sm:h-80 bg-slate-950 rounded-xl overflow-hidden border border-slate-800 flex items-center justify-center relative">
              {isVideo ? (
                <video
                  controls
                  className="w-full h-full object-contain"
                  src={fileUrl}
                  poster={thumbUrl}
                />
              ) : (
                <img
                  src={fileUrl}
                  alt={caption}
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    e.target.src = thumbUrl;
                  }}
                />
              )}
              
              <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 backdrop-blur-sm text-[10px] font-mono text-slate-300 uppercase">
                {asset.media_type} {asset.width && asset.height ? `• ${asset.width}x${asset.height}` : ''}
              </div>
            </div>

            {/* Technical Metadata Bar */}
            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-[11px] font-mono text-slate-400 space-y-1">
              <div className="flex justify-between">
                <span>Capture Timestamp:</span>
                <span className="text-slate-200">{formatTime(asset.capture_time)}</span>
              </div>
              {isVideo && (
                <div className="flex justify-between">
                  <span>Video Duration:</span>
                  <span className="text-cyan-400 font-bold">{asset.duration_sec?.toFixed(1)} seconds</span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Indexed Status:</span>
                <span className={asset.is_indexed ? 'text-teal-400 font-bold' : 'text-amber-400 font-bold'}>
                  {asset.is_indexed ? 'Indexed with VLM' : 'Pending AI Analysis'}
                </span>
              </div>
            </div>
          </div>

          {/* Right: AI Understanding & User Edit Controls */}
          <div className="lg:col-span-6 space-y-4">
            {/* Model Attribution Badge */}
            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-teal-400" />
                <div>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-mono">
                    AI Vision Model Used
                  </span>
                  <strong className="text-xs font-bold text-white uppercase font-mono">
                    {asset.indexed_by_model || (asset.is_indexed ? 'Qwen3.5-4B / Gemini' : 'Not Yet Indexed')}
                  </strong>
                </div>
              </div>

              <button
                onClick={handleReindex}
                disabled={isReindexing || isSaving}
                className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-cyan-300 border border-slate-700 px-3 py-1 rounded-lg text-xs font-semibold transition"
                title="Re-run VLM prompt on this single photo/clip"
              >
                <RotateCw className={`w-3.5 h-3.5 ${isReindexing ? 'animate-spin' : ''}`} />
                {isReindexing ? 'Analyzing...' : 'Re-Index AI'}
              </button>
            </div>

            {/* AI Caption & Description */}
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Scene Caption & Lyric Matching Concept
              </label>
              <textarea
                rows={3}
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="Describe the mood, subject, and action in this scene..."
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono leading-relaxed"
              />
            </div>

            {/* Quality Score Slider */}
            <div className="space-y-1.5 bg-slate-950 p-3 rounded-xl border border-slate-800">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-slate-300 flex items-center gap-1">
                  <Star className="w-3.5 h-3.5 text-amber-400 fill-current" />
                  Cinematic Quality Score
                </span>
                <span className="font-mono text-teal-400 font-bold text-sm">
                  {qualityScore.toFixed(1)} / 10.0
                </span>
              </div>
              <input
                type="range"
                min={1.0}
                max={10.0}
                step={0.1}
                value={qualityScore}
                onChange={(e) => setQualityScore(parseFloat(e.target.value))}
                className="w-full accent-teal-500"
              />
              <p className="text-[10px] text-slate-500">
                Higher scores give this asset priority placement during key chorus and musical climax moments.
              </p>
            </div>

            {/* AI Tags */}
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                <Tag className="w-3.5 h-3.5 text-teal-400" />
                Descriptive Tags (Comma-separated)
              </label>
              <input
                type="text"
                value={tagsText}
                onChange={(e) => setTagsText(e.target.value)}
                placeholder="sunset, beach, travel, happiness, nature"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
              />
            </div>

            {/* Active Switch */}
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-slate-700 text-teal-500 w-4 h-4"
              />
              <span>Include this asset in the montage video</span>
            </label>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Close
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving || isReindexing}
                className="flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-bold bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 transition shadow-lg shadow-teal-500/20"
              >
                <Save className="w-3.5 h-3.5" />
                {isSaving ? 'Saving...' : 'Save AI Changes'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
