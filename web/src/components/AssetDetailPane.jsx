import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
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
  Sparkles,
  MousePointerClick
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

export default function AssetDetailPane({ project, asset, onAssetUpdated }) {
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

  if (!asset) {
    return (
      <div className="glass-panel rounded-2xl p-5 border border-slate-800 h-full flex flex-col items-center justify-center text-center select-none">
        <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 text-slate-500 flex items-center justify-center mb-3">
          <MousePointerClick className="w-6 h-6 text-teal-400/60" />
        </div>
        <h3 className="text-sm font-bold text-slate-200">Source Inspector</h3>
        <p className="text-xs text-slate-400 max-w-xs mt-1">
          Click any photo or video in the Source Media pool to inspect AI tags, captions, relevance metrics, and trim points.
        </p>
      </div>
    );
  }

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
      const maxT = asset.duration_sec || (chartPoints.length > 0 ? chartPoints[chartPoints.length - 1]?.t : 99999) || 1;
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

      setStatusMessage('AI analysis & metadata saved.');
      if (onAssetUpdated) onAssetUpdated(updated);
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err) {
      setErrorMessage('Failed to save: ' + err.message);
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

  // Chart configuration
  const chartPoints = Array.isArray(frameScoresData?.frame_scores) ? frameScoresData.frame_scores : [];
  const chartLabels = chartPoints.map((p) => (p && typeof p.t === 'number' ? `${p.t.toFixed(0)}s` : '0s'));
  const maxDuration = asset.duration_sec || (chartPoints.length > 0 ? (chartPoints[chartPoints.length - 1]?.t || 1) : 1);

  const chartData = useMemo(() => ({
    labels: chartLabels,
    datasets: [
      {
        label: 'Composite (S_comp)',
        data: chartPoints.map((p) => (p && typeof p.s_comp === 'number' ? p.s_comp : 0)),
        borderColor: '#2dd4bf',
        backgroundColor: 'rgba(45, 212, 191, 0.15)',
        borderWidth: 1.5,
        tension: 0.3,
        fill: true,
        pointRadius: 0
      },
      {
        label: 'Relevance (S_rel)',
        data: chartPoints.map((p) => (p && typeof p.s_rel === 'number' ? p.s_rel : 0)),
        borderColor: '#38bdf8',
        backgroundColor: 'transparent',
        borderWidth: 1,
        borderDash: [3, 3],
        tension: 0.2,
        pointRadius: 0
      },
      {
        label: 'Aesthetic (S_aes)',
        data: chartPoints.map((p) => (p && typeof p.s_aes === 'number' ? p.s_aes : 0)),
        borderColor: '#fbbf24',
        backgroundColor: 'transparent',
        borderWidth: 1,
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
          font: { size: 9, family: 'monospace' },
          boxWidth: 8,
          padding: 4
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
        titleFont: { size: 10, family: 'monospace' },
        bodyFont: { size: 9, family: 'monospace' }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(51, 65, 85, 0.2)' },
        ticks: { color: '#64748b', font: { size: 8, family: 'monospace' }, maxTicksLimit: 8 }
      },
      y: {
        min: 0,
        max: 1.0,
        grid: { color: 'rgba(51, 65, 85, 0.2)' },
        ticks: { color: '#64748b', font: { size: 8, family: 'monospace' } }
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
      top: '20px',
      height: 'calc(100% - 40px)',
      transform: 'translateX(-50%)'
    };
  };

  return (
    <div className="glass-panel rounded-2xl p-4 border border-slate-800 h-full flex flex-col overflow-hidden">
      {/* Pane Title */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-800/80 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center shrink-0">
            {isVideo ? <Video className="w-3.5 h-3.5" /> : <ImageIcon className="w-3.5 h-3.5" />}
          </div>
          <div className="min-w-0">
            <h2 className="text-xs font-bold text-white uppercase tracking-wider truncate">
              Review Selected Media
            </h2>
            <p className="text-[10px] text-slate-400 truncate font-mono">
              {assetTitle}
            </p>
          </div>
        </div>

        <button
          onClick={handleReindex}
          disabled={isReindexing || isSaving}
          className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-cyan-300 border border-slate-700 px-2.5 py-1 rounded-lg text-[11px] font-semibold transition shrink-0"
          title="Re-run AI vision indexing"
        >
          <RotateCw className={`w-3 h-3 ${isReindexing ? 'animate-spin' : ''}`} />
          <span>{isReindexing ? 'Analyzing...' : 'Re-Index'}</span>
        </button>
      </div>

      {/* Feedback alerts */}
      {statusMessage && (
        <div className="mb-2 bg-teal-500/10 border border-teal-500/30 text-teal-300 text-[11px] px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 shrink-0">
          <CheckCircle2 className="w-3.5 h-3.5 text-teal-400 shrink-0" />
          <span className="truncate">{statusMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="mb-2 bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 shrink-0">
          <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
          <span className="truncate">{errorMessage}</span>
        </div>
      )}

      {/* Scrollable Content Body */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-3">
        {/* Media Player / Preview */}
        <div className="w-full h-44 bg-slate-950 rounded-xl overflow-hidden border border-slate-800 flex items-center justify-center relative shrink-0">
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
          <div className="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-black/70 backdrop-blur-sm text-[9px] font-mono text-slate-300 uppercase">
            {asset.media_type} {asset.width && asset.height ? `• ${asset.width}x${asset.height}` : ''}
          </div>
        </div>

        {/* Video Score Timeline Graph RIGHT UNDER THE VIDEO */}
        {isVideo && (
          <div className="bg-slate-950 p-2.5 rounded-xl border border-slate-800 space-y-1.5 shrink-0">
            <div className="flex items-center justify-between text-[11px] font-bold text-white">
              <span className="flex items-center gap-1 text-[10px] uppercase font-bold text-slate-300">
                <Activity className="w-3.5 h-3.5 text-cyan-400" />
                Score Timeline (Click to Seek)
              </span>
              <span className="text-[9px] font-mono text-rose-400 bg-rose-500/10 px-1.5 py-0.5 rounded border border-rose-500/20 font-bold">
                ▶ {currentTime.toFixed(1)}s / {maxDuration.toFixed(1)}s
              </span>
            </div>

            <div
              className="h-32 relative select-none cursor-crosshair group overflow-hidden"
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
                    <div className="w-[2px] h-full bg-rose-500 shadow-[0_0_10px_#f43f5e] relative">
                      {/* Top Handle */}
                      <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-rose-500 border border-white shadow-md flex items-center justify-center">
                        <div className="w-1 h-1 rounded-full bg-white" />
                      </div>

                      {/* Floating Time Pill */}
                      <div className="absolute -top-5 left-1/2 -translate-x-1/2 px-1 py-0.5 rounded bg-slate-950/95 border border-rose-500 text-[8px] font-mono font-bold text-rose-300 shadow-xl whitespace-nowrap">
                        {currentTime.toFixed(1)}s
                      </div>

                      {/* Bottom Pin */}
                      <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-rose-500 border border-white" />
                    </div>
                  </div>
                </>
              ) : (
                <div className="h-full flex items-center justify-center text-[10px] text-slate-500 font-mono">
                  {isLoadingScores ? 'Loading scores...' : 'No frame score curve available.'}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Dual Relevance Scores */}
        <div className="grid grid-cols-2 gap-2">
          <div className={`p-2 rounded-lg border ${asset.is_indexed ? ((asset.relevance_score_daily || 0) > 0.7 ? 'bg-teal-500/10 border-teal-500/30' : (asset.relevance_score_daily || 0) > 0.4 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-rose-500/10 border-rose-500/30') : 'bg-slate-900 border-slate-800'}`}>
            <span className="text-[9px] text-slate-400 block font-semibold uppercase tracking-wider">Day Relevance</span>
            <strong className={`text-base font-bold ${asset.is_indexed ? ((asset.relevance_score_daily || 0) > 0.7 ? 'text-teal-400' : (asset.relevance_score_daily || 0) > 0.4 ? 'text-amber-400' : 'text-rose-400') : 'text-slate-500'}`}>
              {asset.is_indexed ? `${Math.round((asset.relevance_score_daily || 0) * 100)}%` : 'N/A'}
            </strong>
          </div>
          <div className={`p-2 rounded-lg border ${asset.is_indexed ? ((asset.relevance_score_overall || 0) > 0.7 ? 'bg-purple-500/10 border-purple-500/30' : (asset.relevance_score_overall || 0) > 0.4 ? 'bg-amber-500/10 border-amber-500/30' : 'bg-rose-500/10 border-rose-500/30') : 'bg-slate-900 border-slate-800'}`}>
            <span className="text-[9px] text-slate-400 block font-semibold uppercase tracking-wider">Trip Narrative</span>
            <strong className={`text-base font-bold ${asset.is_indexed ? ((asset.relevance_score_overall || 0) > 0.7 ? 'text-purple-400' : (asset.relevance_score_overall || 0) > 0.4 ? 'text-amber-400' : 'text-rose-400') : 'text-slate-500'}`}>
              {asset.is_indexed ? `${Math.round((asset.relevance_score_overall || 0) * 100)}%` : 'N/A'}
            </strong>
          </div>
        </div>

        {/* AI Caption & Concept */}
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider">
            AI Caption & Lyric Match Concept
          </label>
          <textarea
            rows={2}
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Scene description..."
            className="w-full bg-slate-950 border border-slate-700 rounded-lg p-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono leading-relaxed"
          />
        </div>

        {/* Quality Score Slider */}
        <div className="space-y-1 bg-slate-950 p-2.5 rounded-xl border border-slate-800">
          <div className="flex justify-between items-center text-xs">
            <span className="font-bold text-slate-300 flex items-center gap-1 text-[11px]">
              <Star className="w-3 h-3 text-amber-400 fill-current" />
              Cinematic Score
            </span>
            <span className="font-mono text-teal-400 font-bold text-xs">
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
        </div>

        {/* Tags */}
        <div className="space-y-1">
          <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1">
            <Tag className="w-3 h-3 text-teal-400" />
            Tags
          </label>
          <input
            type="text"
            value={tagsText}
            onChange={(e) => setTagsText(e.target.value)}
            placeholder="sunset, beach, nature"
            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 font-mono"
          />
        </div>

        {/* Active Toggle & Save Button */}
        <div className="flex items-center justify-between pt-1">
          <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="rounded border-slate-700 text-teal-500 w-3.5 h-3.5"
            />
            <span className="text-[11px]">Include in video</span>
          </label>

          <button
            onClick={handleSave}
            disabled={isSaving || isReindexing}
            className="flex items-center gap-1 px-3.5 py-1.5 rounded-lg text-xs font-bold bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 transition shadow-md shadow-teal-500/20"
          >
            <Save className="w-3.5 h-3.5" />
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>

        {/* Subsegments (if available) */}
        {isVideo && segments.length > 0 && (
          <div className="pt-2 border-t border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-[11px] font-bold text-white">
              <span className="flex items-center gap-1 text-[10px] uppercase font-bold text-slate-300">
                <Layers className="w-3.5 h-3.5 text-purple-400" />
                Subsegments ({segments.length})
              </span>
            </div>
            <div className="space-y-1.5">
              {segments.map((seg, idx) => (
                <div
                  key={seg.id || idx}
                  onClick={() => jumpToSecond(seg.best_shot_start || seg.start_time || 0)}
                  className="bg-slate-950 p-2 rounded-lg border border-slate-800 hover:border-teal-500/40 cursor-pointer transition text-[10px] font-mono flex items-center justify-between"
                  title="Click to seek video to this segment"
                >
                  <span className="font-semibold text-slate-200">
                    #{idx + 1} ({(seg.start_time || 0).toFixed(1)}s – {(seg.end_time || 0).toFixed(1)}s)
                  </span>
                  <span className="text-teal-400 bg-teal-500/10 px-1.5 py-0.5 rounded border border-teal-500/30 font-bold">
                    ★ {(seg.motion_score || 0).toFixed(2)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
