import React, { useState, useRef } from 'react';
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
  ArrowRight
} from 'lucide-react';

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
  isSolving,
  isRendering
}) {
  const [zoom, setZoom] = useState(60);
  const timelineRef = useRef(null);

  const totalDuration = audioTrack?.beat_grid?.length
    ? (audioTrack.beat_grid[audioTrack.beat_grid.length - 1] || 30.0) + 1.0
    : 30.0;

  const totalWidth = totalDuration * zoom;

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
    const beatIdx = beatGrid.findIndex((b) => Math.abs(b - currentTime) <= 0.3);
    if (beatIdx > active.start_beat && beatIdx < active.start_beat + active.beat_count) {
      onSplitSlice(active.id, beatIdx);
    } else {
      alert('Playhead must be inside the slice and aligned near a beat to split.');
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

  const aspect = project?.config_override?.video?.aspect_ratio || '16:9';

  return (
    <div className="glass-panel rounded-2xl p-4 border border-slate-800 h-full flex flex-col overflow-hidden">
      {/* Control & Status Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3 pb-2 border-b border-slate-800/80 shrink-0">
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

          {/* Quick Metrics */}
          <div className="hidden md:flex items-center gap-2 font-mono text-[11px]">
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
              {audioTrack?.bpm || 120} BPM
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-300">
              {slices.length} Cuts
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-white">
              {aspect}
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
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
            <span>{isRendering ? 'Rendering...' : 'Export Final MP4'}</span>
          </button>
        </div>
      </div>

      {/* Multi-Track Timeline Viewport */}
      <div className="flex-1 overflow-hidden flex flex-col min-h-0">
        <div
          ref={timelineRef}
          onClick={handleTimelineClick}
          className="timeline-grid overflow-x-auto overflow-y-hidden flex-1 relative rounded-xl bg-slate-950/90 border border-slate-800 cursor-pointer select-none"
        >
          <div style={{ width: `${Math.max(totalWidth, 800)}px` }} className="relative h-full flex flex-col justify-between">
            {/* Playhead Marker */}
            <div
              className="absolute top-0 bottom-0 z-30 w-0.5 bg-cyan-400 pointer-events-none"
              style={{ left: `${currentTime * zoom}px` }}
            >
              <div className="w-3 h-3 -ml-1.5 bg-cyan-400 rotate-45 transform shadow-md shadow-cyan-400/50" />
            </div>

            {/* Track 1: Beat Grid */}
            <div className="h-7 border-b border-slate-800/80 bg-slate-900/90 flex items-center relative font-mono text-[9px] shrink-0">
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

            {/* Track 2: Lyrics Ribbon */}
            <div className="h-8 border-b border-slate-800/60 bg-slate-900/50 relative flex items-center shrink-0">
              {audioTrack?.aligned_lyrics?.map((wordObj, idx) => {
                const wLeft = wordObj.snapped_start * zoom;
                const wWidth = Math.max(20, (wordObj.snapped_end - wordObj.snapped_start) * zoom);
                const isActive = currentTime >= wordObj.snapped_start && currentTime <= wordObj.snapped_end;

                return (
                  <div
                    key={idx}
                    className={`absolute h-5 rounded px-1 flex items-center justify-center text-[10px] font-semibold transition-all ${
                      isActive
                        ? 'bg-teal-500 text-slate-950 scale-105 shadow-md z-20'
                        : 'bg-slate-800/80 text-slate-300 border border-slate-700/50'
                    }`}
                    style={{ left: `${wLeft}px`, width: `${wWidth}px` }}
                  >
                    <span className="truncate">{wordObj.word}</span>
                  </div>
                );
              })}
            </div>

            {/* Track 3: Media Slices */}
            <div className="flex-1 relative bg-slate-950/60 p-2 min-h-[140px]">
              {slices.map((slice, idx) => {
                const sliceLeft = slice.timeline_start_sec * zoom;
                const sliceWidth = Math.max(50, (slice.timeline_end_sec - slice.timeline_start_sec) * zoom);
                const isCurrent = currentTime >= slice.timeline_start_sec && currentTime < slice.timeline_end_sec;
                const asset = slice.asset;

                return (
                  <div
                    key={slice.id}
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpenSwapModal(slice);
                    }}
                    className={`absolute top-2 bottom-2 rounded-xl overflow-hidden border-2 transition-all group cursor-pointer flex flex-col justify-between p-2 ${
                      isCurrent
                        ? 'border-cyan-400 bg-cyan-950/50 shadow-xl z-20 scale-[1.01]'
                        : 'border-slate-800 bg-slate-900/90 hover:border-slate-600'
                    }`}
                    style={{ left: `${sliceLeft}px`, width: `${sliceWidth}px` }}
                  >
                    <div className="flex items-center justify-between text-[9px] font-mono">
                      <span className="px-1 py-0.2 rounded bg-black/70 text-teal-300 font-bold">
                        #{idx + 1} ({slice.beat_count}b)
                      </span>
                      {slice.enable_ken_burns && (
                        <span className="text-[8px] px-1 py-0.2 rounded bg-cyan-500/20 text-cyan-300">
                          Ken Burns
                        </span>
                      )}
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
                          >
                            -
                          </button>
                          <button
                            onClick={() => onUpdateSliceBeatCount(slice.id, slice.beat_count + 1)}
                            className="w-3.5 h-3.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 flex items-center justify-center font-bold"
                          >
                            +
                          </button>
                        </div>

                        <div className="flex items-center gap-0.5">
                          <button
                            onClick={() => handleMoveSlice(idx, -1)}
                            disabled={idx === 0}
                            className="w-3.5 h-3.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-30 flex items-center justify-center"
                          >
                            <ArrowLeft className="w-2 h-2" />
                          </button>
                          <button
                            onClick={() => handleMoveSlice(idx, 1)}
                            disabled={idx === slices.length - 1}
                            className="w-3.5 h-3.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-30 flex items-center justify-center"
                          >
                            <ArrowRight className="w-2 h-2" />
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="text-[8px] text-teal-400 font-medium opacity-0 group-hover:opacity-100 transition text-center flex items-center justify-center gap-0.5">
                      <Sparkles className="w-2 h-2" /> Swap Shot
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
