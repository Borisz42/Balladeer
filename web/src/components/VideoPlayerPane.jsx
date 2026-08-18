import React, { useRef, useEffect, useState } from 'react';
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

  // Active word in lyrics
  const activeWord = audioTrack?.aligned_lyrics?.find(
    (w) => currentTime >= w.snapped_start && currentTime <= w.snapped_end
  );

  // Active phrase
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

    const asset = activeSlice.asset;
    const isVideo = asset.media_type === 'video';
    const isKenBurns = activeSlice.enable_ken_burns;
    const bgMode = activeSlice.bg_mode || 'blurred_fill';

    const sliceDur = Math.max(0.1, activeSlice.timeline_end_sec - activeSlice.timeline_start_sec);
    const sliceProgress = Math.max(0, Math.min(1, (currentTime - activeSlice.timeline_start_sec) / sliceDur));
    const zoomFactor = (!isVideo && isKenBurns) ? 1.0 + sliceProgress * 0.12 : 1.0;

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
      // 1. Blurred Fill Backdrop
      if (bgMode === 'blurred_fill') {
        ctx.save();
        ctx.filter = 'blur(28px) brightness(0.45) saturate(1.4)';
        ctx.drawImage(mediaSource, -30, -30, targetW + 60, targetH + 60);
        ctx.restore();
      }

      // 2. Main Foreground Media with Aspect Fit & Ken Burns (for photos)
      ctx.save();
      const imgRatio = srcW / srcH;
      const canvasRatio = targetW / targetH;

      let drawW, drawH;
      if (imgRatio > canvasRatio) {
        drawW = targetW;
        drawH = targetW / imgRatio;
      } else {
        drawH = targetH;
        drawW = targetH * imgRatio;
      }

      const scaledW = drawW * zoomFactor;
      const scaledH = drawH * zoomFactor;
      const posX = (targetW - scaledW) / 2;
      const posY = (targetH - scaledH) / 2;

      ctx.drawImage(mediaSource, posX, posY, scaledW, scaledH);
      ctx.restore();
    } else {
      // Loading state
      ctx.fillStyle = '#1e293b';
      ctx.fillRect(0, 0, targetW, targetH);
      ctx.fillStyle = '#38bdf8';
      ctx.font = 'bold 22px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(asset.caption || asset.file_path.split(/[\\/]/).pop(), targetW / 2, targetH / 2);
    }

    // 3. Subtitles & Real-time Karaoke Lyrics Ribbon
    if (audioTrack?.is_instrumental) {
      // Documentary Chapter Badge
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.strokeStyle = 'rgba(45, 212, 191, 0.4)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(targetW * 0.1, targetH - 65, targetW * 0.8, 42, 10);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 15px Inter, sans-serif';
      ctx.textAlign = 'center';
      const eventText = asset.caption || `Chapter #${activeSlice.clip_order + 1}`;
      ctx.fillText(eventText, targetW / 2, targetH - 39);
    } else if (activePhraseWords.length > 0) {
      // Karaoke Lyrics Overlay
      ctx.fillStyle = 'rgba(8, 12, 22, 0.88)';
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.roundRect(targetW * 0.06, targetH - 72, targetW * 0.88, 52, 12);
      ctx.fill();
      ctx.stroke();

      ctx.font = 'bold 16px Inter, sans-serif';
      ctx.textAlign = 'center';

      const phraseText = activePhraseWords.map((w) => w.word).join(' ');
      if (activeWord) {
        ctx.fillStyle = '#2dd4bf';
        ctx.fillText(`🎶 ${activeWord.word.toUpperCase()} 🎶`, targetW / 2, targetH - 40);
      } else {
        ctx.fillStyle = '#f1f5f9';
        ctx.fillText(phraseText, targetW / 2, targetH - 40);
      }
    }

    // 4. Subtle Timecode HUD (Top Right of canvas)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
    ctx.fillRect(targetW - 130, 15, 115, 28);
    ctx.fillStyle = '#2dd4bf';
    ctx.font = 'bold 12px JetBrains Mono, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`${currentTime.toFixed(2)}s / ${aspect}`, targetW - 72, 34);

  }, [currentTime, activeSlice, activeWord, activePhraseWords, aspect, audioTrack, viewMode]);

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
