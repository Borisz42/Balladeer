import React, { useRef, useEffect, useState, useMemo } from 'react';
import {
  Tv,
  Download,
  Play,
  Pause,
  Film
} from 'lucide-react';

export default function VideoPlayerPane({
  project,
  audioTrack,
  slices = [],
  currentTime = 0,
  isPlaying = false,
  onTogglePlay,
  onSeek,
  videoUrl
}) {
  const [viewMode, setViewMode] = useState('realtime'); // 'realtime' | 'rendered'
  const canvasRef = useRef(null);
  const imageCacheRef = useRef(new Map());
  const videoCacheRef = useRef(new Map());

  const aspect = project?.config_override?.video?.aspect_ratio || '16:9';

  // Find active slice at currentTime
  const activeSlice = slices.find(
    (s) => currentTime >= s.timeline_start_sec && currentTime < s.timeline_end_sec
  ) || (slices.length > 0 ? slices[0] : null);

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

  // Active phrase fallback
  const activePhraseWords = audioTrack?.aligned_lyrics?.filter(
    (w) => Math.abs(w.snapped_start - currentTime) <= 2.2
  ) || [];

  // Preload and cache media elements (Images, Thumbnails, Videos)
  useEffect(() => {
    if (!project?.id) return;

    slices.forEach((slice) => {
      const asset = slice.asset;
      if (!asset) return;

      const isVideo = asset.media_type === 'video';
      const fileUrl = `http://localhost:8000/api/projects/${project.id}/assets/${asset.id}/file`;
      const thumbUrl = `http://localhost:8000/api/projects/${project.id}/assets/${asset.id}/thumbnail`;

      // Cache thumbnail/image
      if (!imageCacheRef.current.has(asset.id)) {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.src = isVideo ? thumbUrl : fileUrl;
        img.onload = () => {
          imageCacheRef.current.set(asset.id, img);
        };
      }

      // Cache video element for video slices
      if (isVideo && !videoCacheRef.current.has(asset.id)) {
        const v = document.createElement('video');
        v.crossOrigin = 'anonymous';
        v.src = fileUrl;
        v.muted = true;
        v.playsInline = true;
        v.preload = 'auto';
        v.load();
        videoCacheRef.current.set(asset.id, v);
      }
    });
  }, [slices, project?.id]);

  // Synchronize active video element playback & seeking
  useEffect(() => {
    if (viewMode !== 'realtime' || !activeSlice?.asset) return;

    const asset = activeSlice.asset;
    const isVideo = asset.media_type === 'video';

    // Pause all non-active video elements
    videoCacheRef.current.forEach((vElem, aId) => {
      if (aId !== asset.id && !vElem.paused) {
        vElem.pause();
      }
    });

    if (isVideo) {
      const vElem = videoCacheRef.current.get(asset.id);
      if (vElem) {
        const sliceElapsed = Math.max(0, currentTime - activeSlice.timeline_start_sec);
        const targetVideoTime = (activeSlice.source_start_sec || 0) + sliceElapsed;

        // Keep video time in tight sync with playhead
        if (Math.abs(vElem.currentTime - targetVideoTime) > 0.25) {
          vElem.currentTime = targetVideoTime;
        }

        if (isPlaying) {
          if (vElem.paused) {
            vElem.play().catch(() => {});
          }
        } else {
          if (!vElem.paused) {
            vElem.pause();
          }
        }
      }
    }
  }, [activeSlice, currentTime, isPlaying, viewMode]);

  // Real-time 60 FPS Canvas Render Loop
  useEffect(() => {
    if (viewMode !== 'realtime') return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let targetW = 960;
    let targetH = 540;
    if (aspect === '9:16') {
      targetW = 540;
      targetH = 960;
    } else if (aspect === '1:1') {
      targetW = 720;
      targetH = 720;
    }
    canvas.width = targetW;
    canvas.height = targetH;

    // Clear background
    ctx.fillStyle = '#090d16';
    ctx.fillRect(0, 0, targetW, targetH);

    if (!activeSlice || !activeSlice.asset) {
      ctx.fillStyle = '#475569';
      ctx.font = 'bold 20px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No Media on Timeline', targetW / 2, targetH / 2 - 10);
      ctx.font = '13px JetBrains Mono, monospace';
      ctx.fillStyle = '#334155';
      ctx.fillText('Auto-solve or add clips to timeline below to preview in real time', targetW / 2, targetH / 2 + 20);
      return;
    }

    const cfg = project?.config_override || {};
    const vFx = cfg.video_effects || {};
    const lStyle = cfg.lyrics_style || {};
    const tOverlays = cfg.text_overlays || {};
    const vConfig = cfg.video || {};

    const asset = activeSlice.asset;
    const isVideo = asset.media_type === 'video';
    const bgMode = activeSlice.bg_mode || vFx.default_bg_mode || vConfig.default_bg_mode || 'blurred_fill';
    const blurRadius = vFx.blur_radius !== undefined ? vFx.blur_radius : 28;
    const enableKenBurns = activeSlice.enable_ken_burns !== undefined
      ? activeSlice.enable_ken_burns
      : (vFx.enable_ken_burns !== undefined ? vFx.enable_ken_burns : true);
    const kenBurnsZoom = vFx.ken_burns_zoom !== undefined ? vFx.ken_burns_zoom : 1.15;
    const colorFilter = vFx.color_filter || 'natural';
    const enableVignette = vFx.enable_vignette || false;

    // Apply color grading LUT filter in CSS context or pixel filter
    if (colorFilter === 'teal_orange') {
      ctx.filter = 'contrast(1.15) saturate(1.25) hue-rotate(-10deg)';
    } else if (colorFilter === 'warm_gold') {
      ctx.filter = 'sepia(0.25) saturate(1.3) brightness(1.05)';
    } else if (colorFilter === 'vintage_35mm') {
      ctx.filter = 'sepia(0.35) contrast(0.95) saturate(0.85)';
    } else if (colorFilter === 'cyberpunk') {
      ctx.filter = 'contrast(1.3) saturate(1.6) hue-rotate(15deg)';
    } else if (colorFilter === 'noir_bw') {
      ctx.filter = 'grayscale(1) contrast(1.4)';
    } else {
      ctx.filter = 'none';
    }

    // Determine the active visual source (video frame, cached photo, or thumbnail)
    const cachedImg = imageCacheRef.current.get(asset.id);
    const cachedVideo = isVideo ? videoCacheRef.current.get(asset.id) : null;

    let mediaSource = null;
    let srcW = 0;
    let srcH = 0;

    if (isVideo && cachedVideo && cachedVideo.readyState >= 2 && cachedVideo.videoWidth > 0) {
      mediaSource = cachedVideo;
      srcW = cachedVideo.videoWidth;
      srcH = cachedVideo.videoHeight;
    } else if (cachedImg && cachedImg.complete && cachedImg.naturalWidth > 0) {
      mediaSource = cachedImg;
      srcW = cachedImg.naturalWidth;
      srcH = cachedImg.naturalHeight;
    }

    if (mediaSource && srcW > 0 && srcH > 0) {
      // 1. Background Rendering (Blurred Fill or Ambient Glow or Black)
      if (bgMode === 'blurred_fill') {
        ctx.save();
        ctx.filter = `blur(${blurRadius}px) brightness(0.55) saturate(1.3)`;
        ctx.drawImage(mediaSource, -30, -30, targetW + 60, targetH + 60);
        ctx.restore();
      } else if (bgMode === 'ambient_glow') {
        ctx.save();
        ctx.filter = 'blur(45px) saturate(2.0) brightness(0.4)';
        ctx.drawImage(mediaSource, -20, -20, targetW + 40, targetH + 40);
        ctx.restore();
      } else {
        ctx.fillStyle = '#05070d';
        ctx.fillRect(0, 0, targetW, targetH);
      }

      // 2. Main Foreground Media with Aspect Fit & Ken Burns (for photos)
      ctx.save();
      const mediaAspect = srcW / srcH;
      const canvasAspect = targetW / targetH;

      let drawW, drawH;
      if (mediaAspect > canvasAspect) {
        drawW = targetW;
        drawH = targetW / mediaAspect;
      } else {
        drawH = targetH;
        drawW = targetH * mediaAspect;
      }

      // Ken Burns dynamic pan/zoom
      let zoomFactor = 1.0;
      if (enableKenBurns && !isVideo) {
        const sliceDur = Math.max(0.1, activeSlice.timeline_end_sec - activeSlice.timeline_start_sec);
        const sliceProgress = Math.max(0, Math.min(1,
          (currentTime - activeSlice.timeline_start_sec) / sliceDur
        ));
        zoomFactor = 1.0 + (kenBurnsZoom - 1.0) * sliceProgress;
      }

      const scaledW = drawW * zoomFactor;
      const scaledH = drawH * zoomFactor;
      const posX = (targetW - scaledW) / 2;
      const posY = (targetH - scaledH) / 2;

      ctx.drawImage(mediaSource, posX, posY, scaledW, scaledH);
      ctx.restore();
    }

    // Reset filter for UI overlays
    ctx.filter = 'none';

    // Optional Vignette corner darkening
    if (enableVignette) {
      const grad = ctx.createRadialGradient(
        targetW / 2, targetH / 2, Math.min(targetW, targetH) * 0.35,
        targetW / 2, targetH / 2, Math.max(targetW, targetH) * 0.7
      );
      grad.addColorStop(0, 'rgba(0,0,0,0)');
      grad.addColorStop(1, 'rgba(0,0,0,0.65)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, targetW, targetH);
    }

    // 3. OVERLAYS: Creator Watermark Badge (Top Right)
    if (tOverlays.watermark_text) {
      ctx.save();
      const op = (tOverlays.watermark_opacity !== undefined ? tOverlays.watermark_opacity : 80) / 100;
      ctx.fillStyle = `rgba(255, 255, 255, ${op})`;
      ctx.shadowColor = 'rgba(0,0,0,0.8)';
      ctx.shadowBlur = 4;
      ctx.font = 'bold 12px Inter, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(tOverlays.watermark_text, targetW - 20, 28);
      ctx.restore();
    }

    // OVERLAYS: Video Intro Title Card (During intro duration)
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

    // 4. SUBTITLES & CAPTIONS (STRICT SINGLE-TYPE MUTUAL EXCLUSIVITY: Exactly ONE or none!)
    const rawSubtitleMode = lStyle.subtitle_mode;
    const subtitleMode = (rawSubtitleMode && rawSubtitleMode !== 'auto')
      ? rawSubtitleMode
      : 'karaoke_lyrics';

    const highlightColor = lStyle.highlight_color || '#2dd4bf';
    const fontFamily = lStyle.font_family || 'Inter';
    const alignPos = lStyle.alignment || 2; // 2=bottom, 5=center, 8=top
    const subY = alignPos === 8 ? 65 : alignPos === 5 ? targetH / 2 : targetH - 65;

    if (subtitleMode === 'hidden') {
      // Subtitles Off: No text rendered
    } else if (subtitleMode === 'narrative_descriptions') {
      // 1. Scene story narration ONLY (Raw slice caption)
      const descText = activeSlice.custom_caption || asset.caption || 'Descriptive story narration';
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
      ctx.fillText(`🏷️ ACT: ${asset.caption || `Chapter #${activeSlice.clip_order + 1}`}`, targetW / 2, subY + 8);
      ctx.restore();
    } else if (subtitleMode === 'karaoke_lyrics') {
      // 3. Line-by-line Karaoke synced lyrics or Timed Voiceover Narration Subtitles
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
          // Full line with active word highlighted
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
            } else {
              ctx.fillStyle = '#e2e8f0';
              ctx.shadowBlur = 0;
            }
            ctx.fillText(m.word, drawX, subY + 8);
            drawX += m.width + spaceWidth;
          });
        }
        ctx.restore();
      }
    }

    // 5. Subtle Timecode HUD (Top Left of canvas)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
    ctx.fillRect(15, 15, 115, 26);
    ctx.fillStyle = '#2dd4bf';
    ctx.font = 'bold 11px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`${currentTime.toFixed(2)}s / ${aspect}`, 72, 32);

  }, [currentTime, activeSlice, activeLine, activePhraseWords, lyricLines, aspect, audioTrack, viewMode, project?.config_override]);

  return (
    <div className="glass-panel rounded-2xl p-4 border border-slate-800 h-full flex flex-col overflow-hidden">
      {/* Header with Mode Toggle & Download */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center shrink-0">
            <Tv className="w-3.5 h-3.5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-white uppercase tracking-wider truncate">
              Program Monitor (Real-Time Output)
            </h2>
            <p className="text-[10px] text-teal-400 font-mono truncate">
              {viewMode === 'realtime' ? '⚡ 60 FPS Real-Time Compositor' : '🎬 Rendered NVENC Video'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {videoUrl && (
            <div className="flex items-center bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-[10px] font-semibold">
              <button
                onClick={() => setViewMode('realtime')}
                className={`px-2 py-0.5 rounded transition ${
                  viewMode === 'realtime'
                    ? 'bg-teal-500 text-slate-950 font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Real-Time
              </button>
              <button
                onClick={() => setViewMode('rendered')}
                className={`px-2 py-0.5 rounded transition ${
                  viewMode === 'rendered'
                    ? 'bg-teal-500 text-slate-950 font-bold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                MP4 Export
              </button>
            </div>
          )}

          {videoUrl && (
            <a
              href={videoUrl}
              download={`${project?.title || 'montage'}.mp4`}
              className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 px-2.5 py-1 rounded-lg text-[11px] font-bold transition shadow-sm"
              title="Download rendered MP4"
            >
              <Download className="w-3 h-3" />
              <span>MP4</span>
            </a>
          )}
        </div>
      </div>

      {/* Main Viewport */}
      <div className="flex-1 flex flex-col justify-center items-center rounded-xl overflow-hidden bg-slate-950 border border-slate-800/80 relative min-h-0">
        {viewMode === 'rendered' && videoUrl ? (
          <video
            controls
            autoPlay
            className="w-full h-full object-contain"
            src={videoUrl}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center relative select-none">
            <canvas
              ref={canvasRef}
              onClick={onTogglePlay}
              className="max-h-full max-w-full object-contain cursor-pointer shadow-2xl rounded-lg"
            />

            {/* Overlay Play/Pause indicator on hover */}
            <button
              onClick={onTogglePlay}
              className="absolute bottom-3 right-3 w-9 h-9 rounded-full bg-slate-900/85 hover:bg-teal-500 hover:text-slate-950 text-white border border-slate-700 flex items-center justify-center transition shadow-xl"
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
            </button>
          </div>
        )}
      </div>

      {/* Footer HUD info */}
      <div className="flex items-center justify-between pt-2 mt-2 border-t border-slate-800/80 text-[10px] font-mono text-slate-400 shrink-0">
        <span className="truncate">
          Active Cut: {activeSlice ? `#${activeSlice.clip_order + 1} (${activeSlice.beat_count} beats)` : 'None'}
        </span>
        <span className="text-slate-300">
          Aspect: <strong className="text-teal-400 font-bold">{aspect}</strong>
        </span>
        <span className={isPlaying ? 'text-teal-400 font-bold' : 'text-slate-500'}>
          {isPlaying ? '▶ Real-time Active' : '⏸ Paused'}
        </span>
      </div>
    </div>
  );
}
