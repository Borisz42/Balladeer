import React, { useState } from 'react';
import { Music, Sliders, Play, RotateCw, Volume2, Mic, Disc3, VolumeX } from 'lucide-react';

export default function MusicStudio({
  project,
  audioTrack,
  onGenerateMusic,
  isGenerating,
  health
}) {
  const [bpm, setBpm] = useState(audioTrack?.bpm || 120);
  const [duration, setDuration] = useState(15);
  const [prompt, setPrompt] = useState(audioTrack?.prompt || '');
  const [activeStem, setActiveStem] = useState('master');
  const [isInstrumental, setIsInstrumental] = useState(audioTrack?.is_instrumental || false);

  const handleGenerate = () => {
    onGenerateMusic({
      bpm: parseFloat(bpm),
      duration_sec: parseFloat(duration),
      prompt: prompt.trim() || undefined,
      is_instrumental: isInstrumental
    });
  };

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Disc3 className="w-4 h-4 text-teal-400" />
              Music & Lyric Studio (MiniMax 3 CMF + Demucs + MMS_FA)
            </h2>
            <span className="flex items-center gap-1.5 text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              MiniMax Music 3 CMF Native Engine Active (RTX GPU + Multi-Core)
            </span>
          </div>
          <p className="text-xs text-slate-400">
            Rhyming event lyrics, 2-stem vocal demixing, and CTC trellis forced alignment
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 rounded-lg px-2 py-1">
            <span className="text-[11px] text-slate-400">Duration:</span>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="bg-transparent text-teal-400 text-xs font-bold outline-none cursor-pointer"
            >
              <option value={10} className="bg-slate-900 text-white">10s (Fast Preview)</option>
              <option value={15} className="bg-slate-900 text-white">15s (Standard)</option>
              <option value={20} className="bg-slate-900 text-white">20s (Extended)</option>
              <option value={30} className="bg-slate-900 text-white">30s (Full Montage)</option>
            </select>
          </div>

          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={isInstrumental}
              onChange={(e) => setIsInstrumental(e.target.checked)}
              className="rounded border-slate-700 text-teal-500 w-3.5 h-3.5"
            />
            <span>Instrumental</span>
          </label>

          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="flex items-center gap-1.5 bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-1.5 rounded-lg text-xs transition shadow-md shadow-teal-500/20"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            {isGenerating ? 'Synthesizing & Aligning...' : 'Generate Beat & Lyrics'}
          </button>
        </div>
      </div>

      {/* Main Grid: Audio Stem Preview + Lyrics Display */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-5 space-y-4 bg-slate-950/60 rounded-xl p-4 border border-slate-800/80">
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Audio Stem Selector
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => setActiveStem('master')}
                className={`py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition ${
                  activeStem === 'master'
                    ? 'bg-teal-500 text-slate-950 shadow'
                    : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                <Music className="w-3 h-3" /> Master
              </button>
              <button
                onClick={() => setActiveStem('vocals')}
                className={`py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition ${
                  activeStem === 'vocals'
                    ? 'bg-teal-500 text-slate-950 shadow'
                    : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                <Mic className="w-3 h-3" /> Vocals
              </button>
              <button
                onClick={() => setActiveStem('accompaniment')}
                className={`py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition ${
                  activeStem === 'accompaniment'
                    ? 'bg-teal-500 text-slate-950 shadow'
                    : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                <Disc3 className="w-3 h-3" /> Backing
              </button>
            </div>
          </div>

          {audioTrack && (
            <div className="bg-slate-900 rounded-lg p-3 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-300 font-mono">
                <span>Stem: <strong className="text-teal-300 uppercase">{activeStem}</strong></span>
                <span>{audioTrack.bpm} BPM</span>
              </div>
              <audio
                controls
                className="w-full h-8"
                src={`http://localhost:8000/api/projects/${project.id}/audio/${activeStem}`}
              />
            </div>
          )}

          <div className="space-y-1">
            <div className="flex justify-between text-xs text-slate-300">
              <span className="font-semibold">Song Tempo (BPM)</span>
              <span className="font-mono text-teal-400 font-bold">{bpm} BPM</span>
            </div>
            <input
              type="range"
              min={80}
              max={160}
              step={1}
              value={bpm}
              onChange={(e) => setBpm(e.target.value)}
              className="w-full accent-teal-500"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-300">
              Musical Style Prompt
            </label>
            <input
              type="text"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Uplifting acoustic indie pop with rhythmic guitar..."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
            />
          </div>
        </div>

        {/* Right Col: Structured Rhyming Lyrics / Event Cards */}
        <div className="lg:col-span-7 bg-slate-950/60 rounded-xl p-4 border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                {audioTrack?.is_instrumental ? 'Documentary Event Cards' : 'Event-Structured Rhyming Lyrics'}
              </span>
              <span className="text-[11px] font-mono text-teal-400">
                {audioTrack?.aligned_lyrics?.length || 0} phoneme-aligned tokens
              </span>
            </div>

            <div className="max-h-56 overflow-y-auto font-mono text-xs text-slate-300 bg-slate-900/90 rounded-lg p-3 border border-slate-800 space-y-2 leading-relaxed">
              {audioTrack?.lyrics ? (
                audioTrack.lyrics.split('\n\n').map((block, i) => (
                  <div key={i} className="pb-1 border-b border-slate-800/50 last:border-0">
                    {block.split('\n').map((line, j) => (
                      <p
                        key={j}
                        className={
                          line.startsWith('[')
                            ? 'text-teal-400 font-bold text-[11px] uppercase tracking-wide pt-1'
                            : 'text-slate-200'
                        }
                      >
                        {line}
                      </p>
                    ))}
                  </div>
                ))
              ) : (
                <p className="text-slate-500 italic">
                  Click "Generate Beat & Lyrics" to compose musical acts from your diary.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
