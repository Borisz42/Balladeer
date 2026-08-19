import React, { useState, useRef } from 'react';
import { Music, Play, RotateCw, Mic, Disc3, BookOpen, Upload, Copy, Check, Sparkles } from 'lucide-react';

export default function MusicStudio({
  project,
  audioTrack,
  onGenerateMusic,
  onUploadAudio,
  onOpenDiary,
  isGenerating,
  health
}) {
  const [bpm, setBpm] = useState(audioTrack?.bpm || 120);
  const [duration, setDuration] = useState(15);
  const [prompt, setPrompt] = useState(audioTrack?.prompt || '');
  const [activeStem, setActiveStem] = useState('master');
  const [isInstrumental, setIsInstrumental] = useState(audioTrack?.is_instrumental || false);
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedLyrics, setCopiedLyrics] = useState(false);
  const [isUploadingAudio, setIsUploadingAudio] = useState(false);

  const fileInputRef = useRef(null);

  const handleGenerate = () => {
    onGenerateMusic({
      bpm: parseFloat(bpm),
      duration_sec: parseFloat(duration),
      prompt: prompt.trim() || undefined,
      is_instrumental: isInstrumental
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
    <div className="glass-panel rounded-2xl p-4 border border-slate-800 h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center shrink-0">
            <Disc3 className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-white uppercase tracking-wider truncate">
              Music Studio
            </h2>
            <p className="text-[10px] text-slate-400 truncate font-mono">
              Demucs + Trellis Beat Sync
            </p>
          </div>
        </div>

        <button
          onClick={handleGenerate}
          disabled={isGenerating || isUploadingAudio}
          className="flex items-center gap-1 bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 font-bold px-2.5 py-1 rounded-lg text-[11px] transition shadow-sm shrink-0"
        >
          <RotateCw className={`w-3 h-3 ${isGenerating ? 'animate-spin' : ''}`} />
          <span>{isGenerating ? 'Generating...' : 'Generate Music'}</span>
        </button>
      </div>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-3">
        {/* Duration & Mode Controls */}
        <div className="flex items-center justify-between gap-2 bg-slate-950/60 p-2 rounded-xl border border-slate-800/80 text-xs">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-slate-400">Duration:</span>
            <select
              value={duration}
              onChange={(e) => setDuration(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700 rounded px-1.5 py-0.5 text-teal-400 text-[11px] font-bold outline-none cursor-pointer"
            >
              <option value={10} className="bg-slate-900 text-white">10s</option>
              <option value={15} className="bg-slate-900 text-white">15s</option>
              <option value={20} className="bg-slate-900 text-white">20s</option>
              <option value={30} className="bg-slate-900 text-white">30s</option>
            </select>
          </div>

          <label className="flex items-center gap-1.5 text-[11px] text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={isInstrumental}
              onChange={(e) => setIsInstrumental(e.target.checked)}
              className="rounded border-slate-700 text-teal-500 w-3.5 h-3.5"
            />
            <span>Instrumental</span>
          </label>
        </div>

        {/* Audio Stems & Player */}
        <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800/80 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
              Audio Stems
            </span>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploadingAudio}
              className="flex items-center gap-1 text-[10px] bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 px-2 py-0.5 rounded font-semibold transition"
            >
              <Upload className="w-2.5 h-2.5" />
              {isUploadingAudio ? 'Uploading...' : 'Upload Audio'}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*,.wav,.mp3,.flac,.m4a"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>

          <div className="grid grid-cols-3 gap-1">
            <button
              onClick={() => setActiveStem('master')}
              className={`py-1 rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition ${
                activeStem === 'master'
                  ? 'bg-teal-500 text-slate-950 shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <Music className="w-2.5 h-2.5" /> Master
            </button>
            <button
              onClick={() => setActiveStem('vocals')}
              className={`py-1 rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition ${
                activeStem === 'vocals'
                  ? 'bg-teal-500 text-slate-950 shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <Mic className="w-2.5 h-2.5" /> Vocals
            </button>
            <button
              onClick={() => setActiveStem('accompaniment')}
              className={`py-1 rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition ${
                activeStem === 'accompaniment'
                  ? 'bg-teal-500 text-slate-950 shadow'
                  : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
              }`}
            >
              <Disc3 className="w-2.5 h-2.5" /> Backing
            </button>
          </div>

          {audioTrack ? (
            <div className="bg-slate-900 rounded-lg p-2 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-[10px] text-slate-300 font-mono">
                <span>Stem: <strong className="text-teal-300 uppercase">{activeStem}</strong></span>
                <span>{audioTrack.bpm} BPM</span>
              </div>
              <audio
                controls
                className="w-full h-7"
                src={`http://localhost:8000/api/projects/${project?.id}/audio/${activeStem}`}
              />
            </div>
          ) : (
            <div className="bg-slate-900/60 rounded-lg p-2 border border-slate-800 text-center text-[10px] text-slate-500">
              No audio track generated yet.
            </div>
          )}

          {/* Song Tempo (BPM) */}
          <div className="space-y-1 pt-1">
            <div className="flex justify-between text-[10px] text-slate-300">
              <span className="font-semibold">Song Tempo</span>
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
        </div>

        {/* Music Prompt */}
        <div className="space-y-1 bg-slate-950/60 rounded-xl p-2.5 border border-slate-800/80">
          <div className="flex items-center justify-between">
            <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-cyan-400" />
              Prompt
            </label>
            {(prompt || audioTrack?.prompt) && (
              <button
                onClick={handleCopyPrompt}
                className="flex items-center gap-1 text-[9px] text-teal-400 hover:text-teal-300 font-semibold"
              >
                {copiedPrompt ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5" />}
                {copiedPrompt ? 'Copied' : 'Copy'}
              </button>
            )}
          </div>
          <textarea
            rows={2}
            value={prompt || audioTrack?.prompt || ''}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="e.g. Uplifting acoustic indie pop with rhythmic guitar..."
            className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono leading-relaxed"
          />
        </div>

        {/* Structured Lyrics Block */}
        <div className="space-y-1 bg-slate-950/60 rounded-xl p-2.5 border border-slate-800/80">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
              {audioTrack?.is_instrumental ? 'Event Cards' : 'Lyrics'}
            </span>
            {audioTrack?.lyrics && (
              <button
                onClick={handleCopyLyrics}
                className="flex items-center gap-1 text-[9px] text-slate-300 hover:text-white"
              >
                {copiedLyrics ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5" />}
                {copiedLyrics ? 'Copied' : 'Copy'}
              </button>
            )}
          </div>

          <div className="max-h-28 overflow-y-auto font-mono text-[10px] text-slate-300 bg-slate-900/90 rounded-lg p-2 border border-slate-800 space-y-1">
            {audioTrack?.lyrics ? (
              audioTrack.lyrics.split('\n\n').map((block, i) => (
                <div key={i} className="pb-1 border-b border-slate-800/50 last:border-0">
                  {block.split('\n').map((line, j) => (
                    <p
                      key={j}
                      className={
                        line.startsWith('[')
                          ? 'text-teal-400 font-bold text-[9px] uppercase tracking-wide'
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
                Generate prompt & lyrics from diary to see 5-act rhythm structure.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
