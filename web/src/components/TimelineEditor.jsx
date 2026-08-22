import React, { useState, useRef, useMemo } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  ZoomIn,
  ZoomOut,
  Film,
  Scissors,
  ArrowLeft,
  ArrowRight,
  Volume2,
  VolumeX,
  Music,
  Tag,
  Type,
  Layers,
  Edit3
} from 'lucide-react';
import TimelineControlDeck from './TimelineControlDeck';

export default function TimelineEditor({
  project,
  audioTrack,
  slices = [],
  currentTime = 0,
  isPlaying = false,
  onTogglePlay,
  onSeek,
  onOpenSwapModal,
  onUpdateSliceBeatCount,
  onSplitSlice,
  onReorderSlices,
  onSolveTimeline,
  onRenderVideo,
  onUpdateControls,
  onBulkApply,
  onUpdateSliceCaption,
  onUpdateSliceAudio,
  onOpenLyricEditor,
  isSolving,
  isRendering
}) {
  const [zoom, setZoom] = useState(60);
  const timelineRef = useRef(null);

  const config = project?.config_override || {};
  const tOverlays = config.text_overlays || {};
  const lStyle = config.lyrics_style || {};
  const rawSubMode = lStyle.subtitle_mode;
  const subtitleMode = (rawSubMode && rawSubMode !== 'auto')
    ? rawSubMode
    : 'karaoke_lyrics';

  const totalDuration = audioTrack?.beat_grid?.length
    ? (audioTrack.beat_grid[audioTrack.beat_grid.length - 1] || 30.0) + 1.0
    : 30.0;

  const totalWidth = totalDuration * zoom;

  // Generate deterministic musical waveform heights for master music track visualizer
  const waveformBars = useMemo(() => {
    const barCount = Math.max(120, Math.floor(totalDuration * 8));
    const bars = [];
    for (let i = 0; i < barCount; i++) {
      const t = (i / barCount) * totalDuration;
      // Simulated dynamic amplitude envelope based on BPM and musical phrases
      const baseAmp = 0.35 + 0.35 * Math.sin(i * 0.28) * Math.cos(i * 0.12);
      const beatPulse = (i % 4 === 0) ? 0.3 : 0.1;
      const height = Math.min(100, Math.max(15, Math.floor((baseAmp + beatPulse) * 85)));
      bars.push({ time: t, height });
    }
    return bars;
  }, [totalDuration]);

  const handleTimelineClick = (e) => {
    if (!timelineRef.current || !onSeek) return;
    const rect = timelineRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left + timelineRef.current.scrollLeft;
    const seekTime = Math.max(0, Math.min(totalDuration, clickX / zoom));
    onSeek(seekTime);
  };

  // Split slice at playhead
  const handleSplitAtPlayhead = () => {
    if (!slices.length) return;
    const active = slices.find(
      (s) => currentTime >= s.timeline_start_sec && currentTime < s.timeline_end_sec
    );
    if (!active) return;

    // Calculate nearest beat
    const beatGrid = audioTrack?.beat_grid || [];
    const beatIdx = beatGrid.findIndex((b) => Math.abs(b - currentTime) <= 0.35);
    if (beatIdx > active.start_beat && beatIdx < active.start_beat + active.beat_count) {
      onSplitSlice(active.id, beatIdx);
    } else {
      alert('Playhead must be inside the slice and aligned near a musical beat to split.');
    }
  };

  // Move slice left/right
  const handleMoveSlice = (idx, direction) => {
    const targetIdx = idx + direction;
    if (targetIdx < 0 || targetIdx >= slices.length) return;
    const newOrder = [...slices];
    const temp = newOrder[idx];
    newOrder[idx] = newOrder[targetIdx];
    newOrder[targetIdx] = temp;
    onReorderSlices(newOrder.map((s) => s.id));
  };

  const aspect = config?.video?.aspect_ratio || '16:9';

  return (
    <div className="glass-panel rounded-2xl p-3.5 border border-slate-800 h-full flex flex-col overflow-hidden">
      {/* Control & Status Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 mb-2.5 pb-2 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={onTogglePlay}
              disabled={!audioTrack}
              className="w-8 h-8 rounded-lg bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 flex items-center justify-center font-bold shadow-md shadow-teal-500/20 transition shrink-0"
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
            </button>
            <div className="font-mono text-xs">
              <span className="text-teal-400 font-bold">{currentTime.toFixed(2)}s</span>
              <span className="text-slate-500"> / {totalDuration.toFixed(2)}s</span>
            </div>
          </div>

          <div className="h-4 w-px bg-slate-800 hidden sm:block" />

          {/* Quick Layer Metrics */}
          <div className="hidden md:flex items-center gap-2 font-mono text-[10px]">
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
              {audioTrack?.bpm || 120} BPM
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-300">
              {slices.length} Media Cuts
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-amber-300 font-semibold">
              5 Timeline Layers
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-white">
              {aspect}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleSplitAtPlayhead}
            className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-2.5 py-1 rounded-lg text-xs font-semibold transition"
            title="Split active slice at playhead"
          >
            <Scissors className="w-3 h-3 text-cyan-400" />
            <span>Split Cut</span>
          </button>

          <button
            onClick={onSolveTimeline}
            disabled={isSolving || !audioTrack}
            className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 border border-slate-700 px-2.5 py-1 rounded-lg text-xs font-semibold transition"
            title="Auto-match diary themes and music beats"
          >
            <RotateCcw className="w-3 h-3 text-teal-400" />
            <span>{isSolving ? 'Solving...' : 'Auto-Solve'}</span>
          </button>

          <div className="flex items-center gap-1 bg-slate-950 border border-slate-800 rounded px-1 py-0.5">
            <button onClick={() => setZoom((z) => Math.max(30, z - 15))} className="p-0.5 hover:text-white text-slate-400">
              <ZoomOut className="w-3 h-3" />
            </button>
            <span className="text-[10px] px-1 font-mono text-slate-400">{zoom}px/s</span>
            <button onClick={() => setZoom((z) => Math.min(150, z + 15))} className="p-0.5 hover:text-white text-slate-400">
              <ZoomIn className="w-3 h-3" />
            </button>
          </div>

          <button
            onClick={onRenderVideo}
            disabled={isRendering || slices.length === 0}
            className="flex items-center gap-1.5 bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 disabled:opacity-50 text-slate-950 px-3.5 py-1 rounded-lg text-xs font-bold transition shadow-md shadow-teal-500/20"
          >
            <Film className="w-3.5 h-3.5" />
            <span>{isRendering ? 'Rendering...' : 'Export MP4'}</span>
          </button>
        </div>
      </div>

      {/* Multi-Track Timeline with Fixed Left Headers & Scrollable Right Canvas */}
      <div className="flex-1 overflow-hidden flex flex-col min-h-0">
        <div className="flex flex-1 min-h-0 rounded-xl bg-slate-950/95 border border-slate-800 overflow-hidden shadow-inner">
          {/* Fixed Left Track Headers */}
          <div className="w-36 sm:w-44 bg-slate-950 border-r border-slate-800/90 flex flex-col shrink-0 select-none z-10 text-[10px] font-semibold text-slate-400">
            {/* Beat Ruler Header */}
            <div className="h-6 px-2.5 flex items-center gap-1.5 bg-slate-900/90 border-b border-slate-800/80 font-mono text-[9px] text-teal-400">
              <span>⏱️ Ruler / Bars</span>
            </div>

            {/* Layer 5: Titles & Overlays Header */}
            <div className="h-8 px-2.5 flex items-center justify-between border-b border-slate-800/70 bg-slate-900/40">
              <span className="flex items-center gap-1 text-teal-300 font-bold">
                <Tag className="w-3 h-3 text-teal-400" /> Titles & Overlays
              </span>
            </div>

            {/* Layer 4: Subtitles & Lyrics Header */}
            <div className="h-9 px-2.5 flex items-center justify-between border-b border-slate-800/70 bg-slate-900/30">
              <span className="flex items-center gap-1 text-cyan-300 font-bold truncate">
                <Type className="w-3 h-3 text-cyan-400 shrink-0" />
                <span className="truncate">
                  {subtitleMode === 'narrative_descriptions'
                    ? 'Narrative Captions'
                    : subtitleMode === 'chapter_event_cards'
                    ? 'Chapter Cards'
                    : subtitleMode === 'hidden'
                    ? 'Subs (Off)'
                    : 'Karaoke Lyrics'}
                </span>
              </span>

              {audioTrack && onOpenLyricEditor && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenLyricEditor();
                  }}
                  className="flex items-center gap-0.5 text-[9px] bg-slate-800 hover:bg-slate-700 text-teal-300 px-1.5 py-0.5 rounded border border-slate-700 font-semibold transition"
                  title="Open interactive lyric & timestamp editor"
                >
                  <Edit3 className="w-2.5 h-2.5" />
                  <span>Edit</span>
                </button>
              )}
            </div>

            {/* Layer 3: Video & Photo Media Header */}
            <div className="h-28 px-2.5 flex flex-col justify-between py-2 border-b border-slate-800/80 bg-slate-900/20">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 text-white font-bold">
                  <Film className="w-3.5 h-3.5 text-teal-400" /> Video & Photos
                </span>
                <span className="text-[9px] font-mono text-slate-400">{slices.length} Cuts</span>
              </div>
              <p className="text-[8px] text-slate-400 leading-tight">
                Visual cuts timed to musical beat grid.
              </p>
            </div>

            {/* Layer 2: Video Audio Header */}
            <div className="h-9 px-2.5 flex items-center justify-between border-b border-slate-800/80 bg-slate-900/40">
              <span className="flex items-center gap-1 text-amber-300 font-bold">
                <Volume2 className="w-3 h-3 text-amber-400" /> Clip Audio
              </span>
              <span className="text-[8px] px-1 py-0.2 rounded bg-slate-800 text-slate-400">Default Muted</span>
            </div>

            {/* Layer 1: Master Music & Waveform Header */}
            <div className="h-12 px-2.5 flex flex-col justify-center bg-slate-900/70">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 text-teal-300 font-bold">
                  <Music className="w-3.5 h-3.5 text-teal-400" /> Master Music
                </span>
                <span className="text-[9px] font-mono text-teal-400 font-bold">{audioTrack?.bpm || 120} BPM</span>
              </div>
              <span className="text-[8px] text-slate-400 font-mono">EBU R128 Mastered Waveform</span>
            </div>
          </div>

          {/* Scrollable Multi-Track Lanes & Playhead */}
          <div
            ref={timelineRef}
            onClick={handleTimelineClick}
            className="flex-1 overflow-x-auto overflow-y-hidden relative bg-slate-950/80 cursor-pointer select-none"
          >
            <div style={{ width: `${Math.max(totalWidth, 800)}px` }} className="relative h-full flex flex-col">
              {/* Global Playhead Marker (Runs across all 5 layers) */}
              <div
                className="absolute top-0 bottom-0 z-40 w-0.5 bg-cyan-400 pointer-events-none"
                style={{ left: `${currentTime * zoom}px` }}
              >
                <div className="w-3 h-3 -ml-1.5 bg-cyan-400 rotate-45 transform shadow-lg shadow-cyan-400/60" />
              </div>

              {/* RULER / BEAT GRID BAR */}
              <div className="h-6 border-b border-slate-800/80 bg-slate-900/90 relative font-mono text-[9px] shrink-0">
                {audioTrack?.beat_grid?.map((beatTime, idx) => {
                  const isDownbeat = idx % 4 === 0;
                  return (
                    <div
                      key={idx}
                      className={`absolute top-0 bottom-0 flex flex-col justify-between ${
                        isDownbeat ? 'border-l-2 border-teal-500/50 text-teal-400 font-bold' : 'border-l border-slate-800 text-slate-600'
                      }`}
                      style={{ left: `${beatTime * zoom}px` }}
                    >
                      <span className="pl-1 pt-0.5">{isDownbeat ? `Bar ${idx / 4 + 1}` : `b${idx + 1}`}</span>
                    </div>
                  );
                })}
              </div>

              {/* LAYER 5: TITLES & OVERLAYS TRACK */}
              <div className="h-8 border-b border-slate-800/70 bg-slate-900/30 relative flex items-center shrink-0">
                {/* Intro Title Block */}
                {tOverlays.intro_enabled && (
                  <div
                    className="absolute h-5.5 rounded-lg px-2 flex items-center gap-1 bg-gradient-to-r from-teal-600/80 to-cyan-600/80 border border-teal-400/60 text-slate-950 font-bold text-[9px] shadow-sm z-10 truncate"
                    style={{ left: '0px', width: `${Math.max(80, (tOverlays.intro_duration || 3.5) * zoom)}px` }}
                    title={`Intro Title Card: "${tOverlays.intro_title || project?.title || 'Title'}"`}
                  >
                    <Tag className="w-2.5 h-2.5 text-slate-950 shrink-0" />
                    <span className="truncate">{tOverlays.intro_title || project?.title || 'Intro Title'}</span>
                  </div>
                )}

                {/* Creator Watermark Span Indicator */}
                {tOverlays.watermark_text && (
                  <div
                    className="absolute h-4.5 rounded-md px-1.5 flex items-center gap-1 bg-slate-800/70 border border-cyan-500/30 text-cyan-300 font-mono text-[8px] z-0"
                    style={{ left: `${(tOverlays.intro_duration || 3.5) * zoom + 10}px`, right: '100px' }}
                  >
                    <span>Watermark: {tOverlays.watermark_text}</span>
                  </div>
                )}

                {/* Outro End Card Block */}
                {tOverlays.outro_text && totalDuration > 4.0 && (
                  <div
                    className="absolute h-5.5 rounded-lg px-2 flex items-center gap-1 bg-gradient-to-r from-cyan-600/80 to-teal-600/80 border border-cyan-400/60 text-slate-950 font-bold text-[9px] shadow-sm z-10 truncate"
                    style={{
                      left: `${Math.max(0, totalDuration - 3.0) * zoom}px`,
                      width: `${3.0 * zoom}px`
                    }}
                    title={`Outro End Card: "${tOverlays.outro_text}"`}
                  >
                    <span className="truncate">Outro: {tOverlays.outro_text}</span>
                  </div>
                )}
              </div>

              {/* LAYER 4: SUBTITLES & LYRICS TRACK (STRICT SINGLE TYPE - ZERO OVERLAP) */}
              <div className="h-9 border-b border-slate-800/70 bg-slate-900/20 relative flex items-center shrink-0">
                {subtitleMode === 'hidden' ? (
                  <div className="px-3 text-[9px] text-slate-600 italic">
                    🚫 Subtitles Off (Clean video presentation active)
                  </div>
                ) : subtitleMode === 'narrative_descriptions' ? (
                  /* Narrative Scene Description Blocks */
                  slices.map((slice, idx) => {
                    const sLeft = slice.timeline_start_sec * zoom;
                    const sWidth = Math.max(40, (slice.timeline_end_sec - slice.timeline_start_sec) * zoom);
                    const isActive = currentTime >= slice.timeline_start_sec && currentTime < slice.timeline_end_sec;
                    const caption = slice.custom_caption || slice.asset?.caption || `Scene #${idx + 1}`;

                    return (
                      <div
                        key={slice.id}
                        className={`absolute h-6 rounded-md px-1.5 flex items-center gap-1 border text-[9px] font-medium transition-all ${
                          isActive
                            ? 'bg-cyan-500 text-slate-950 border-cyan-300 font-bold shadow-md z-20 scale-[1.02]'
                            : 'bg-slate-900/90 text-cyan-200 border-slate-800 hover:border-cyan-500/40'
                        }`}
                        style={{ left: `${sLeft}px`, width: `${sWidth}px` }}
                        title={`Scene #${idx + 1} Narration: ${caption}`}
                      >
                        <span className="shrink-0 font-bold">📖 #{idx + 1}:</span>
                        <span className="truncate">{caption}</span>
                      </div>
                    );
                  })
                ) : subtitleMode === 'chapter_event_cards' ? (
                  /* Chapter Event Cards */
                  slices.map((slice, idx) => {
                    const sLeft = slice.timeline_start_sec * zoom;
                    const sWidth = Math.max(40, (slice.timeline_end_sec - slice.timeline_start_sec) * zoom);
                    const isActive = currentTime >= slice.timeline_start_sec && currentTime < slice.timeline_end_sec;
                    return (
                      <div
                        key={slice.id}
                        className={`absolute h-6 rounded-md px-1.5 flex items-center gap-1 border text-[9px] font-bold ${
                          isActive
                            ? 'bg-amber-400 text-slate-950 border-amber-300 shadow-md z-20'
                            : 'bg-slate-900 text-slate-300 border-slate-800'
                        }`}
                        style={{ left: `${sLeft}px`, width: `${sWidth}px` }}
                      >
                        <span className="truncate">🏷️ ACT #{idx + 1}</span>
                      </div>
                    );
                  })
                ) : (
                  /* Synced Karaoke Lyrics Word Tokens */
                  audioTrack?.aligned_lyrics?.map((wordObj, idx) => {
                    const wLeft = wordObj.snapped_start * zoom;
                    const wWidth = Math.max(20, (wordObj.snapped_end - wordObj.snapped_start) * zoom);
                    const isActive = currentTime >= wordObj.snapped_start && currentTime <= wordObj.snapped_end;

                    return (
                      <div
                        key={idx}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (onSeek) onSeek(wordObj.snapped_start);
                        }}
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          if (onOpenLyricEditor) onOpenLyricEditor();
                        }}
                        className={`absolute h-5 rounded px-1 flex items-center justify-center text-[10px] font-semibold transition-all cursor-pointer group ${
                          isActive
                            ? 'bg-teal-500 text-slate-950 scale-105 shadow-md z-20 font-bold'
                            : 'bg-slate-800/90 text-slate-200 border border-slate-700/60 hover:border-teal-400 hover:text-white'
                        }`}
                        style={{ left: `${wLeft}px`, width: `${wWidth}px` }}
                        title={`"${wordObj.word}" (${wordObj.start}s – ${wordObj.end}s) • Click to seek, Double-click to edit`}
                      >
                        <span className="truncate">{wordObj.word}</span>
                      </div>
                    );
                  })
                )}
              </div>

              {/* LAYER 3: VIDEO & PHOTO MEDIA TRACK */}
              <div className="h-28 relative bg-slate-950/40 p-1.5 border-b border-slate-800/80">
                {slices.map((slice, idx) => {
                  const sliceLeft = slice.timeline_start_sec * zoom;
                  const sliceWidth = Math.max(50, (slice.timeline_end_sec - slice.timeline_start_sec) * zoom);
                  const isCurrent = currentTime >= slice.timeline_start_sec && currentTime < slice.timeline_end_sec;
                  const asset = slice.asset;
                  const isVideo = asset?.media_type === 'video';

                  return (
                    <div
                      key={slice.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenSwapModal(slice);
                      }}
                      className={`absolute top-1.5 bottom-1.5 rounded-xl overflow-hidden border-2 transition-all group cursor-pointer flex flex-col justify-between p-2 ${
                        isCurrent
                          ? 'border-cyan-400 bg-cyan-950/60 shadow-xl z-20 scale-[1.01]'
                          : 'border-slate-800 bg-slate-900/90 hover:border-slate-600'
                      }`}
                      style={{ left: `${sliceLeft}px`, width: `${sliceWidth}px` }}
                    >
                      <div className="flex items-center justify-between text-[9px] font-mono">
                        <span className="px-1.5 py-0.5 rounded bg-black/80 text-teal-300 font-bold">
                          #{idx + 1} ({slice.beat_count}b • {(slice.timeline_end_sec - slice.timeline_start_sec).toFixed(1)}s)
                        </span>
                        <div className="flex items-center gap-1">
                          <span className={`text-[8px] px-1 py-0.2 rounded font-bold ${
                            isVideo ? 'bg-amber-500/20 text-amber-300' : 'bg-teal-500/20 text-teal-300'
                          }`}>
                            {isVideo ? 'VIDEO' : 'PHOTO'}
                          </span>
                          {slice.enable_ken_burns && !isVideo && (
                            <span className="text-[8px] px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300">
                              KB Zoom
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="space-y-1">
                        <p className="text-[10px] font-semibold text-white truncate drop-shadow">
                          {asset?.caption || asset?.file_path.split(/[\\/]/).pop()}
                        </p>

                        <div className="flex items-center justify-between gap-1 text-[9px] text-slate-400 font-mono" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center gap-0.5">
                            <button
                              onClick={() => onUpdateSliceBeatCount(slice.id, Math.max(1, slice.beat_count - 1))}
                              className="w-3.5 h-3.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center justify-center font-bold"
                              title="Shorten clip duration by 1 beat"
                            >
                              -
                            </button>
                            <button
                              onClick={() => onUpdateSliceBeatCount(slice.id, slice.beat_count + 1)}
                              className="w-3.5 h-3.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center justify-center font-bold"
                              title="Extend clip duration by 1 beat"
                            >
                              +
                            </button>
                          </div>

                          <div className="flex items-center gap-0.5">
                            <button
                              onClick={() => handleMoveSlice(idx, -1)}
                              disabled={idx === 0}
                              className="w-3.5 h-3.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-30 flex items-center justify-center"
                              title="Shift clip earlier"
                            >
                              <ArrowLeft className="w-2 h-2" />
                            </button>
                            <button
                              onClick={() => handleMoveSlice(idx, 1)}
                              disabled={idx === slices.length - 1}
                              className="w-3.5 h-3.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-30 flex items-center justify-center"
                              title="Shift clip later"
                            >
                              <ArrowRight className="w-2 h-2" />
                            </button>
                          </div>
                        </div>
                      </div>

                      <div className="text-[8px] text-teal-400 font-medium opacity-0 group-hover:opacity-100 transition text-center flex items-center justify-center gap-0.5">
                        <Sparkles className="w-2 h-2" /> Swap Media
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* LAYER 2: VIDEO AUDIO / CLIP SOUND TRACK */}
              <div className="h-9 relative bg-slate-900/30 border-b border-slate-800/80 flex items-center">
                {slices.map((slice, idx) => {
                  const sLeft = slice.timeline_start_sec * zoom;
                  const sWidth = Math.max(40, (slice.timeline_end_sec - slice.timeline_start_sec) * zoom);
                  const isVideo = slice.asset?.media_type === 'video';
                  const isMuted = slice.audio_muted !== false;
                  const volume = slice.audio_volume !== undefined ? slice.audio_volume : 1.0;

                  return (
                    <div
                      key={slice.id}
                      onClick={(e) => e.stopPropagation()}
                      className={`absolute h-6 rounded-md px-1.5 flex items-center justify-between border text-[9px] transition-all ${
                        !isVideo
                          ? 'bg-slate-950/40 border-slate-800/40 text-slate-600'
                          : isMuted
                          ? 'bg-slate-900 border-slate-800 text-slate-400'
                          : 'bg-amber-950/40 border-amber-500/50 text-amber-300 font-bold'
                      }`}
                      style={{ left: `${sLeft}px`, width: `${sWidth}px` }}
                    >
                      {!isVideo ? (
                        <span className="text-[8px] text-slate-600 truncate">Photo (Silent)</span>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              if (onUpdateSliceAudio) {
                                onUpdateSliceAudio(slice.id, !isMuted, volume);
                              }
                            }}
                            className={`flex items-center gap-1 px-1 py-0.5 rounded text-[8px] font-bold transition ${
                              isMuted ? 'bg-slate-800 hover:bg-slate-700 text-slate-400' : 'bg-amber-500 text-slate-950'
                            }`}
                            title={isMuted ? 'Click to Unmute video clip audio' : 'Click to Mute video clip audio'}
                          >
                            {isMuted ? <VolumeX className="w-2.5 h-2.5" /> : <Volume2 className="w-2.5 h-2.5" />}
                            <span>{isMuted ? 'MUTED' : `${Math.round(volume * 100)}%`}</span>
                          </button>

                          {/* Mini Audio Amplitude Visualizer */}
                          <div className="flex items-center gap-0.5 opacity-60">
                            {[4, 8, 12, 6, 14, 8].map((h, i) => (
                              <div
                                key={i}
                                className={`w-0.5 rounded-full ${isMuted ? 'bg-slate-700' : 'bg-amber-400'}`}
                                style={{ height: `${h}px` }}
                              />
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* LAYER 1 (BOTTOM): MASTER MUSIC & WAVEFORM TRACK */}
              <div className="h-12 relative bg-gradient-to-b from-slate-950 to-slate-900/90 flex items-center overflow-hidden">
                {/* Visualizer Waveform Bars */}
                <div className="absolute inset-0 flex items-center gap-[2px] px-1 pointer-events-none opacity-80">
                  {waveformBars.map((bar, i) => {
                    const isPast = currentTime >= bar.time;
                    return (
                      <div
                        key={i}
                        className={`flex-1 rounded-full transition-colors ${
                          isPast ? 'bg-teal-400' : 'bg-slate-700/80'
                        }`}
                        style={{ height: `${bar.height}%` }}
                      />
                    );
                  })}
                </div>

                {/* Beat Grid Downbeat Lines on Master Track */}
                {audioTrack?.beat_grid?.map((beatTime, idx) => {
                  const isDownbeat = idx % 4 === 0;
                  if (!isDownbeat) return null;
                  return (
                    <div
                      key={idx}
                      className="absolute top-0 bottom-0 border-l border-teal-500/30 pointer-events-none z-10"
                      style={{ left: `${beatTime * zoom}px` }}
                    />
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Embedded Timeline & Video Effects Control Deck */}
      <div className="mt-2 shrink-0">
        <TimelineControlDeck
          project={project}
          audioTrack={audioTrack}
          slices={slices}
          currentTime={currentTime}
          onUpdateControls={onUpdateControls}
          onBulkApply={onBulkApply}
          onSolveTimeline={onSolveTimeline}
          onUpdateSliceCaption={onUpdateSliceCaption}
          isSolving={isSolving}
        />
      </div>
    </div>
  );
}

