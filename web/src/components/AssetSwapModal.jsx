import React, { useEffect, useState } from 'react';
import { X, Sparkles, Check, Image as ImageIcon, Video, Star, Sliders } from 'lucide-react';
import { getSliceRecommendations, swapSliceAsset, updateSlice } from '../api';

export default function AssetSwapModal({
  isOpen,
  onClose,
  project,
  slice,
  onAssetSwapped
}) {
  const [recommendations, setRecommendations] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [bgMode, setBgMode] = useState('blurred_fill');
  const [enableKenBurns, setEnableKenBurns] = useState(false);

  useEffect(() => {
    if (isOpen && slice && project) {
      setBgMode(slice.bg_mode || 'blurred_fill');
      setEnableKenBurns(slice.enable_ken_burns || false);
      fetchRecs();
    }
  }, [isOpen, slice, project]);

  const fetchRecs = async () => {
    setIsLoading(true);
    try {
      const data = await getSliceRecommendations(project.id, slice.id);
      setRecommendations(data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSwap = async (newAssetId) => {
    try {
      await swapSliceAsset(project.id, slice.id, newAssetId);
      onAssetSwapped();
      onClose();
    } catch (err) {
      alert('Failed to swap: ' + err.message);
    }
  };

  const handleSaveSliceSettings = async () => {
    try {
      await updateSlice(slice.id, {
        bg_mode: bgMode,
        enable_ken_burns: enableKenBurns
      });
      onAssetSwapped();
      onClose();
    } catch (err) {
      alert('Failed to update slice settings: ' + err.message);
    }
  };

  if (!isOpen || !slice) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="glass-panel w-full max-w-3xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2 mb-4">
          <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Clip Inspector & Recommendation Engine</h2>
            <p className="text-xs text-slate-400">
              Swap media shot using top-k CLIP visual similarity or customize slice background mode
            </p>
          </div>
        </div>

        {/* Current Active Clip & Settings */}
        <div className="bg-slate-950/80 rounded-xl p-4 border border-slate-800 space-y-3 mb-5">
          <div className="flex items-start justify-between">
            <div>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-300 border border-teal-500/30">
                Current Timeline Shot
              </span>
              <h3 className="text-sm font-bold text-white mt-1">
                {slice.asset?.caption || slice.asset?.file_path.split(/[\\/]/).pop()}
              </h3>
              <p className="text-xs text-slate-400 font-mono">
                Duration: {slice.beat_count} beats ({slice.timeline_start_sec}s - {slice.timeline_end_sec}s)
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-slate-300">Quality:</span>
              <span className="px-2 py-0.5 rounded bg-teal-500/20 text-teal-300 font-mono font-bold text-xs">
                ⭐ {slice.asset?.quality_score?.toFixed(1) || '7.5'}
              </span>
            </div>
          </div>

          {/* Per-Slice Settings */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t border-slate-800/80">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Aspect Ratio Background Fill
              </label>
              <select
                value={bgMode}
                onChange={(e) => setBgMode(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white"
              >
                <option value="blurred_fill">Blurred & Zoomed Background (Default)</option>
                <option value="black_bars">Black Letterbox / Pillarbox</option>
                <option value="ken_burns_zoom">Crop & Zoom</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">Motion</label>
              <label className="flex items-center gap-2 mt-2 cursor-pointer text-xs text-slate-200">
                <input
                  type="checkbox"
                  checked={enableKenBurns}
                  onChange={(e) => setEnableKenBurns(e.target.checked)}
                  className="rounded border-slate-700 text-teal-500 focus:ring-teal-500 w-4 h-4"
                />
                <span>Enable Ken Burns Pan/Zoom</span>
              </label>
            </div>
          </div>
          
          <div className="flex justify-end pt-1">
            <button
              onClick={handleSaveSliceSettings}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 rounded-lg border border-slate-700 transition"
            >
              Update Slice Settings
            </button>
          </div>
        </div>

        {/* Top-K Recommendations */}
        <div>
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-teal-400" />
            Top-5 CLIP Semantic Recommendations
          </h3>

          {isLoading ? (
            <div className="py-8 text-center text-xs text-slate-400 font-mono">
              Computing CLIP semantic similarity embeddings...
            </div>
          ) : recommendations.length === 0 ? (
            <div className="py-6 text-center text-xs text-slate-500">
              No alternative candidates found in project pool.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {recommendations.map((rec) => {
                const asset = rec.asset;
                const simPct = Math.round(rec.similarity_score * 100);

                return (
                  <div
                    key={asset.id}
                    className="glass-panel rounded-xl p-3 border border-slate-800 hover:border-teal-500/60 transition flex flex-col justify-between space-y-2 group"
                  >
                    <div className="flex items-start justify-between">
                      <span className="px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 font-mono text-[10px] font-bold">
                        {simPct}% Match
                      </span>
                      <span className="text-[10px] font-mono text-slate-400">
                        ⭐ {asset.quality_score?.toFixed(1)}
                      </span>
                    </div>

                    <p className="text-xs font-semibold text-white line-clamp-2">
                      {asset.caption || asset.file_path.split(/[\\/]/).pop()}
                    </p>

                    <button
                      onClick={() => handleSwap(asset.id)}
                      className="w-full py-1.5 rounded-lg bg-teal-500/10 hover:bg-teal-500 text-teal-400 hover:text-slate-950 font-bold text-xs transition flex items-center justify-center gap-1"
                    >
                      <Check className="w-3 h-3" />
                      Swap to This Shot
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
