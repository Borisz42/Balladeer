import React, { useRef, useEffect, useState } from 'react';
import { Play, Pause, Maximize2, Sparkles, Film, Image as ImageIcon } from 'lucide-react';

export default function LiveCanvasPreview({
  project,
  audioTrack,
  slices,
  currentTime,
  isPlaying,
  onTogglePlay,
  aspectRatio = '16:9'
}) {
  const canvasRef = useRef(null);

  // Find active slice at currentTime
  const activeSlice = slices.find(
    (s) => currentTime >= s.timeline_start_sec && currentTime < s.timeline_end_sec
  ) || slices[0];

  // Find active aligned words
  const activeWords = audioTrack?.aligned_lyrics?.filter(
    (w) => currentTime >= w.snapped_start && currentTime <= w.snapped_end
  ) || [];

  // Active phrase
  const activePhraseWords = audioTrack?.aligned_lyrics?.filter(
    (w) => Math.abs(w.snapped_start - currentTime) <= 2.0
  ) || [];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let targetW = 960;
    let targetH = 540;
    if (aspectRatio === '9:16') {
      targetW = 405;
      targetH = 720;
    } else if (aspectRatio === '1:1') {
      targetW = 540;
      targetH = 540;
    }
    canvas.width = targetW;
    canvas.height = targetH;

    // Clear canvas
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, targetW, targetH);

    if (!activeSlice || !activeSlice.asset) {
      ctx.fillStyle = '#64748b';
      ctx.font = '16px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No media in active slice', targetW / 2, targetH / 2);
      return;
    }

    const asset = activeSlice.asset;
    const isKenBurns = activeSlice.enable_ken_burns;
    const bgMode = activeSlice.bg_mode;

    // Progress within slice
    const sliceDur = activeSlice.timeline_end_sec - activeSlice.timeline_start_sec;
    const sliceProgress = Math.max(0, Math.min(1, (currentTime - activeSlice.timeline_start_sec) / Math.max(sliceDur, 0.1)));
    const zoomFactor = isKenBurns ? 1.0 + sliceProgress * 0.2 : 1.0;

    // Draw background (Blurred Fill simulation)
    if (bgMode === 'blurred_fill') {
      // Simulated vibrant blurred backdrop
      const grad = ctx.createRadialGradient(
        targetW / 2, targetH / 2, 50,
        targetW / 2, targetH / 2, Math.max(targetW, targetH)
      );
      grad.addColorStop(0, '#1e293b');
      grad.addColorStop(0.5, '#0f172a');
      grad.addColorStop(1, '#020617');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, targetW, targetH);
    }

    // Draw centered foreground box
    const cardW = targetW * 0.75 * zoomFactor;
    const cardH = targetH * 0.75 * zoomFactor;
    const cardX = (targetW - cardW) / 2;
    const cardY = (targetH - cardH) / 2;

    ctx.save();
    ctx.fillStyle = '#1e293b';
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(cardX, cardY, cardW, cardH, 12);
    ctx.fill();
    ctx.stroke();

    // Asset title & icon inside card
    ctx.fillStyle = '#f8fafc';
    ctx.font = 'bold 18px Inter, sans-serif';
    ctx.textAlign = 'center';
    const titleText = asset.caption || asset.file_path.split(/[\\/]/).pop();
    ctx.fillText(titleText, targetW / 2, targetH / 2 - 10);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px JetBrains Mono, monospace';
    ctx.fillText(`${asset.media_type.toUpperCase()} • Rating: ${asset.quality_score?.toFixed(1)}/10`, targetW / 2, targetH / 2 + 20);
    ctx.restore();

    // Draw Subtitles / Karaoke Overlay
    if (audioTrack?.is_instrumental) {
      // Event Card chapter overlay
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(targetW * 0.1, targetH - 65, targetW * 0.8, 45, 8);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#f1f5f9';
      ctx.font = 'bold 15px Inter, sans-serif';
      ctx.textAlign = 'center';
      const eventText = titleText.startsWith('Day') ? titleText : `[Act] ${titleText}`;
      ctx.fillText(eventText, targetW / 2, targetH - 37);
    } else {
      // Karaoke lyric ribbon overlay
      if (activePhraseWords.length > 0) {
        ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
        ctx.beginPath();
        ctx.roundRect(targetW * 0.08, targetH - 70, targetW * 0.84, 50, 10);
        ctx.fill();

        ctx.font = 'bold 16px Inter, sans-serif';
        ctx.textAlign = 'center';

        const lineString = activePhraseWords.map((w) => w.word).join(' ');
        const activeWord = activeWords[0]?.word;

        if (activeWord) {
          ctx.fillStyle = '#2dd4bf';
          ctx.fillText(`🎶 ${activeWord.toUpperCase()}`, targetW / 2, targetH - 38);
        } else {
          ctx.fillStyle = '#e2e8f0';
          ctx.fillText(lineString, targetW / 2, targetH - 38);
        }
      }
    }
  }, [currentTime, activeSlice, activeWords, activePhraseWords, aspectRatio, audioTrack]);

  return (
    <div className="bg-slate-950 rounded-xl p-3 border border-slate-800 flex flex-col items-center justify-center relative overflow-hidden">
      <div className="flex items-center justify-between w-full pb-2 mb-2 border-b border-slate-800 text-xs text-slate-300 font-mono">
        <span className="flex items-center gap-1.5 text-teal-400 font-bold">
          <Film className="w-3.5 h-3.5" />
          Live Compositor Canvas
        </span>
        <span>Aspect: <strong className="text-white">{aspectRatio}</strong></span>
      </div>

      <div className="relative rounded-lg overflow-hidden border border-slate-800 shadow-2xl bg-black flex items-center justify-center">
        <canvas
          ref={canvasRef}
          className="max-h-72 w-auto object-contain cursor-pointer"
          onClick={onTogglePlay}
        />
      </div>

      <div className="flex items-center justify-between w-full pt-2 mt-2 text-[11px] text-slate-400 font-mono">
        <span>Shot: {activeSlice ? `#${activeSlice.clip_order + 1}` : 'None'}</span>
        <span>Mode: {activeSlice?.bg_mode === 'blurred_fill' ? 'Blurred Fill' : activeSlice?.bg_mode}</span>
        <span>{isPlaying ? '▶ Playing' : '⏸ Paused'}</span>
      </div>
    </div>
  );
}
