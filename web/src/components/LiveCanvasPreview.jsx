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

  // Extract video effects & text overlay configs
  const config = project?.config_override || {};
  const vFx = config.video_effects || {};
  const lStyle = config.lyrics_style || {};
  const tOverlays = config.text_overlays || {};

  // Find active slice at currentTime
  const activeSlice = slices.find(
    (s) => currentTime >= s.timeline_start_sec && currentTime < s.timeline_end_sec
  ) || slices[0];

  // Find active aligned words
  const activeWords = audioTrack?.aligned_lyrics?.filter(
    (w) => currentTime >= w.snapped_start && currentTime <= w.snapped_end
  ) || [];

  // Group aligned lyrics into lines
  const lyricLines = useMemo(() => {
    if (!audioTrack?.aligned_lyrics?.length) return [];
    const grouped = [];
    let currentLineIdx = null;
    let currentChunk = [];

    audioTrack.aligned_lyrics.forEach((w, idx) => {
      const lIdx = w.line_index !== undefined && w.line_index !== null ? w.line_index : Math.floor(idx / 5);
      if (currentLineIdx === null || lIdx === currentLineIdx) {
        currentChunk.push(w);
        currentLineIdx = lIdx;
      } else {
        if (currentChunk.length > 0) {
          grouped.push({
            words: currentChunk,
            start: currentChunk[0].snapped_start,
            end: currentChunk[currentChunk.length - 1].snapped_end + 0.3
          });
        }
        currentChunk = [w];
        currentLineIdx = lIdx;
      }
    });

    if (currentChunk.length > 0) {
      grouped.push({
        words: currentChunk,
        start: currentChunk[0].snapped_start,
        end: currentChunk[currentChunk.length - 1].snapped_end + 0.3
      });
    }

    return grouped;
  }, [audioTrack?.aligned_lyrics]);

  // Find active line at currentTime
  const activeLine = lyricLines.find(
    (l) => currentTime >= l.start && currentTime <= l.end
  );

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
    ctx.fillStyle = '#090d16';
    ctx.fillRect(0, 0, targetW, targetH);

    if (!activeSlice || !activeSlice.asset) {
      ctx.fillStyle = '#64748b';
      ctx.font = '16px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No media in active slice', targetW / 2, targetH / 2);
      return;
    }

    const asset = activeSlice.asset;
    const isKenBurns = activeSlice.enable_ken_burns !== undefined
      ? activeSlice.enable_ken_burns
      : (vFx.enable_ken_burns !== undefined ? vFx.enable_ken_burns : true);
    const bgMode = activeSlice.bg_mode || vFx.default_bg_mode || 'blurred_fill';

    // Progress within slice for Ken Burns
    const sliceDur = activeSlice.timeline_end_sec - activeSlice.timeline_start_sec;
    const sliceProgress = Math.max(0, Math.min(1, (currentTime - activeSlice.timeline_start_sec) / Math.max(sliceDur, 0.1)));
    const zoomFactor = isKenBurns ? 1.0 + sliceProgress * ((vFx.ken_burns_zoom || 1.2) - 1.0) : 1.0;

    // Draw background (Blurred Fill simulation or ambient glow)
    if (bgMode === 'blurred_fill' || bgMode === 'ambient_glow') {
      const grad = ctx.createRadialGradient(
        targetW / 2, targetH / 2, 60,
        targetW / 2, targetH / 2, Math.max(targetW, targetH)
      );
      if (bgMode === 'ambient_glow') {
        grad.addColorStop(0, '#1e3a8a');
        grad.addColorStop(0.6, '#0f172a');
        grad.addColorStop(1, '#020617');
      } else {
        grad.addColorStop(0, '#1e293b');
        grad.addColorStop(0.5, '#0f172a');
        grad.addColorStop(1, '#020617');
      }
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, targetW, targetH);
    } else {
      // Black bars / pillar box
      ctx.fillStyle = '#000000';
      ctx.fillRect(0, 0, targetW, targetH);
    }

    // Draw centered foreground box
    const cardW = targetW * 0.78 * zoomFactor;
    const cardH = targetH * 0.78 * zoomFactor;
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
    const titleText = activeSlice.custom_caption || asset.caption || asset.file_path.split(/[\\/]/).pop();
    ctx.fillText(titleText, targetW / 2, targetH / 2 - 10);

    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px JetBrains Mono, monospace';
    ctx.fillText(`${asset.media_type.toUpperCase()} • Rating: ${asset.quality_score?.toFixed(1)}/10`, targetW / 2, targetH / 2 + 20);
    ctx.restore();

    // Apply Color Filter LUT Overlay
    const colorFilter = vFx.color_filter || 'natural';
    if (colorFilter === 'teal_orange') {
      ctx.save();
      ctx.globalCompositeOperation = 'overlay';
      const fGrad = ctx.createLinearGradient(0, 0, targetW, targetH);
      fGrad.addColorStop(0, 'rgba(13, 148, 136, 0.35)');
      fGrad.addColorStop(1, 'rgba(234, 88, 12, 0.35)');
      ctx.fillStyle = fGrad;
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.restore();
    } else if (colorFilter === 'vintage_35mm') {
      ctx.save();
      ctx.fillStyle = 'rgba(217, 119, 6, 0.18)';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.restore();
    } else if (colorFilter === 'cyberpunk') {
      ctx.save();
      ctx.globalCompositeOperation = 'color-dodge';
      ctx.fillStyle = 'rgba(168, 85, 247, 0.25)';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.restore();
    } else if (colorFilter === 'warm_gold') {
      ctx.save();
      ctx.fillStyle = 'rgba(245, 158, 11, 0.15)';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.restore();
    } else if (colorFilter === 'noir_bw') {
      ctx.save();
      ctx.globalCompositeOperation = 'saturation';
      ctx.fillStyle = '#000000';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.restore();
    }

    // Apply Vignette Lens Darkening
    if (vFx.enable_vignette) {
      ctx.save();
      const vGrad = ctx.createRadialGradient(
        targetW / 2, targetH / 2, targetW * 0.3,
        targetW / 2, targetH / 2, targetW * 0.65
      );
      vGrad.addColorStop(0, 'rgba(0, 0, 0, 0)');
      vGrad.addColorStop(1, 'rgba(0, 0, 0, 0.65)');
      ctx.fillStyle = vGrad;
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.restore();
    }

    // Watermark Overlay
    if (tOverlays.watermark_text) {
      ctx.save();
      ctx.fillStyle = `rgba(255, 255, 255, ${(tOverlays.watermark_opacity || 80) / 100})`;
      ctx.font = 'bold 12px Inter, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(tOverlays.watermark_text, targetW - 20, 25);
      ctx.restore();
    }

    // Intro Title Card Overlay
    const introDuration = tOverlays.intro_duration || 3.5;
    if (tOverlays.intro_enabled && currentTime <= introDuration) {
      ctx.save();
      ctx.fillStyle = 'rgba(15, 23, 42, 0.75)';
      ctx.fillRect(0, 0, targetW, 80);

      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 22px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(tOverlays.intro_title || project?.title || 'Balladeer Video', targetW / 2, 40);

      if (tOverlays.intro_subtitle) {
        ctx.fillStyle = '#2dd4bf';
        ctx.font = '13px Inter, sans-serif';
        ctx.fillText(tOverlays.intro_subtitle, targetW / 2, 62);
      }
      ctx.restore();
    }

    // Subtitle & Caption Rendering
    const rawSubtitleMode = lStyle.subtitle_mode;
    const subtitleMode = (rawSubtitleMode && rawSubtitleMode !== 'auto')
      ? rawSubtitleMode
      : 'karaoke_lyrics';

    const highlightColor = lStyle.highlight_color || '#2dd4bf';
    const fontFamily = lStyle.font_family || 'Inter';
    const alignPos = lStyle.alignment || 2; // 2=bottom, 5=center, 8=top
    const subY = alignPos === 8 ? 65 : alignPos === 5 ? targetH / 2 : targetH - 65;

    if (subtitleMode === 'hidden') {
      // Clean video output: No subtitles rendered
    } else if (subtitleMode === 'narrative_descriptions') {
      // 1. Scene story narration ONLY
      const descText = activeSlice?.custom_caption || asset.caption || 'Descriptive story narration';
      ctx.save();
      ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
      ctx.strokeStyle = 'rgba(45, 212, 191, 0.4)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(targetW * 0.08, subY - 20, targetW * 0.84, 46, 10);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#ffffff';
      ctx.font = `bold 14px ${fontFamily}, sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(`📖 ${descText}`, targetW / 2, subY + 8);
      ctx.restore();
    } else if (subtitleMode === 'chapter_event_cards') {
      // 2. Chapter act badge ONLY
      ctx.save();
      ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.roundRect(targetW * 0.12, subY - 18, targetW * 0.76, 42, 8);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#f8fafc';
      ctx.font = `bold 14px ${fontFamily}, sans-serif`;
      ctx.textAlign = 'center';
      ctx.fillText(`🏷️ ACT: ${titleText}`, targetW / 2, subY + 8);
      ctx.restore();
    } else if (subtitleMode === 'karaoke_lyrics') {
      // 3. Line-by-line Karaoke synced lyrics or Timed Story Subtitles
      const lineToRender = activeLine || (activePhraseWords.length > 0 ? {
        words: activePhraseWords,
        start: activePhraseWords[0].snapped_start,
        end: activePhraseWords[activePhraseWords.length - 1].snapped_end + 0.3
      } : null);

      if (lineToRender && lineToRender.words.length > 0) {
        ctx.save();
        ctx.fillStyle = 'rgba(15, 23, 42, 0.92)';
        ctx.strokeStyle = 'rgba(45, 212, 191, 0.35)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.roundRect(targetW * 0.06, subY - 22, targetW * 0.88, 46, 10);
        ctx.fill();
        ctx.stroke();

        ctx.font = `bold 15px ${fontFamily}, sans-serif`;
        const enableHighlight = lStyle.enable_word_highlight !== false;
        const iconPrefix = audioTrack?.is_instrumental ? '🎙️' : '🎶';

        if (!enableHighlight) {
          // Clean full line without word highlight
          ctx.fillStyle = '#ffffff';
          ctx.textAlign = 'center';
          const lineText = lineToRender.words.map((w) => w.word).join(' ');
          ctx.fillText(`${iconPrefix} ${lineText}`, targetW / 2, subY + 8);
        } else {
          const lineWords = lineToRender.words;
          const spaceWidth = ctx.measureText(' ').width;
          const wordMetrics = lineWords.map((w) => ({
            word: w.word,
            width: ctx.measureText(w.word).width,
            isActive: currentTime >= w.snapped_start && currentTime <= w.snapped_end
          }));

          const totalLineWidth = wordMetrics.reduce((acc, m) => acc + m.width, 0) + (wordMetrics.length - 1) * spaceWidth;
          let drawX = (targetW - totalLineWidth) / 2;

          ctx.textAlign = 'left';
          wordMetrics.forEach((m) => {
            if (m.isActive) {
              ctx.fillStyle = highlightColor;
              ctx.shadowColor = highlightColor;
              ctx.shadowBlur = 8;
              ctx.fillText(m.word, drawX, subY + 8);
              ctx.shadowBlur = 0;
            } else {
              ctx.fillStyle = '#e2e8f0';
              ctx.fillText(m.word, drawX, subY + 8);
            }
            drawX += m.width + spaceWidth;
          });
        }
        ctx.restore();
      }
    }
  }, [currentTime, activeSlice, activeWords, activePhraseWords, activeLine, lyricLines, aspectRatio, audioTrack, config]);

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
