import React, { useState, useEffect, useRef } from 'react';
import {
  Music,
  Play,
  RotateCw,
  Mic,
  Disc3,
  BookOpen,
  Upload,
  Copy,
  Check,
  Sparkles,
  Sliders,
  Clock,
  Layers,
  ChevronDown,
  ChevronUp,
  Zap,
  Activity,
  CheckCircle2,
  Calendar,
  Volume2,
  Edit3
} from 'lucide-react';
import {
  analyzeMusicTimeline,
  generateMusicPrompt,
  generateMusicLyrics,
  synthesizeMusicAudio
} from '../api';

export default function MusicStudio({
  project,
  audioTrack,
  timelineEstimate,
  onTimelineEstimateUpdated,
  onGenerateMusic,
  onUploadAudio,
  onOpenDiary,
  onOpenLyricEditor,
  isGenerating,
  health
}) {
  // Pacing & Threshold Configuration State
  const [pacingPreset, setPacingPreset] = useState(
    project?.config_override?.pacing_rules?.pacing_preset || 'balanced'
  );
  const [defaultThreshold, setDefaultThreshold] = useState(
    project?.config_override?.default_inclusion_threshold || 70.0
  );
  const [dailyThresholds, setDailyThresholds] = useState(
    project?.config_override?.daily_inclusion_thresholds || {}
  );
  const [styleVibe, setStyleVibe] = useState(
    project?.config_override?.style_vibe || ''
  );

  // Music Generation Parameters
  const [bpm, setBpm] = useState(audioTrack?.bpm || timelineEstimate?.suggested_bpm || 118);
  const [duration, setDuration] = useState(
    timelineEstimate?.total_duration_sec || 30
  );
  const [manualDurationOverride, setManualDurationOverride] = useState(false);
  const [prompt, setPrompt] = useState(audioTrack?.prompt || '');
  const [lyrics, setLyrics] = useState(audioTrack?.lyrics || '');
  const [activeStem, setActiveStem] = useState('master');
  const [isInstrumental, setIsInstrumental] = useState(audioTrack?.is_instrumental || false);

  // UI / Copy / Loading States
  const [copiedPrompt, setCopiedPrompt] = useState(false);
  const [copiedLyrics, setCopiedLyrics] = useState(false);
  const [isUploadingAudio, setIsUploadingAudio] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [isGeneratingLyrics, setIsGeneratingLyrics] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [activeSectionTab, setActiveSectionTab] = useState('pacing'); // 'pacing' | 'prompt' | 'lyrics' | 'audio'
  const [statusNote, setStatusNote] = useState(null);

  const fileInputRef = useRef(null);

  // Sync state when project, audioTrack or timelineEstimate changes
  useEffect(() => {
    if (audioTrack) {
      if (audioTrack.bpm) setBpm(audioTrack.bpm);
      if (audioTrack.prompt) setPrompt(audioTrack.prompt);
      if (audioTrack.lyrics) setLyrics(audioTrack.lyrics);
      if (audioTrack.is_instrumental !== undefined) setIsInstrumental(audioTrack.is_instrumental);
    }
  }, [audioTrack]);

  useEffect(() => {
    if (timelineEstimate) {
      if (!manualDurationOverride && timelineEstimate.total_duration_sec) {
        setDuration(timelineEstimate.total_duration_sec);
      }
      if (!audioTrack && timelineEstimate.suggested_bpm) {
        setBpm(timelineEstimate.suggested_bpm);
      }
    }
  }, [timelineEstimate, manualDurationOverride, audioTrack]);

  // Initial timeline analysis on project load if not present
  useEffect(() => {
    if (project?.id && !timelineEstimate && !isAnalyzing) {
      handleAnalyzeTimeline();
    }
  }, [project?.id]);

  // Phase 1: Analyze Timeline & Pacing
  const handleAnalyzeTimeline = async (overridePacing, overrideThresholds) => {
    if (!project?.id) return;
    setIsAnalyzing(true);
    setStatusNote('Analyzing media scores & calculating timeline pacing...');
    try {
      const activePacing = overridePacing || pacingPreset;
      const activeThresholds = overrideThresholds || dailyThresholds;
      const res = await analyzeMusicTimeline(project.id, {
        pacingPreset: activePacing,
        defaultThreshold: defaultThreshold,
        dailyThresholds: activeThresholds
      });
      if (onTimelineEstimateUpdated) {
        onTimelineEstimateUpdated(res);
      }
      if (!manualDurationOverride && res.total_duration_sec) {
        setDuration(res.total_duration_sec);
      }
      if (!audioTrack && res.suggested_bpm) {
        setBpm(res.suggested_bpm);
      }
      setStatusNote(`Timeline calculated: ${res.total_duration_sec}s (${res.acts?.length || 0} sections).`);
      setTimeout(() => setStatusNote(null), 3500);
    } catch (err) {
      alert('Timeline analysis failed: ' + err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Phase 2: Generate Flow Music Prompt
  const handleGeneratePrompt = async () => {
    if (!project?.id) return;
    setIsGeneratingPrompt(true);
    setStatusNote('Synthesizing Google Flow Music prompt with section cues...');
    try {
      const acts = timelineEstimate?.acts || undefined;
      const res = await generateMusicPrompt(project.id, {
        styleVibe: styleVibe.trim() || undefined,
        suggestedBpm: parseInt(bpm) || 118,
        totalDurationSec: parseFloat(duration) || 30.0,
        acts: acts
      });
      if (res.flow_prompt) {
        setPrompt(res.flow_prompt);
      }
      if (res.suggested_bpm) {
        setBpm(res.suggested_bpm);
      }
      setStatusNote('Flow Music prompt generated successfully!');
      setTimeout(() => setStatusNote(null), 3000);
    } catch (err) {
      alert('Prompt generation failed: ' + err.message);
    } finally {
      setIsGeneratingPrompt(false);
    }
  };

  // Phase 3: Generate Structured Rhyming Lyrics
  const handleGenerateLyrics = async () => {
    if (!project?.id) return;
    setIsGeneratingLyrics(true);
    setStatusNote('Generating proportional rhyming lyrics with timing tags...');
    try {
      const acts = timelineEstimate?.acts || undefined;
      const res = await generateMusicLyrics(project.id, {
        flowPrompt: prompt.trim() || undefined,
        isInstrumental: isInstrumental,
        acts: acts
      });
      if (res.lyrics) {
        setLyrics(res.lyrics);
      }
      if (res.prompt && !prompt) {
        setPrompt(res.prompt);
      }
      setStatusNote('Lyrics & event cards generated successfully!');
      setTimeout(() => setStatusNote(null), 3000);
    } catch (err) {
      alert('Lyrics generation failed: ' + err.message);
    } finally {
      setIsGeneratingLyrics(false);
    }
  };

  // Phase 4: Analyze Audio & Align Stems / Subtitles
  const handleSynthesizeAudio = async () => {
    if (!onGenerateMusic) return;
    setIsSynthesizing(true);
    try {
      await onGenerateMusic({
        bpm: parseFloat(bpm),
        duration_sec: parseFloat(duration),
        prompt: prompt.trim() || undefined,
        lyrics: lyrics.trim() || undefined,
        is_instrumental: isInstrumental
      });
      setStatusNote('Audio analyzed, stems separated and subtitles/lyrics aligned!');
      setTimeout(() => setStatusNote(null), 3500);
    } finally {
      setIsSynthesizing(false);
    }
  };

  // One-Click Auto-Generate All
  const handleAutoGenerateAll = async () => {
    setIsSynthesizing(true);
    setStatusNote('Executing full 4-phase music workflow...');
    try {
      // 1. Analyze
      const est = await analyzeMusicTimeline(project.id, {
        pacingPreset: pacingPreset,
        defaultThreshold: defaultThreshold,
        dailyThresholds: dailyThresholds
      });
      if (onTimelineEstimateUpdated) onTimelineEstimateUpdated(est);
      const estDur = est.total_duration_sec || duration;
      const estBpm = est.suggested_bpm || bpm;
      setDuration(estDur);
      setBpm(estBpm);

      // 2. Prompt
      const pRes = await generateMusicPrompt(project.id, {
        styleVibe: styleVibe.trim() || undefined,
        suggestedBpm: parseInt(estBpm),
        totalDurationSec: parseFloat(estDur),
        acts: est.acts
      });
      const finalPrompt = pRes.flow_prompt || prompt;
      setPrompt(finalPrompt);

      // 3. Lyrics
      const lRes = await generateMusicLyrics(project.id, {
        flowPrompt: finalPrompt,
        isInstrumental: isInstrumental,
        acts: est.acts
      });
      const finalLyrics = lRes.lyrics || lyrics;
      setLyrics(finalLyrics);

      // 4. Analyze & Align
      await onGenerateMusic({
        bpm: parseFloat(estBpm),
        duration_sec: parseFloat(estDur),
        prompt: finalPrompt,
        lyrics: finalLyrics,
        is_instrumental: isInstrumental
      });
      setStatusNote('Full music pipeline complete!');
      setTimeout(() => setStatusNote(null), 4000);
    } catch (err) {
      alert('Auto-generation failed: ' + err.message);
    } finally {
      setIsSynthesizing(false);
    }
  };

  // Handle Daily Threshold Slider Change
  const handleDailyThresholdChange = (dayNumber, val) => {
    const updated = { ...dailyThresholds, [String(dayNumber)]: parseFloat(val) };
    setDailyThresholds(updated);
    // Debounced or direct re-analyze
    handleAnalyzeTimeline(pacingPreset, updated);
  };

  const handlePacingPresetChange = (preset) => {
    setPacingPreset(preset);
    handleAnalyzeTimeline(preset, dailyThresholds);
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
    const textToCopy = lyrics || audioTrack?.lyrics || '';
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
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

  const dailyStats = timelineEstimate?.daily_stats || [];
  const acts = timelineEstimate?.acts || [];
  const isBusy = isGenerating || isAnalyzing || isGeneratingPrompt || isGeneratingLyrics || isSynthesizing || isUploadingAudio;

  return (
    <div className="glass-panel rounded-2xl p-4 border border-slate-800 h-full flex flex-col overflow-hidden">
      {/* Header & Quick Action */}
      <div className="flex items-center justify-between mb-2.5 pb-2 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center shrink-0">
            <Disc3 className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-white uppercase tracking-wider truncate">
              Music Studio
            </h2>
            <p className="text-[9px] text-slate-400 truncate font-mono">
              Demucs Stem Sync & Google Flow Prompts
            </p>
          </div>
        </div>

        <button
          onClick={handleAutoGenerateAll}
          disabled={isBusy}
          className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 disabled:opacity-50 text-slate-950 font-bold px-3 py-1 rounded-lg text-[11px] transition shadow-md shadow-teal-500/20 shrink-0"
          title="Executes all 4 phases: Analyze, Prompt, Lyrics, Audio"
        >
          <Zap className={`w-3 h-3 fill-current ${isBusy ? 'animate-pulse' : ''}`} />
          <span>{isBusy ? 'Processing...' : 'Auto-Generate All'}</span>
        </button>
      </div>

      {/* Feedback Banner */}
      {statusNote && (
        <div className="mb-2 bg-teal-500/10 border border-teal-500/30 text-teal-300 text-[10px] px-2.5 py-1 rounded-lg flex items-center gap-1.5 shrink-0">
          <Sparkles className="w-3 h-3 text-teal-400 shrink-0 animate-spin" />
          <span className="truncate">{statusNote}</span>
        </div>
      )}

      {/* Phase Navigation Tabs */}
      <div className="grid grid-cols-4 gap-1 mb-2.5 shrink-0">
        <button
          onClick={() => setActiveSectionTab('pacing')}
          className={`py-1 px-1.5 rounded-lg text-[10px] font-bold flex items-center justify-center gap-1 transition ${
            activeSectionTab === 'pacing'
              ? 'bg-slate-800 text-teal-300 border border-teal-500/40 shadow'
              : 'bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800/80'
          }`}
        >
          <Sliders className="w-3 h-3" />
          <span>1. Pacing</span>
        </button>
        <button
          onClick={() => setActiveSectionTab('prompt')}
          className={`py-1 px-1.5 rounded-lg text-[10px] font-bold flex items-center justify-center gap-1 transition ${
            activeSectionTab === 'prompt'
              ? 'bg-slate-800 text-cyan-300 border border-cyan-500/40 shadow'
              : 'bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800/80'
          }`}
        >
          <Sparkles className="w-3 h-3" />
          <span>2. Style</span>
        </button>
        <button
          onClick={() => setActiveSectionTab('lyrics')}
          className={`py-1 px-1.5 rounded-lg text-[10px] font-bold flex items-center justify-center gap-1 transition ${
            activeSectionTab === 'lyrics'
              ? 'bg-slate-800 text-purple-300 border border-purple-500/40 shadow'
              : 'bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800/80'
          }`}
        >
          <Mic className="w-3 h-3" />
          <span>{isInstrumental ? '3. Narration' : '3. Lyrics'}</span>
        </button>
        <button
          onClick={() => setActiveSectionTab('audio')}
          className={`py-1 px-1.5 rounded-lg text-[10px] font-bold flex items-center justify-center gap-1 transition ${
            activeSectionTab === 'audio'
              ? 'bg-slate-800 text-emerald-300 border border-emerald-500/40 shadow'
              : 'bg-slate-950/60 text-slate-400 hover:text-slate-200 border border-slate-800/80'
          }`}
        >
          <Music className="w-3 h-3" />
          <span>4. Audio</span>
        </button>
      </div>

      {/* Scrollable Content Body */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-3">
        {/* ========================================================================= */}
        {/* TAB 1: MEDIA PACING & DAILY INCLUSION THRESHOLDS */}
        {/* ========================================================================= */}
        {activeSectionTab === 'pacing' && (
          <div className="space-y-2.5">
            {/* Pacing Preset Selector & Duration Summary */}
            <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                  <Sliders className="w-3 h-3 text-teal-400" />
                  Media Pacing Preset
                </span>
                <div className="flex items-center gap-1.5 bg-slate-900 px-2 py-0.5 rounded-md border border-slate-700">
                  <Clock className="w-3 h-3 text-teal-400" />
                  <span className="text-[10px] font-mono font-bold text-teal-300">
                    {duration.toFixed(1)}s Song
                  </span>
                </div>
              </div>

              {/* Pacing Preset Buttons */}
              <div className="grid grid-cols-3 gap-1">
                {[
                  { id: 'fast', label: 'Fast', pace: '1.5s/photo' },
                  { id: 'balanced', label: 'Balanced', pace: '2.5s/photo' },
                  { id: 'cinematic', label: 'Cinematic', pace: '4.0s/photo' }
                ].map((p) => (
                  <button
                    key={p.id}
                    onClick={() => handlePacingPresetChange(p.id)}
                    className={`py-1 px-1.5 rounded text-left transition flex flex-col ${
                      pacingPreset === p.id
                        ? 'bg-teal-500/20 text-teal-300 border border-teal-500/50'
                        : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                    }`}
                  >
                    <span className="text-[10px] font-bold">{p.label}</span>
                    <span className="text-[8px] font-mono text-slate-500">{p.pace}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Daily Media Inclusion Sliders */}
            <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                  <Calendar className="w-3 h-3 text-cyan-400" />
                  Daily Media Inclusion
                </span>
                <button
                  onClick={() => handleAnalyzeTimeline()}
                  disabled={isBusy}
                  className="flex items-center gap-1 text-[9px] bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 px-2 py-0.5 rounded font-semibold transition"
                  title="Recalculate timeline from daily inclusion sliders"
                >
                  <RotateCw className={`w-2.5 h-2.5 ${isAnalyzing ? 'animate-spin' : ''}`} />
                  <span>{isAnalyzing ? 'Calculating...' : '1. Recalculate'}</span>
                </button>
              </div>

              {dailyStats.length === 0 ? (
                <p className="text-[10px] text-slate-500 italic p-2 bg-slate-900/50 rounded">
                  Import media files and travel diary to configure daily inclusion.
                </p>
              ) : (
                <div className="space-y-2">
                  {dailyStats.map((d) => {
                    const dNum = d.day_number;
                    const curThresh = dailyThresholds[String(dNum)] !== undefined
                      ? dailyThresholds[String(dNum)]
                      : d.threshold_percent;

                    return (
                      <div
                        key={dNum}
                        className="bg-slate-900/80 p-2 rounded-lg border border-slate-800 space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-[10px]">
                          <div className="flex items-center gap-1 min-w-0">
                            <span className="font-bold text-slate-200 truncate">
                              Day {dNum}: {d.title || `Day ${dNum}`}
                            </span>
                            {d.date && (
                              <span className="text-[8px] font-mono text-slate-500">
                                ({d.date})
                              </span>
                            )}
                          </div>
                          <span className="text-[9px] font-mono bg-teal-500/10 text-teal-300 px-1.5 py-0.2 rounded border border-teal-500/20 font-bold shrink-0">
                            {d.section_duration_sec}s
                          </span>
                        </div>

                        {/* Slider */}
                        <div className="space-y-0.5">
                          <div className="flex justify-between text-[9px] text-slate-400 font-mono">
                            <span>Top {Math.round(curThresh)}% Media</span>
                            <span className="text-cyan-300 font-semibold">
                              {d.included_media_count} of {d.total_media_count} clips
                            </span>
                          </div>
                          <input
                            type="range"
                            min={10}
                            max={100}
                            step={5}
                            value={curThresh}
                            onChange={(e) => handleDailyThresholdChange(dNum, e.target.value)}
                            className="w-full accent-teal-500 h-1.5"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Musical Buffers Indicator */}
              <div className="p-1.5 rounded bg-slate-900/60 border border-slate-800 text-[9px] font-mono text-slate-400 flex items-center justify-between">
                <span>Buffers: Intro (4.0s) + Chorus (7.5s) + Outro (4.5s)</span>
                <span className="text-purple-300 font-bold">+16.0s</span>
              </div>
            </div>

            {/* Song Duration & Tempo (BPM) */}
            <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-2">
              <div className="flex justify-between items-center text-[10px] text-slate-300">
                <span className="font-bold uppercase tracking-wider">Song Tempo (BPM)</span>
                <span className="font-mono text-teal-400 font-bold">{bpm} BPM</span>
              </div>
              <input
                type="range"
                min={80}
                max={160}
                step={1}
                value={bpm}
                onChange={(e) => setBpm(parseFloat(e.target.value))}
                className="w-full accent-teal-500"
              />

              <div className="flex items-center justify-between pt-1 text-[10px]">
                <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={manualDurationOverride}
                    onChange={(e) => setManualDurationOverride(e.target.checked)}
                    className="rounded border-slate-700 text-teal-500 w-3 h-3"
                  />
                  <span>Manual duration override</span>
                </label>
                {manualDurationOverride && (
                  <input
                    type="number"
                    min={10}
                    max={120}
                    value={duration}
                    onChange={(e) => setDuration(parseFloat(e.target.value) || 30)}
                    className="w-16 bg-slate-900 border border-slate-700 rounded px-1 text-right text-teal-300 font-mono font-bold text-[10px]"
                  />
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: GOOGLE FLOW MUSIC PROMPT & TIMELINE BREAKDOWN */}
        {/* ========================================================================= */}
        {activeSectionTab === 'prompt' && (
          <div className="space-y-2.5">
            {/* Style Vibe & Genre Tags */}
            <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-1.5">
              <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
                <span>Music Style / Vibe</span>
                <span className="text-[9px] text-slate-500 font-normal">Optional genre guide</span>
              </label>
              <input
                type="text"
                value={styleVibe}
                onChange={(e) => setStyleVibe(e.target.value)}
                placeholder="e.g. Uplifting Indie Folk Acoustic, Warm Cinematic Lo-Fi..."
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
              />
              <div className="flex flex-wrap gap-1 pt-1">
                {['Acoustic Indie Folk', 'Warm Lo-Fi Beats', 'Cinematic Pop', 'Upbeat Travel Rock'].map((vibe) => (
                  <button
                    key={vibe}
                    onClick={() => setStyleVibe(vibe)}
                    className="text-[8px] bg-slate-900 hover:bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-800 transition"
                  >
                    {vibe}
                  </button>
                ))}
              </div>
            </div>

            {/* Prompt Box */}
            <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-cyan-400" />
                  Google Flow Music Prompt
                </label>
                <div className="flex items-center gap-1.5">
                  {(prompt || audioTrack?.prompt) && (
                    <button
                      onClick={handleCopyPrompt}
                      className="flex items-center gap-1 text-[9px] text-cyan-400 hover:text-cyan-300 font-semibold"
                    >
                      {copiedPrompt ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5" />}
                      <span>{copiedPrompt ? 'Copied' : 'Copy'}</span>
                    </button>
                  )}
                  <button
                    onClick={handleGeneratePrompt}
                    disabled={isBusy}
                    className="flex items-center gap-1 bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-slate-950 font-bold px-2 py-0.5 rounded text-[9px] transition shadow-sm"
                  >
                    <RotateCw className={`w-2.5 h-2.5 ${isGeneratingPrompt ? 'animate-spin' : ''}`} />
                    <span>{isGeneratingPrompt ? 'Generating...' : '2. Generate Prompt'}</span>
                  </button>
                </div>
              </div>

              <textarea
                rows={3}
                value={prompt || audioTrack?.prompt || ''}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Google Flow Music optimized prompt with section cues and duration hints..."
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-[11px] text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono leading-relaxed"
              />
            </div>

            {/* Section Timing Visualization Pills */}
            {acts.length > 0 && (
              <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-1.5">
                <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block">
                  Calculated Section Timeline
                </span>
                <div className="space-y-1">
                  {acts.map((act, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between bg-slate-900/80 p-1.5 rounded border border-slate-800 text-[9px] font-mono"
                    >
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300 font-bold">
                          {Math.floor(act.start_sec / 60)}:{String(Math.floor(act.start_sec % 60)).padStart(2, '0')} - {Math.floor(act.end_sec / 60)}:{String(Math.floor(act.end_sec % 60)).padStart(2, '0')}
                        </span>
                        <span className="text-slate-200 font-semibold truncate">
                          [{act.act_type}] {act.title}
                        </span>
                      </div>
                      <span className={`px-1 py-0.2 rounded font-bold ${act.is_instrumental ? 'bg-purple-500/20 text-purple-300' : 'bg-teal-500/20 text-teal-300'}`}>
                        {act.duration_sec}s {act.is_instrumental ? '• Instr' : '• Singing'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: STRUCTURED RHYMING LYRICS / TIMED STORY SUBTITLES */}
        {/* ========================================================================= */}
        {activeSectionTab === 'lyrics' && (
          <div className="space-y-2.5">
            <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                    {isInstrumental ? 'Story Subtitles & Narration' : 'Structured Rhyming Lyrics'}
                  </span>
                  <label className="flex items-center gap-1 text-[10px] text-slate-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isInstrumental}
                      onChange={(e) => setIsInstrumental(e.target.checked)}
                      className="rounded border-slate-700 text-teal-500 w-3 h-3"
                    />
                    <span>Instrumental</span>
                  </label>
                </div>

                <div className="flex items-center gap-1.5">
                  {audioTrack && onOpenLyricEditor && (
                    <button
                      onClick={onOpenLyricEditor}
                      className="flex items-center gap-1 text-[10px] bg-teal-500/20 hover:bg-teal-500/30 text-teal-300 border border-teal-500/40 px-2 py-0.5 rounded font-semibold transition"
                      title="Open in-browser interactive lyric & timestamp editor"
                    >
                      <Edit3 className="w-2.5 h-2.5" />
                      <span>Edit Timings</span>
                    </button>
                  )}

                  {(lyrics || audioTrack?.lyrics) && (
                    <button
                      onClick={handleCopyLyrics}
                      className="flex items-center gap-1 text-[9px] text-purple-400 hover:text-purple-300 font-semibold"
                    >
                      {copiedLyrics ? <Check className="w-2.5 h-2.5 text-emerald-400" /> : <Copy className="w-2.5 h-2.5" />}
                      <span>{copiedLyrics ? 'Copied' : 'Copy'}</span>
                    </button>
                  )}
                  <button
                    onClick={handleGenerateLyrics}
                    disabled={isBusy}
                    className="flex items-center gap-1 bg-purple-500 hover:bg-purple-400 disabled:opacity-50 text-slate-950 font-bold px-2 py-0.5 rounded text-[9px] transition shadow-sm"
                  >
                    <RotateCw className={`w-2.5 h-2.5 ${isGeneratingLyrics ? 'animate-spin' : ''}`} />
                    <span>{isGeneratingLyrics ? 'Generating...' : (isInstrumental ? '3. Generate Subtitles' : '3. Generate Lyrics')}</span>
                  </button>
                </div>
              </div>

              {isInstrumental && (
                <div className="p-1 rounded bg-purple-950/30 border border-purple-800/40 text-[9px] text-purple-300 font-mono flex items-center justify-between">
                  <span>🗣️ Spoken Voiceover Narration</span>
                  <span className="font-semibold">~2.2 words/sec normal speaking pace</span>
                </div>
              )}

              {/* Editable Lyrics / Subtitles Area */}
              <textarea
                rows={5}
                value={lyrics || audioTrack?.lyrics || ''}
                onChange={(e) => setLyrics(e.target.value)}
                placeholder={
                  isInstrumental
                    ? "[0:00-0:04] [Intro] (4s)\nOur journey begins as morning light breaks across the horizon...\n\n[0:04-0:15] [Verse 1: Day 1] (11s)\nWalking through the cobblestone streets, the sunlight reflects on historic facades as we explore the quaint cafes..."
                    : "[0:00-0:04] [Intro] (4s)\n[Instrumental - Gentle acoustic guitar strumming]\n\n[0:04-0:15] [Verse 1: Day 1] (11s)\nStepping out into the golden morning light\nCobblestone streets stretching out of sight..."
                }
                className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2 text-[10px] text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 font-mono leading-relaxed"
              />
            </div>

            {/* Formatted Preview Box */}
            <div className="bg-slate-950/70 p-2.5 rounded-xl border border-slate-800/80 space-y-1.5">
              <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block">
                {isInstrumental ? 'Timed Story Subtitle Preview' : 'Lyric Timing Card Preview'}
              </span>
              <div className="max-h-36 overflow-y-auto font-mono text-[10px] text-slate-300 bg-slate-900/90 rounded-lg p-2 border border-slate-800 space-y-1.5">
                {(lyrics || audioTrack?.lyrics) ? (
                  (lyrics || audioTrack.lyrics).split('\n\n').map((block, i) => (
                    <div key={i} className="pb-1.5 border-b border-slate-800/60 last:border-0">
                      {block.split('\n').map((line, j) => (
                        <p
                          key={j}
                          className={
                            line.startsWith('[')
                              ? 'text-teal-400 font-bold text-[9px] uppercase tracking-wide'
                              : 'text-slate-200 pl-1'
                          }
                        >
                          {line}
                        </p>
                      ))}
                    </div>
                  ))
                ) : (
                  <p className="text-slate-500 italic text-center py-2">
                    Click '3. Generate Lyrics' to generate rhyming lines matching daily media timing.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 4: AUDIO SYNTHESIS & STEM PLAYER */}
        {/* ========================================================================= */}
        {activeSectionTab === 'audio' && (
          <div className="space-y-2.5">
            {/* Audio Stems Controls */}
            <div className="bg-slate-950/70 rounded-xl p-2.5 border border-slate-800/80 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
                  Audio Stems (Demucs)
                </span>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isBusy}
                    className="flex items-center gap-1 text-[9px] bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 px-2 py-0.5 rounded font-semibold transition"
                  >
                    <Upload className="w-2.5 h-2.5" />
                    <span>Upload Audio</span>
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="audio/*,.wav,.mp3,.flac,.m4a"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                  <button
                    onClick={handleSynthesizeAudio}
                    disabled={isBusy}
                    className="flex items-center gap-1 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-bold px-2.5 py-0.5 rounded text-[9px] transition shadow-sm"
                  >
                    <RotateCw className={`w-2.5 h-2.5 ${isSynthesizing ? 'animate-spin' : ''}`} />
                    <span>{isSynthesizing ? 'Analyzing & Aligning...' : '4. Analyze & Align'}</span>
                  </button>
                </div>
              </div>

              {/* Stem Selectors */}
              <div className="grid grid-cols-3 gap-1">
                <button
                  onClick={() => setActiveStem('master')}
                  className={`py-1 rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition ${
                    activeStem === 'master'
                      ? 'bg-teal-500 text-slate-950 shadow font-bold'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  <Music className="w-2.5 h-2.5" /> Master
                </button>
                <button
                  onClick={() => setActiveStem('vocals')}
                  className={`py-1 rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition ${
                    activeStem === 'vocals'
                      ? 'bg-teal-500 text-slate-950 shadow font-bold'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  <Mic className="w-2.5 h-2.5" /> Vocals
                </button>
                <button
                  onClick={() => setActiveStem('accompaniment')}
                  className={`py-1 rounded text-[10px] font-semibold flex items-center justify-center gap-1 transition ${
                    activeStem === 'accompaniment'
                      ? 'bg-teal-500 text-slate-950 shadow font-bold'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  <Disc3 className="w-2.5 h-2.5" /> Backing
                </button>
              </div>

              {/* Player */}
              {audioTrack ? (
                <div className="bg-slate-900 rounded-lg p-2 border border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between text-[10px] text-slate-300 font-mono">
                    <span>Stem: <strong className="text-teal-300 uppercase">{activeStem}</strong></span>
                    <span>{audioTrack.bpm} BPM</span>
                  </div>
                  <audio
                    controls
                    className="w-full h-8"
                    src={`http://localhost:8000/api/projects/${project?.id}/audio/${activeStem}`}
                  />
                </div>
              ) : (
                <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-800 text-center text-[10px] text-slate-500">
                  No audio analyzed or uploaded yet. Click '4. Analyze & Align' or 'Upload Audio'.
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
