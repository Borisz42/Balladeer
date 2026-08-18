import React, { useState, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  Star,
  Tag,
  Clock,
  Cpu,
  Save,
  RotateCw,
  CheckCircle2,
  AlertCircle,
  Image as ImageIcon,
  Video,
  Film,
  Activity,
  Layers,
  Sparkles
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { updateAsset, reindexAsset, fetchAssetSegments, fetchAssetFrameScores } from '../api';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function AssetDetailModal({ isOpen, onClose, project, asset, onAssetUpdated }) {
  const [caption, setCaption] = useState('');
  const [tagsText, setTagsText] = useState('');
  const [qualityScore, setQualityScore] = useState(7.0);
  const [isActive, setIsActive] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isReindexing, setIsReindexing] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  // Video Analytics state & playhead tracking
  const [segments, setSegments] = useState([]);
  const [frameScoresData, setFrameScoresData] = useState(null);
  const [isLoadingScores, setIsLoadingScores] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isScrubbing, setIsScrubbing] = useState(false);

  const videoRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (asset) {
      setCaption(asset.caption || '');
      setTagsText(asset.tags ? asset.tags.join(', ') : '');
      setQualityScore(typeof asset.quality_score === 'number' ? asset.quality_score : 7.0);
      setIsActive(asset.is_active !== undefined ? asset.is_active : true);
      setStatusMessage(null);
      setErrorMessage(null);
      setCurrentTime(0);

      if (asset.media_type === 'video' && project?.id) {
        setIsLoadingScores(true);
        Promise.all([
          fetchAssetSegments(project.id, asset.id).catch(() => []),
          fetchAssetFrameScores(project.id, asset.id).catch(() => null)
        ])
          .then(([segs, scoresObj]) => {
            setSegments(segs || []);
            setFrameScoresData(scoresObj);
          })
          .finally(() => {
            setIsLoadingScores(false);
          });
      } else {
        setSegments([]);
        setFrameScoresData(null);
      }
    }
  }, [asset, project?.id]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !asset) return null;

  const isVideo = asset.media_type === 'video';
  const fileUrl = `http://localhost:8000/api/projects/${project?.id}/assets/${asset.id}/file`;
  const thumbUrl = `http://localhost:8000/api/projects/${project?.id}/assets/${asset.id}/thumbnail`;

  const assetTitle = (asset.file_path && typeof asset.file_path === 'string')
    ? (asset.file_path.split(/[\\/]/).pop() || asset.file_path)
    : (asset.caption || asset.id || 'Media Asset');

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const jumpToSecond = (targetSec) => {
    if (videoRef.current) {
      const maxT = asset.duration_sec || (chartPoints.length > 0 ? (chartPoints[chartPoints.length - 1]?.t || 1) : 99999) || 1;
      const clamped = Math.max(0, Math.min(targetSec, maxT));
      videoRef.current.currentTime = clamped;
      setCurrentTime(clamped);
    }
  };

  const handleSave = async () => {
    if (!project?.id) return;
    setIsSaving(true);
    setErrorMessage(null);
    try {
      const parsedTags = tagsText
        .split(',')
        .map((t) => t.trim().replace(/^#/, ''))
        .filter(Boolean);

      const updated = await updateAsset(project.id, asset.id, {
        caption: caption.trim(),
        tags: parsedTags,
        quality_score: parseFloat(qualityScore) || 7.0,
        is_active: isActive
      });

      setStatusMessage('AI analysis and caption successfully updated in database.');
      if (onAssetUpdated) onAssetUpdated(updated);
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err) {
      setErrorMessage('Failed to save changes: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReindex = async () => {
    if (!project?.id) return;
    setIsReindexing(true);
    setErrorMessage(null);
    try {
      const updated = await reindexAsset(project.id, asset.id);
      setCaption(updated.caption || '');
      setTagsText(updated.tags ? updated.tags.join(', ') : '');
      setQualityScore(typeof updated.quality_score === 'number' ? updated.quality_score : 7.0);
      setStatusMessage(`Re-indexed with ${updated.indexed_by_model || 'AI'}!`);
      if (onAssetUpdated) onAssetUpdated(updated);

      if (isVideo) {
        const [segs, scoresObj] = await Promise.all([
          fetchAssetSegments(project.id, asset.id).catch(() => []),
          fetchAssetFrameScores(project.id, asset.id).catch(() => null)
        ]);
        setSegments(segs || []);
        setFrameScoresData(scoresObj);
      }

      setTimeout(() => setStatusMessage(null), 4000);
    } catch (err) {
      setErrorMessage('Re-indexing failed: ' + err.message);
    } finally {
      setIsReindexing(false);
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return 'Unknown';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoString;
    }
  };

  // Chart configuration
  const chartPoints = Array.isArray(frameScoresData?.frame_scores) ? frameScoresData.frame_scores : [];
  const chartLabels = chartPoints.map((p) => (p && typeof p.t === 'number' ? `${p.t.toFixed(0)}s` : '0s'));
  const maxDuration = asset.duration_sec || (chartPoints.length > 0 ? (chartPoints[chartPoints.length - 1]?.t || 1) : 1);

  const chartData = useMemo(() => ({
    labels: chartLabels,
    datasets: [
      {
        label: 'Composite Score (S_comp)',
        data: chartPoints.map((p) => (p && typeof p.s_comp === 'number' ? p.s_comp : 0)),
        borderColor: '#2dd4bf',
        backgroundColor: 'rgba(45, 212, 191, 0.15)',
        borderWidth: 2,
        tension: 0.3,
        fill: true,
        pointRadius: chartPoints.length > 30 ? 0 : 3,
        pointHoverRadius: 5
      },
      {
        label: 'Relevance (S_rel)',
        data: chartPoints.map((p) => (p && typeof p.s_rel === 'number' ? p.s_rel : 0)),
        borderColor: '#38bdf8',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [4, 4],
        tension: 0.2,
        pointRadius: 0
      },
      {
        label: 'Aesthetic & Sharpness (S_aes)',
        data: chartPoints.map((p) => (p && typeof p.s_aes === 'number' ? p.s_aes : 0)),
        borderColor: '#fbbf24',
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        borderDash: [2, 2],
        tension: 0.2,
        pointRadius: 0
      }
    ]
  }), [chartPoints, chartLabels]);

  const chartOptions = useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#94a3b8',
          font: { size: 10, family: 'monospace' },
          boxWidth: 12,
          padding: 8
        }
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        titleColor: '#f8fafc',
        bodyColor: '#cbd5e1',
        borderColor: '#334155',
        borderWidth: 1,
        titleFont: { size: 11, family: 'monospace' },
        bodyFont: { size: 10, family: 'monospace' }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(51, 65, 85, 0.25)' },
        ticks: { color: '#64748b', font: { size: 9, family: 'monospace' }, maxTicksLimit: 12 }
      },
      y: {
        min: 0,
        max: 1.0,
        grid: { color: 'rgba(51, 65, 85, 0.25)' },
        ticks: { color: '#64748b', font: { size: 9, family: 'monospace' } }
      }
    }
  }), []);

  const seekFromChartEvent = (e) => {
    if (!videoRef.current || chartPoints.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const chart = chartRef.current;
    const chartArea = chart?.chartArea;
    const left = chartArea?.left ?? 36;
    const right = chartArea?.right ?? (rect.width - 12);

    if (clickX >= left && clickX <= right) {
      const progress = (clickX - left) / (right - left);
      const targetTime = Math.max(0, Math.min(progress * maxDuration, maxDuration));
      videoRef.current.currentTime = targetTime;
      setCurrentTime(targetTime);
    }
  };

  const getPlayheadStyle = () => {
    const chart = chartRef.current;
    const clampedTime = Math.min(Math.max(currentTime, 0), maxDuration);
    const progress = maxDuration > 0 ? clampedTime / maxDuration : 0;

    if (chart && chart.chartArea) {
      const { left, right, top, bottom } = chart.chartArea;
      const pixelX = left + progress * (right - left);
      return {
        left: `${pixelX}px`,
        top: `${top}px`,
        height: `${bottom - top}px`,
        transform: 'translateX(-50%)'
      };
    }

    return {
      left: `calc(36px + ${progress} * (100% - 48px))`,
      top: '28px',
      height: 'calc(100% - 48px)',
      transform: 'translateX(-50%)'
    };
  };

  return createPortal(
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/85 backdrop-blur-md p-4"
      onClick={onClose}
    >
      <div 
        className="glass-panel w-full max-w-5xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative max-h-[92vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Title */}
        <div className="flex items-center gap-3 mb-4 pb-3 border-b border-slate-800">
          <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center">
            {isVideo ? <Video className="w-4 h-4" /> : <ImageIcon className="w-4 h-4" />}
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Media Asset Inspector & AI Editor</h2>
            <p className="text-xs text-slate-400 truncate max-w-md font-mono">
              {assetTitle}
            </p>
          </div>
        </div>

        {/* Feedback alerts */}
        {statusMessage && (
          <div className="mb-4 bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs px-3.5 py-2.5 rounded-xl flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
            <span>{statusMessage}</span>
          </div>
        )}

        {errorMessage && (
          <div className="mb-4 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs px-3.5 py-2.5 rounded-xl flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Media Preview, Interactive Timeline Graph & Technical Stats */}
          <div className="lg:col-span-6 flex flex-col space-y-4">
            {/* Video or Image Preview */}
            <div className="w-full h-64 sm:h-72 bg-slate-950 rounded-xl overflow-hidden border border-slate-800 flex items-center justify-center relative">
              {isVideo ? (
                <video
                  ref={videoRef}
                  controls
                  className="w-full h-full object-contain"
                  src={fileUrl}
                  poster={thumbUrl}
                  onTimeUpdate={handleTimeUpdate}
                  onSeeking={handleTimeUpdate}
                  onSeeked={handleTimeUpdate}
                />
              ) : (
                <img
                  src={fileUrl}
                  alt={caption || assetTitle}
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    e.target.src = thumbUrl;
                  }}
                />
              )}
              
              <div className="absolute top-2 left-2 px-2 py-0.5 rounded bg-black/70 backdrop-blur-sm text-[10px] font-mono text-slate-300 uppercase">
                {asset.media_type} {asset.width && asset.height ? `• ${asset.width}x${asset.height}` : ''}
              </div>
            </div>

            {/* Video Score Timeline Graph DIRECTLY UNDER THE VIDEO */}
            {isVideo && (
              <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <Activity className="w-4 h-4 text-cyan-400" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      Timeline Scores (Click to Seek)
                    </h3>
                  </div>
                  <span className="text-[10px] font-mono text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20 font-bold">
                    ▶ {currentTime.toFixed(1)}s / {maxDuration.toFixed(1)}s
                  </span>
                </div>

                <div
                  className="h-44 relative select-none cursor-crosshair group overflow-hidden"
                  onClick={seekFromChartEvent}
                  onMouseDown={(e) => {
                    setIsScrubbing(true);
                    seekFromChartEvent(e);
                  }}
                  onMouseMove={(e) => {
                    if (isScrubbing) seekFromChartEvent(e);
                  }}
                  onMouseUp={() => setIsScrubbing(false)}
                  onMouseLeave={() => setIsScrubbing(false)}
                  title="Click or drag anywhere on graph to jump to that second in video"
                >
                  {chartPoints.length > 0 ? (
                    <>
                      <Line
                        ref={chartRef}
                        data={chartData}
                        options={chartOptions}
                      />

                      {/* Visible Overlay Playhead Marker */}
                      <div
                        className="absolute pointer-events-none z-20"
                        style={getPlayheadStyle()}
                      >
                        {/* Vertical Scrubber Bar with Glow */}
                        <div className="w-[2px] h-full bg-rose-500 shadow-[0_0_12px_#f43f5e] relative">
                          {/* Top Circular Scrubber Handle */}
                          <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-rose-500 border-2 border-white shadow-md flex items-center justify-center">
                            <div className="w-1 h-1 rounded-full bg-white" />
                          </div>

                          {/* Floating Timestamp Pin */}
                          <div className="absolute -top-6 left-1/2 -translate-x-1/2 px-1.5 py-0.5 rounded bg-slate-950/95 border border-rose-500 text-[9px] font-mono font-bold text-rose-300 shadow-xl whitespace-nowrap">
                            {currentTime.toFixed(1)}s
                          </div>

                          {/* Bottom Pin */}
                          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-rose-500 border border-white" />
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="h-full flex items-center justify-center text-xs text-slate-500 font-mono">
                      {isLoadingScores ? 'Loading frame-by-frame scores...' : 'No frame score curve available. Re-index to compute.'}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Technical Metadata */}
            <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 text-[11px] font-mono text-slate-400 space-y-1.5">
              <div className="flex justify-between">
                <span>Capture Timestamp:</span>
                <span className="text-slate-200">{formatTime(asset.capture_time)}</span>
              </div>
              {isVideo && (
                <div className="flex justify-between">
                  <span>Video Duration:</span>
                  <span className="text-cyan-400 font-bold">{(asset.duration_sec || 0).toFixed(1)} seconds</span>
                </div>
              )}
              <div className="flex justify-between">
                <span>Indexed Status:</span>
                <span className={asset.is_indexed ? 'text-teal-400 font-bold' : 'text-amber-400 font-bold'}>
                  {asset.is_indexed ? 'Indexed with SigLIP 2 + VLM' : 'Pending AI Analysis'}
                </span>
              </div>
            </div>
          </div>

          {/* Right: AI Understanding & User Edit Controls */}
          <div className="lg:col-span-6 space-y-4">
            {/* Dual Relevance Scores (Prominent) */}
            <div className="grid grid-cols-2 gap-3 mb-2">
              <div className={`p-3 rounded-xl border ${asset.is_indexed ? ((asset.relevance_score_daily || 0) > 0.7 ? 'bg-teal-500/10 border-teal-500/30' : (asset.relevance_score_daily || 0) > 0.4 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-rose-500/10 border-rose-500/30') : 'bg-slate-800/50 border-slate-700/50'}`}>
                <span className="text-[10px] text-slate-400 block font-semibold uppercase tracking-wider mb-1">Matched Day Relevance</span>
                <div className="flex items-end gap-2">
                  <strong className={`text-2xl font-bold ${asset.is_indexed ? ((asset.relevance_score_daily || 0) > 0.7 ? 'text-teal-400' : (asset.relevance_score_daily || 0) > 0.4 ? 'text-amber-400' : 'text-rose-400') : 'text-slate-500'}`}>
                    {asset.is_indexed ? `${Math.round((asset.relevance_score_daily || 0) * 100)}%` : 'N/A'}
                  </strong>
                </div>
              </div>
              <div className={`p-3 rounded-xl border ${asset.is_indexed ? ((asset.relevance_score_overall || 0) > 0.7 ? 'bg-purple-500/10 border-purple-500/30' : (asset.relevance_score_overall || 0) > 0.4 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-rose-500/10 border-rose-500/30') : 'bg-slate-800/50 border-slate-700/50'}`}>
                <span className="text-[10px] text-slate-400 block font-semibold uppercase tracking-wider mb-1">Full Trip Narrative</span>
                <div className="flex items-end gap-2">
                  <strong className={`text-2xl font-bold ${asset.is_indexed ? ((asset.relevance_score_overall || 0) > 0.7 ? 'text-purple-400' : (asset.relevance_score_overall || 0) > 0.4 ? 'text-amber-400' : 'text-rose-400') : 'text-slate-500'}`}>
                    {asset.is_indexed ? `${Math.round((asset.relevance_score_overall || 0) * 100)}%` : 'N/A'}
                  </strong>
                </div>
              </div>
            </div>

            {/* Model Attribution Badge */}
            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-teal-400" />
                <div>
                  <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-mono">
                    AI Vision Model Used
                  </span>
                  <strong className="text-xs font-bold text-white uppercase font-mono">
                    {asset.indexed_by_model || (asset.is_indexed ? 'SigLIP 2 + Qwen3.5-4B' : 'Not Yet Indexed')}
                  </strong>
                </div>
              </div>

              <button
                onClick={handleReindex}
                disabled={isReindexing || isSaving}
                className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-cyan-300 border border-slate-700 px-3 py-1 rounded-lg text-xs font-semibold transition"
                title="Re-run SigLIP 2 scoring & VLM prompt on this asset"
              >
                <RotateCw className={`w-3.5 h-3.5 ${isReindexing ? 'animate-spin' : ''}`} />
                {isReindexing ? 'Analyzing...' : 'Re-Index AI'}
              </button>
            </div>

            {/* AI Caption & Description */}
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Scene Caption & Lyric Matching Concept
              </label>
              <textarea
                rows={3}
                value={caption}
                onChange={(e) => setCaption(e.target.value)}
                placeholder="Describe the mood, subject, and action in this scene..."
                className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono leading-relaxed"
              />
            </div>

            {/* Quality Score Slider */}
            <div className="space-y-1.5 bg-slate-950 p-3 rounded-xl border border-slate-800">
              <div className="flex justify-between items-center text-xs">
                <span className="font-bold text-slate-300 flex items-center gap-1">
                  <Star className="w-3.5 h-3.5 text-amber-400 fill-current" />
                  Cinematic Quality Score
                </span>
                <span className="font-mono text-teal-400 font-bold text-sm">
                  {(typeof qualityScore === 'number' && !isNaN(qualityScore) ? qualityScore : 7.0).toFixed(1)} / 10.0
                </span>
              </div>
              <input
                type="range"
                min={1.0}
                max={10.0}
                step={0.1}
                value={typeof qualityScore === 'number' && !isNaN(qualityScore) ? qualityScore : 7.0}
                onChange={(e) => setQualityScore(parseFloat(e.target.value) || 7.0)}
                className="w-full accent-teal-500"
              />
              <p className="text-[10px] text-slate-500">
                Higher scores prioritize placement during key musical chorus and climax moments.
              </p>
            </div>

            {/* AI Tags */}
            <div className="space-y-1">
              <label className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
                <Tag className="w-3.5 h-3.5 text-teal-400" />
                Descriptive Tags (Comma-separated)
              </label>
              <input
                type="text"
                value={tagsText}
                onChange={(e) => setTagsText(e.target.value)}
                placeholder="sunset, beach, travel, happiness, nature"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
              />
            </div>

            {/* Active Switch */}
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="rounded border-slate-700 text-teal-500 w-4 h-4"
              />
              <span>Include this asset in the montage video</span>
            </label>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
              >
                Close
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving || isReindexing}
                className="flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-bold bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 transition shadow-lg shadow-teal-500/20"
              >
                <Save className="w-3.5 h-3.5" />
                {isSaving ? 'Saving...' : 'Save AI Changes'}
              </button>
            </div>
          </div>
        </div>

        {/* Visual Subsegments & Best Shot Windows (Full Width at Bottom) */}
        {isVideo && segments.length > 0 && (
          <div className="mt-6 pt-6 border-t border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-purple-400" />
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Visual Similarity Subsegments & Best Shot Windows
                </h4>
              </div>
              <span className="text-[10px] text-slate-400 font-mono">
                Click any segment to seek video
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {segments.map((seg, idx) => (
                <div
                  key={seg.id || idx}
                  onClick={() => jumpToSecond(seg.best_shot_start || seg.start_time || 0)}
                  className="bg-slate-950 p-3 rounded-xl border border-slate-800 hover:border-teal-500/50 cursor-pointer transition flex flex-col justify-between text-xs font-mono space-y-2 group"
                  title="Click to seek video to this segment"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white group-hover:text-teal-300 transition">
                      Segment #{idx + 1} ({(seg.start_time || 0).toFixed(1)}s – {(seg.end_time || 0).toFixed(1)}s)
                    </span>
                    <span className="px-2 py-0.5 rounded bg-teal-500/20 border border-teal-500/40 text-teal-300 text-[10px] font-bold">
                      Score: {(seg.motion_score || 0).toFixed(2)}
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-400 line-clamp-1">
                    {seg.description || 'Action Scene'}
                  </p>

                  <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-slate-800/80">
                    <span className="text-slate-400 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-amber-400" />
                      Best Shot Window:
                    </span>
                    <span className="font-bold text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                      {seg.best_shot_start ? `${seg.best_shot_start.toFixed(1)}s – ${seg.best_shot_end.toFixed(1)}s` : `${(seg.start_time || 0).toFixed(1)}s – ${(seg.end_time || 0).toFixed(1)}s`}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
