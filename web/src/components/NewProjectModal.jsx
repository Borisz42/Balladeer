import React, { useState } from 'react';
import { X, Sparkles, Sliders, Image, Film, Music, Smartphone, Monitor, Square } from 'lucide-react';

export default function NewProjectModal({ isOpen, onClose, onCreate }) {
  const [title, setTitle] = useState('');
  const [narrativeText, setNarrativeText] = useState('');
  const [aspectRatio, setAspectRatio] = useState('16:9'); // '16:9', '9:16', '1:1'
  const [musicMode, setMusicMode] = useState('vocal'); // 'vocal', 'instrumental'
  const [bgMode, setBgMode] = useState('blurred_fill');
  const [enableKenBurns, setEnableKenBurns] = useState(false);
  const [photoBeatMin, setPhotoBeatMin] = useState(1);
  const [photoBeatMax, setPhotoBeatMax] = useState(3);
  const [videoBeatMin, setVideoBeatMin] = useState(2);
  const [videoBeatMax, setVideoBeatMax] = useState(5);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleLoadSampleDiary = () => {
    setTitle('Kyoto & Tokyo Expedition');
    setNarrativeText(`Day 1: Arrived in Kyoto amidst gentle autumn rain. Walked through the historic Gion district under red paper lanterns.
Day 2: Morning stroll through the whispering Arashiyama bamboo forest. Golden sunlight piercing through the towering stalks.
Day 3: Shinkansen bullet train to Tokyo. Neon lights blazing across the bustling Shibuya crossing at midnight.`);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim() || !narrativeText.trim()) return;

    setIsSubmitting(true);
    try {
      const configOverride = {
        video: {
          aspect_ratio: aspectRatio,
          default_bg_mode: bgMode,
          enable_ken_burns: enableKenBurns,
          photo_beat_range: [parseInt(photoBeatMin), parseInt(photoBeatMax)],
          video_beat_range: [parseInt(videoBeatMin), parseInt(videoBeatMax)]
        },
        audio: {
          is_instrumental: musicMode === 'instrumental'
        }
      };
      await onCreate(title, narrativeText, configOverride);
      onClose();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="glass-panel w-full max-w-2xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative max-h-[90vh] overflow-y-auto">
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
            <h2 className="text-lg font-bold text-white">Create New Montage Project</h2>
            <p className="text-xs text-slate-400">Configure diary story, aspect ratio & beat constraints</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Project Title
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Summer in the Alps"
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-teal-500"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Narrative / Trip Diary
              </label>
              <button
                type="button"
                onClick={handleLoadSampleDiary}
                className="text-xs text-teal-400 hover:text-teal-300 font-medium underline"
              >
                Load Sample Diary
              </button>
            </div>
            <textarea
              required
              rows={4}
              value={narrativeText}
              onChange={(e) => setNarrativeText(e.target.value)}
              placeholder="Paste your travel journal or story here. Mention Day 1, Day 2, etc. to partition musical acts..."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-teal-500 font-mono text-xs"
            />
          </div>

          {/* Aspect Ratio & Music Mode Selector */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-slate-800">
            {/* Canvas Aspect Ratio */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Output Video Aspect Ratio
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setAspectRatio('16:9')}
                  className={`p-2 rounded-lg border text-center transition flex flex-col items-center gap-1 ${
                    aspectRatio === '16:9'
                      ? 'border-teal-500 bg-teal-500/10 text-teal-300 font-bold'
                      : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-white'
                  }`}
                >
                  <Monitor className="w-4 h-4" />
                  <span className="text-[11px]">16:9</span>
                  <span className="text-[9px] opacity-75">YouTube / TV</span>
                </button>

                <button
                  type="button"
                  onClick={() => setAspectRatio('9:16')}
                  className={`p-2 rounded-lg border text-center transition flex flex-col items-center gap-1 ${
                    aspectRatio === '9:16'
                      ? 'border-teal-500 bg-teal-500/10 text-teal-300 font-bold'
                      : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-white'
                  }`}
                >
                  <Smartphone className="w-4 h-4" />
                  <span className="text-[11px]">9:16</span>
                  <span className="text-[9px] opacity-75">Shorts / Reels</span>
                </button>

                <button
                  type="button"
                  onClick={() => setAspectRatio('1:1')}
                  className={`p-2 rounded-lg border text-center transition flex flex-col items-center gap-1 ${
                    aspectRatio === '1:1'
                      ? 'border-teal-500 bg-teal-500/10 text-teal-300 font-bold'
                      : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-white'
                  }`}
                >
                  <Square className="w-4 h-4" />
                  <span className="text-[11px]">1:1</span>
                  <span className="text-[9px] opacity-75">Instagram Feed</span>
                </button>
              </div>
            </div>

            {/* Music & Subtitle Mode */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-2">
                Montage Audio & Subtitle Mode
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setMusicMode('vocal')}
                  className={`p-2.5 rounded-lg border text-center transition flex flex-col items-center gap-1 ${
                    musicMode === 'vocal'
                      ? 'border-teal-500 bg-teal-500/10 text-teal-300 font-bold'
                      : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-white'
                  }`}
                >
                  <Music className="w-4 h-4" />
                  <span className="text-xs">Vocal + Lyrics</span>
                  <span className="text-[9px] opacity-75">Karaoke highlight</span>
                </button>

                <button
                  type="button"
                  onClick={() => setMusicMode('instrumental')}
                  className={`p-2.5 rounded-lg border text-center transition flex flex-col items-center gap-1 ${
                    musicMode === 'instrumental'
                      ? 'border-teal-500 bg-teal-500/10 text-teal-300 font-bold'
                      : 'border-slate-800 bg-slate-950 text-slate-400 hover:text-white'
                  }`}
                >
                  <Film className="w-4 h-4" />
                  <span className="text-xs">Instrumental</span>
                  <span className="text-[9px] opacity-75">Event chapter cards</span>
                </button>
              </div>
            </div>
          </div>

          {/* Config-Driven Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-slate-800">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                <Image className="w-3.5 h-3.5 text-teal-400" />
                Background Fill Mode
              </label>
              <select
                value={bgMode}
                onChange={(e) => setBgMode(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white"
              >
                <option value="blurred_fill">Blurred & Zoomed Fill (Recommended Default)</option>
                <option value="black_bars">Classic Letterbox / Pillarbox</option>
                <option value="ken_burns_zoom">Direct Crop & Pan</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                <Film className="w-3.5 h-3.5 text-cyan-400" />
                Motion
              </label>
              <label className="flex items-center gap-2 mt-2 cursor-pointer text-xs text-slate-200">
                <input
                  type="checkbox"
                  checked={enableKenBurns}
                  onChange={(e) => setEnableKenBurns(e.target.checked)}
                  className="rounded border-slate-700 text-teal-500 focus:ring-teal-500 w-4 h-4"
                />
                <span>Enable Dynamic Ken Burns Pan/Zoom</span>
              </label>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-teal-400" />
                Photo Beat Range
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={8}
                  value={photoBeatMin}
                  onChange={(e) => setPhotoBeatMin(e.target.value)}
                  className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white text-center"
                />
                <span className="text-slate-500 text-xs">to</span>
                <input
                  type="number"
                  min={1}
                  max={8}
                  value={photoBeatMax}
                  onChange={(e) => setPhotoBeatMax(e.target.value)}
                  className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white text-center"
                />
                <span className="text-slate-400 text-xs">beats</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1 flex items-center gap-1.5">
                <Sliders className="w-3.5 h-3.5 text-cyan-400" />
                Video Beat Range
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min={1}
                  max={16}
                  value={videoBeatMin}
                  onChange={(e) => setVideoBeatMin(e.target.value)}
                  className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white text-center"
                />
                <span className="text-slate-500 text-xs">to</span>
                <input
                  type="number"
                  min={1}
                  max={16}
                  value={videoBeatMax}
                  onChange={(e) => setVideoBeatMax(e.target.value)}
                  className="w-20 bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white text-center"
                />
                <span className="text-slate-400 text-xs">beats</span>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 rounded-lg text-sm font-semibold bg-teal-500 hover:bg-teal-400 text-slate-950 transition shadow-lg shadow-teal-500/20"
            >
              {isSubmitting ? 'Creating...' : 'Create Project'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
