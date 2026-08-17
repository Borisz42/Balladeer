import React, { useState, useRef } from 'react';
import { Music, Sliders, Play, RotateCw, Volume2, Mic, Disc3, Upload, Copy, Check, Sparkles, AlertTriangle } from 'lucide-react';

export default function MusicStudio({
  project,
  audioTrack,
  onGenerateMusic,
  onUploadAudio,
  isGenerating,
  health
}) {
  const [bpm, setBpm] = useState(audioTrack?.bpm || 120);
  const [duration, setDuration] = useState(15);
  const [prompt, setPrompt] = useState(audioTrack?.prompt || '');
  const [activeStem, setActiveStem] = useState('master');
  const [isInstrumental, setIsInstrumental] = useState(audioTrack?.is_instrumental || false);
  const [enableLocalSynthesis, setEnableLocalSynthesis] = useState(false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedLyrics, setCopiedLyrics] = useState(false);
  const [isUploadingAudio, setIsUploadingAudio] = useState(false);

  const fileInputRef = useRef(null);

  const handleGenerate = () => {
    onGenerateMusic({
      bpm: parseFloat(bpm),
      duration_sec: parseFloat(duration),
      prompt: prompt.trim() || undefined,
      is_instrumental: isInstrumental,
      enable_local_synthesis: enableLocalSynthesis
    });
  };

  const handleCopyPrompt = () => {
    const textToCopy = prompt || audioTrack?.prompt || '';
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopiedPrompt(true);
      setTimeout(() => setCopiedPrompt(false), 2500);
    }
  };

  const handleCopyLyrics = () => {
    if (audioTrack?.lyrics) {
      navigator.clipboard.writeText(audioTrack.lyrics);
      setCopiedLyrics(true);
      setTimeout(() => setCopiedLyrics(false), 2500);
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !onUploadAudio) return;
    setIsUploadingAudio(true);
    try {
      await onUploadAudio(file, parseFloat(bpm), isInstrumental);
    } finally {
      setIsUploadingAudio(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-5 border border-slate-800 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Disc3 className="w-4 h-4 text-teal-400" />
              Music & Lyric Studio (Google Flow Music Optimizer + Demucs + MMS_FA)
            </h2>
            <span className="flex items-center gap-1.5 text-[10px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 px-2 py-0.5 rounded-full font-semibold">
              <Sparkles className="w-3 h-3 text-cyan-400" />
              Google Flow Music (MusicFX / Lyria) Prompt Engine
            </span>
          </div>
          <p className="text-xs text-slate-400">
            AI-optimized prompt generator, 5-act rhyming lyrics, Demucs 2-stem separation, and Trellis beat tracking
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

          <label className="flex items-center gap-2 text-xs text-amber-300 cursor-pointer bg-amber-500/10 border border-amber-500/30 px-2.5 py-1 rounded-lg" title="MiniMax Music 3 local inference is resource-intensive and slow">
            <input
              type="checkbox"
              checked={enableLocalSynthesis}
              onChange={(e) => setEnableLocalSynthesis(e.target.checked)}
              className="rounded border-amber-700 text-amber-500 w-3.5 h-3.5"
            />
            <span className="font-semibold text-[11px]">Local MiniMax 3 Engine (Slow)</span>
          </label>

          <button
            onClick={handleGenerate}
            disabled={isGenerating || isUploadingAudio}
            className="flex items-center gap-1.5 bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 font-bold px-4 py-1.5 rounded-lg text-xs transition shadow-md shadow-teal-500/20"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            {isGenerating ? 'Generating...' : 'Generate Prompts & Lyrics'}
          </button>
        </div>
      </div>

      {/* Main Grid: Audio Stem Preview + Google Flow Music & Lyrics */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-5 space-y-4 bg-slate-950/60 rounded-xl p-4 border border-slate-800/80">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Audio Stems & Track Player
              </label>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploadingAudio}
                className="flex items-center gap-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 px-2 py-0.5 rounded font-semibold transition"
              >
                <Upload className="w-3 h-3" />
                {isUploadingAudio ? 'Processing Stem Audio...' : 'Upload Google Flow Audio'}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*,.wav,.mp3,.flac,.m4a"
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

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

          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-cyan-400" />
                Google Flow Music Prompt
              </label>
              {(prompt || audioTrack?.prompt) && (
                <button
                  onClick={handleCopyPrompt}
                  className="flex items-center gap-1 text-[10px] text-teal-400 hover:text-teal-300 font-semibold"
                >
                  {copiedPrompt ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  {copiedPrompt ? 'Copied!' : 'Copy Prompt'}
                </button>
              )}
            </div>
            <textarea
              rows={3}
              value={prompt || audioTrack?.prompt || ''}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g. Uplifting acoustic indie pop with rhythmic guitar, warm vocals, 120 BPM..."
              className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono leading-relaxed"
            />
          </div>
        </div>

        {/* Right Col: Structured Rhyming Lyrics / Event Cards */}
        <div className="lg:col-span-7 bg-slate-950/60 rounded-xl p-4 border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                {audioTrack?.is_instrumental ? 'Documentary Event Cards' : '5-Act Structured Rhyming Lyrics'}
              </span>
              <div className="flex items-center gap-3">
                <span className="text-[11px] font-mono text-teal-400">
                  {audioTrack?.aligned_lyrics?.length || 0} phoneme-aligned tokens
                </span>
                {audioTrack?.lyrics && (
                  <button
                    onClick={handleCopyLyrics}
                    className="flex items-center gap-1 text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-2 py-0.5 rounded font-semibold transition"
                  >
                    {copiedLyrics ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    {copiedLyrics ? 'Copied!' : 'Copy Lyrics'}
                  </button>
                )}
              </div>
            </div>

            <div className="max-h-64 overflow-y-auto font-mono text-xs text-slate-300 bg-slate-900/90 rounded-lg p-3 border border-slate-800 space-y-2 leading-relaxed">
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
                  Click "Generate Prompts & Lyrics" to compose musical acts from your travel diary.
                </p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
