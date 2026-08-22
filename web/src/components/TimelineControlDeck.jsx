import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Sliders,
  Palette,
  Type,
  AlignLeft,
  Volume2,
  Clock,
  Layers,
  Wand2,
  Check,
  RotateCcw,
  Tag,
  Maximize,
  Compass,
  Film,
  Eye,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  RefreshCw,
  Zap,
  Play,
  Flame
} from 'lucide-react';

export default function TimelineControlDeck({
  project,
  audioTrack,
  slices = [],
  currentTime = 0,
  onUpdateControls,
  onBulkApply,
  onSolveTimeline,
  onUpdateSliceCaption,
  isSolving = false
}) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [activeTab, setActiveTab] = useState('vfx'); // 'vfx' | 'lyrics' | 'overlays' | 'pacing' | 'tools'
  const [saveToast, setSaveToast] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  // Read existing configurations from project.config_override
  const config = project?.config_override || {};
  const vFx = config.video_effects || {};
  const lStyle = config.lyrics_style || {};
  const tOverlays = config.text_overlays || {};
  const pRules = config.pacing_rules || {};
  const aMaster = config.audio_mastering || {};
  const vConfig = config.video || {};

  // Local state for VFX
  const [aspectRatio, setAspectRatio] = useState('16:9');
  const [bgMode, setBgMode] = useState('blurred_fill');
  const [blurRadius, setBlurRadius] = useState(25);
  const [blurScale, setBlurScale] = useState(1.25);
  const [enableKenBurns, setEnableKenBurns] = useState(true);
  const [kenBurnsZoom, setKenBurnsZoom] = useState(1.2);
  const [colorFilter, setColorFilter] = useState('natural');
  const [enableVignette, setEnableVignette] = useState(false);

  // Local state for Lyrics & Subtitles (STRICT MUTUAL EXCLUSIVITY: 'karaoke_lyrics' | 'narrative_descriptions' | 'chapter_event_cards' | 'hidden')
  const [subtitleMode, setSubtitleMode] = useState('karaoke_lyrics');
  const [fontFamily, setFontFamily] = useState('Inter');
  const [fontSize, setFontSize] = useState(46);
  const [highlightColor, setHighlightColor] = useState('#2dd4bf');
  const [baseColor, setBaseColor] = useState('#ffffff');
  const [outlineColor, setOutlineColor] = useState('#000000');
  const [outlineWidth, setOutlineWidth] = useState(3);
  const [alignment, setAlignment] = useState(2); // 2=bottom, 5=center, 8=top

  // Local state for Titles & Overlays
  const [introEnabled, setIntroEnabled] = useState(true);
  const [introTitle, setIntroTitle] = useState('');
  const [introSubtitle, setIntroSubtitle] = useState('');
  const [introDuration, setIntroDuration] = useState(3.5);
  const [watermarkText, setWatermarkText] = useState('');
  const [watermarkOpacity, setWatermarkOpacity] = useState(80);
  const [showLocationBadge, setShowLocationBadge] = useState(true);
  const [outroText, setOutroText] = useState('Created with Balladeer 🎶');

  // Local state for Pacing & Rules
  const [pacingPreset, setPacingPreset] = useState('balanced');
  const [photoMinBeats, setPhotoMinBeats] = useState(1);
  const [photoMaxBeats, setPhotoMaxBeats] = useState(3);
  const [videoMinBeats, setVideoMinBeats] = useState(2);
  const [videoMaxBeats, setVideoMaxBeats] = useState(5);
  const [transitionStyle, setTransitionStyle] = useState('hard_cut');
  const [motionBoost, setMotionBoost] = useState(true);

  // Local state for Master Audio
  const [lufsTarget, setLufsTarget] = useState(-14);
  const [fadeInSec, setFadeInSec] = useState(0.5);
  const [fadeOutSec, setFadeOutSec] = useState(1.5);

  // Local scene captions state
  const [localCaptions, setLocalCaptions] = useState({});

  // Sync state when project changes and not currently dirty
  useEffect(() => {
    if (!project) return;
    const cfg = project.config_override || {};
    const vf = cfg.video_effects || {};
    const ls = cfg.lyrics_style || {};
    const to = cfg.text_overlays || {};
    const pr = cfg.pacing_rules || {};
    const am = cfg.audio_mastering || {};
    const vc = cfg.video || {};

    setAspectRatio(vc.aspect_ratio || cfg.aspect_ratio || '16:9');
    setBgMode(vf.default_bg_mode || vc.default_bg_mode || 'blurred_fill');
    setBlurRadius(vf.blur_radius !== undefined ? vf.blur_radius : 25);
    setBlurScale(vf.blur_scale !== undefined ? vf.blur_scale : 1.25);
    setEnableKenBurns(vf.enable_ken_burns !== undefined ? vf.enable_ken_burns : true);
    setKenBurnsZoom(vf.ken_burns_zoom !== undefined ? vf.ken_burns_zoom : 1.2);
    setColorFilter(vf.color_filter || 'natural');
    setEnableVignette(vf.enable_vignette || false);

    // Subtitle mode
    const rawSubMode = ls.subtitle_mode;
    if (rawSubMode && rawSubMode !== 'auto') {
      setSubtitleMode(rawSubMode);
    } else {
      setSubtitleMode('karaoke_lyrics');
    }

    setFontFamily(ls.font_family || 'Inter');
    setFontSize(ls.font_size !== undefined ? ls.font_size : 46);
    setHighlightColor(ls.highlight_color || '#2dd4bf');
    setBaseColor(ls.base_color || '#ffffff');
    setOutlineColor(ls.outline_color || '#000000');
    setOutlineWidth(ls.outline_width !== undefined ? ls.outline_width : 3);
    setAlignment(ls.alignment !== undefined ? ls.alignment : 2);

    setIntroEnabled(to.intro_enabled !== undefined ? to.intro_enabled : true);
    setIntroTitle(to.intro_title !== undefined ? to.intro_title : (project.title || ''));
    setIntroSubtitle(to.intro_subtitle || '');
    setIntroDuration(to.intro_duration !== undefined ? to.intro_duration : 3.5);
    setWatermarkText(to.watermark_text || '');
    setWatermarkOpacity(to.watermark_opacity !== undefined ? to.watermark_opacity : 80);
    setShowLocationBadge(to.show_location_badge !== undefined ? to.show_location_badge : true);
    setOutroText(to.outro_text || 'Created with Balladeer 🎶');

    setPacingPreset(pr.pacing_preset || 'balanced');
    setPhotoMinBeats(pr.photo_beat_range ? pr.photo_beat_range[0] : 1);
    setPhotoMaxBeats(pr.photo_beat_range ? pr.photo_beat_range[1] : 3);
    setVideoMinBeats(pr.video_beat_range ? pr.video_beat_range[0] : 2);
    setVideoMaxBeats(pr.video_beat_range ? pr.video_beat_range[1] : 5);
    setTransitionStyle(pr.transition_style || 'hard_cut');
    setMotionBoost(pr.motion_boost !== undefined ? pr.motion_boost : true);

    setLufsTarget(am.lufs_target !== undefined ? am.lufs_target : -14);
    setFadeInSec(am.fade_in_sec !== undefined ? am.fade_in_sec : 0.5);
    setFadeOutSec(am.fade_out_sec !== undefined ? am.fade_out_sec : 1.5);
    setIsDirty(false);
  }, [project?.id, project?.config_override]);

  // Handle Big Apply Action (ONLY saves and triggers re-render when pushed!)
  const handleApplyAllChanges = async () => {
    setIsApplying(true);
    const updatedPayload = {
      video_effects: {
        default_bg_mode: bgMode,
        blur_radius: blurRadius,
        blur_scale: blurScale,
        enable_ken_burns: enableKenBurns,
        ken_burns_zoom: kenBurnsZoom,
        color_filter: colorFilter,
        enable_vignette: enableVignette
      },
      lyrics_style: {
        subtitle_mode: subtitleMode,
        font_family: fontFamily,
        font_size: fontSize,
        highlight_color: highlightColor,
        base_color: baseColor,
        outline_color: outlineColor,
        outline_width: outlineWidth,
        alignment: alignment
      },
      text_overlays: {
        intro_enabled: introEnabled,
        intro_title: introTitle,
        intro_subtitle: introSubtitle,
        intro_duration: introDuration,
        watermark_text: watermarkText,
        watermark_opacity: watermarkOpacity,
        show_location_badge: showLocationBadge,
        outro_text: outroText
      },
      pacing_rules: {
        pacing_preset: pacingPreset,
        photo_beat_range: [photoMinBeats, photoMaxBeats],
        video_beat_range: [videoMinBeats, videoMaxBeats],
        transition_style: transitionStyle,
        motion_boost: motionBoost
      },
      audio_mastering: {
        lufs_target: lufsTarget,
        fade_in_sec: fadeInSec,
        fade_out_sec: fadeOutSec
      },
      video: {
        aspect_ratio: aspectRatio,
        default_bg_mode: bgMode,
        enable_ken_burns: enableKenBurns,
        photo_beat_range: [photoMinBeats, photoMaxBeats],
        video_beat_range: [videoMinBeats, videoMaxBeats]
      }
    };

    // Save pending local scene captions if any were edited
    if (Object.keys(localCaptions).length > 0 && onBulkApply) {
      await onBulkApply({ action: 'set_custom_captions', captions_map: localCaptions });
      setLocalCaptions({});
    }

    if (onUpdateControls) {
      await onUpdateControls(updatedPayload);
      setIsDirty(false);
      setSaveToast(true);
      setTimeout(() => setSaveToast(false), 3000);
    }
    setIsApplying(false);
  };

  const handlePacingPresetSelect = (preset) => {
    setPacingPreset(preset);
    let pMin = 1, pMax = 3, vMin = 2, vMax = 5;
    if (preset === 'fast') {
      pMin = 1; pMax = 2; vMin = 2; vMax = 4;
    } else if (preset === 'cinematic') {
      pMin = 3; pMax = 6; vMin = 4; vMax = 8;
    }
    setPhotoMinBeats(pMin);
    setPhotoMaxBeats(pMax);
    setVideoMinBeats(vMin);
    setVideoMaxBeats(vMax);
    setIsDirty(true);
  };

  const handleLocalCaptionChange = (sliceId, text) => {
    setLocalCaptions((prev) => ({ ...prev, [sliceId]: text }));
    setIsDirty(true);
  };

  const handleBulkFillAiCaptions = async () => {
    if (slices.length === 0) return;
    const map = {};
    slices.forEach((s) => {
      if (s.asset && s.asset.caption) {
        map[s.id] = s.asset.caption;
      }
    });
    setLocalCaptions((prev) => ({ ...prev, ...map }));
    setIsDirty(true);
  };

  return (
    <div className="bg-slate-900/95 border-t border-slate-800 rounded-b-2xl flex flex-col shrink-0 text-slate-200 overflow-hidden shadow-2xl transition-all">
      {/* Module Header Bar with Active Badges, Unsaved Changes Indicator & Big Apply Button */}
      <div className="px-4 py-2 bg-slate-950/90 border-b border-slate-800 flex items-center justify-between gap-3 select-none shrink-0 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center shadow-md shadow-teal-500/10">
              <Sliders className="w-3.5 h-3.5" />
            </div>
            <h3 className="text-xs font-bold text-white tracking-wide uppercase truncate">
              Timeline & Video Control Deck
            </h3>
          </div>

          {/* Quick Config Badges */}
          <div className="hidden md:flex items-center gap-1.5 font-mono text-[10px]">
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-teal-300">
              {aspectRatio}
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-400">
              BG: {bgMode.replace('_', ' ')}
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-300 font-semibold">
              {subtitleMode === 'narrative_descriptions'
                ? '📖 Narrative Subs'
                : subtitleMode === 'chapter_event_cards'
                ? '🏷️ Chapter Cards'
                : subtitleMode === 'hidden'
                ? '🚫 Subtitles Off'
                : '🎵 Synced Lyrics'}
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-900 border border-slate-800 text-amber-300">
              ⚡ {pacingPreset}
            </span>
          </div>
        </div>

        {/* Action Controls & Big Apply Button */}
        <div className="flex items-center gap-2 shrink-0">
          {saveToast && (
            <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-400 animate-pulse bg-emerald-950/60 px-2.5 py-1 rounded-lg border border-emerald-800/80">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Applied to Live Monitor!</span>
            </div>
          )}

          {/* PRIMARY BIG APPLY BUTTON */}
          <button
            onClick={handleApplyAllChanges}
            disabled={isApplying}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-xl font-bold text-xs shadow-lg transition-all transform active:scale-95 ${
              isDirty
                ? 'bg-gradient-to-r from-teal-400 via-teal-500 to-cyan-500 hover:from-teal-300 hover:to-cyan-400 text-slate-950 shadow-teal-500/30 ring-2 ring-teal-400/50 animate-pulse'
                : 'bg-teal-600 hover:bg-teal-500 text-white shadow-teal-900/20'
            }`}
            title="Apply all visual, subtitle, title, and audio settings to the real-time monitor and rendering pipeline"
          >
            {isApplying ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : isDirty ? (
              <Flame className="w-4 h-4 text-slate-950" />
            ) : (
              <Check className="w-4 h-4" />
            )}
            <span className="font-extrabold tracking-wide">
              {isApplying ? 'Applying...' : isDirty ? 'APPLY CHANGES (Pending)' : 'APPLY ALL CHANGES'}
            </span>
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
          >
            <span>{isExpanded ? 'Hide' : 'Show'}</span>
            {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="flex flex-col min-h-0">
          {/* Navigation Tab Bar */}
          <div className="flex items-center gap-1 px-3 py-1.5 bg-slate-950/60 border-b border-slate-800/60 overflow-x-auto text-xs shrink-0">
            <button
              onClick={() => setActiveTab('vfx')}
              className={`flex items-center gap-1.5 px-3.5 py-1 rounded-lg font-semibold transition shrink-0 ${
                activeTab === 'vfx'
                  ? 'bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Palette className="w-3.5 h-3.5" />
              <span>🎨 Visual FX & BG</span>
            </button>

            <button
              onClick={() => setActiveTab('lyrics')}
              className={`flex items-center gap-1.5 px-3.5 py-1 rounded-lg font-semibold transition shrink-0 ${
                activeTab === 'lyrics'
                  ? 'bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Type className="w-3.5 h-3.5" />
              <span>🎤 Lyrics & Subtitles</span>
            </button>

            <button
              onClick={() => setActiveTab('overlays')}
              className={`flex items-center gap-1.5 px-3.5 py-1 rounded-lg font-semibold transition shrink-0 ${
                activeTab === 'overlays'
                  ? 'bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Tag className="w-3.5 h-3.5" />
              <span>🏷️ Titles & Overlays</span>
            </button>

            <button
              onClick={() => setActiveTab('pacing')}
              className={`flex items-center gap-1.5 px-3.5 py-1 rounded-lg font-semibold transition shrink-0 ${
                activeTab === 'pacing'
                  ? 'bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              <span>⏱️ Pacing & Beat Rules</span>
            </button>

            <button
              onClick={() => setActiveTab('tools')}
              className={`flex items-center gap-1.5 px-3.5 py-1 rounded-lg font-semibold transition shrink-0 ${
                activeTab === 'tools'
                  ? 'bg-teal-500 text-slate-950 shadow-md shadow-teal-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Volume2 className="w-3.5 h-3.5" />
              <span>🎛️ Master Audio & Tools</span>
            </button>
          </div>

          {/* Tab Content Panes */}
          <div className="p-3.5 max-h-60 overflow-y-auto space-y-3">
            {/* TAB 1: VISUAL EFFECTS & BACKGROUNDS */}
            {activeTab === 'vfx' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {/* Col 1: Aspect Ratio & Background Fill Mode */}
                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-teal-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Maximize className="w-3.5 h-3.5" /> Aspect Ratio & Frame Fill
                  </h4>

                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Canvas Aspect Ratio</label>
                    <div className="grid grid-cols-3 gap-1">
                      {[
                        { id: '16:9', label: '16:9 Wide' },
                        { id: '9:16', label: '9:16 Shorts' },
                        { id: '1:1', label: '1:1 Square' }
                      ].map((asp) => (
                        <button
                          key={asp.id}
                          onClick={() => {
                            setAspectRatio(asp.id);
                            setIsDirty(true);
                          }}
                          className={`px-1.5 py-1 rounded text-[10px] font-bold border transition ${
                            aspectRatio === asp.id
                              ? 'bg-teal-500 text-slate-950 border-teal-400 shadow-sm'
                              : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          {asp.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="text-[10px] text-slate-400 block mb-1">Background Fill Style</label>
                    <div className="grid grid-cols-2 gap-1">
                      {[
                        { id: 'blurred_fill', label: '✨ Blurred Fill' },
                        { id: 'ambient_glow', label: '🌟 Ambient Glow' },
                        { id: 'black_bars', label: '⬛ Dark Pillars' }
                      ].map((bg) => (
                        <button
                          key={bg.id}
                          onClick={() => {
                            setBgMode(bg.id);
                            setIsDirty(true);
                          }}
                          className={`px-1.5 py-1 rounded text-[10px] font-semibold border transition ${
                            bgMode === bg.id
                              ? 'bg-teal-500 text-slate-950 border-teal-400 shadow-sm font-bold'
                              : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          {bg.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {bgMode === 'blurred_fill' && (
                    <div className="grid grid-cols-2 gap-2 pt-1">
                      <div>
                        <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                          <span>Blur Radius</span>
                          <span className="font-mono text-teal-300">{blurRadius}px</span>
                        </div>
                        <input
                          type="range"
                          min="5"
                          max="45"
                          value={blurRadius}
                          onChange={(e) => {
                            setBlurRadius(parseInt(e.target.value));
                            setIsDirty(true);
                          }}
                          className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                        />
                      </div>
                      <div>
                        <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                          <span>Blur Zoom</span>
                          <span className="font-mono text-teal-300">{blurScale}x</span>
                        </div>
                        <input
                          type="range"
                          min="1.0"
                          max="1.8"
                          step="0.05"
                          value={blurScale}
                          onChange={(e) => {
                            setBlurScale(parseFloat(e.target.value));
                            setIsDirty(true);
                          }}
                          className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Col 2: Ken Burns Dynamic Motion */}
                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Film className="w-3.5 h-3.5" /> Ken Burns Pan & Zoom
                  </h4>

                  <div className="flex items-center justify-between bg-slate-900 p-1.5 rounded-lg border border-slate-800">
                    <span className="text-[10px] font-semibold text-white">Dynamic Photo Pan/Zoom</span>
                    <button
                      onClick={() => {
                        setEnableKenBurns(!enableKenBurns);
                        setIsDirty(true);
                      }}
                      className={`px-2.5 py-0.5 rounded text-[10px] font-bold transition ${
                        enableKenBurns ? 'bg-teal-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {enableKenBurns ? 'ON' : 'OFF'}
                    </button>
                  </div>

                  <div>
                    <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                      <span>Zoom Intensity</span>
                      <span className="font-mono text-cyan-300">{(kenBurnsZoom * 100 - 100).toFixed(0)}% Scale</span>
                    </div>
                    <input
                      type="range"
                      min="1.05"
                      max="1.35"
                      step="0.01"
                      value={kenBurnsZoom}
                      disabled={!enableKenBurns}
                      onChange={(e) => {
                        setKenBurnsZoom(parseFloat(e.target.value));
                        setIsDirty(true);
                      }}
                      className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400 disabled:opacity-30"
                    />
                  </div>

                  <p className="text-[9px] text-slate-500 leading-relaxed">
                    Subtly zooms and glides over still photography to eliminate static pauses between beat transitions.
                  </p>
                </div>

                {/* Col 3: Cinematic Color Grading LUTs */}
                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5" /> Cinematic Color Grading
                  </h4>

                  <div className="grid grid-cols-2 gap-1">
                    {[
                      { id: 'natural', label: '🌿 Natural' },
                      { id: 'teal_orange', label: '🌅 Teal & Orange' },
                      { id: 'warm_gold', label: '✨ Golden Hour' },
                      { id: 'vintage_35mm', label: '🎞️ 35mm Film' },
                      { id: 'cyberpunk', label: '🌆 Cyberpunk' },
                      { id: 'noir_bw', label: '🖤 Film Noir' }
                    ].map((f) => (
                      <button
                        key={f.id}
                        onClick={() => {
                          setColorFilter(f.id);
                          setIsDirty(true);
                        }}
                        className={`p-1 rounded text-left border transition ${
                          colorFilter === f.id
                            ? 'bg-amber-500/20 border-amber-400 text-amber-300 font-bold'
                            : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                        }`}
                      >
                        <div className="text-[9px] font-bold truncate">{f.label}</div>
                      </button>
                    ))}
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <label className="text-[9px] text-slate-400">Vignette Lens Darkening</label>
                    <button
                      onClick={() => {
                        setEnableVignette(!enableVignette);
                        setIsDirty(true);
                      }}
                      className={`px-2 py-0.5 rounded text-[9px] font-bold transition ${
                        enableVignette ? 'bg-amber-400 text-slate-950' : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {enableVignette ? 'ON' : 'OFF'}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: LYRICS & SUBTITLES (STRICT SINGLE TYPE ENFORCEMENT) */}
            {activeTab === 'lyrics' && (
              <div className="space-y-3">
                <div className="bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <label className="text-[11px] font-bold text-teal-400 uppercase tracking-wider block mb-1.5">
                    Subtitle Source & Content Mode (Select Exactly One)
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                    {[
                      {
                        id: 'karaoke_lyrics',
                        label: '🎵 Song Lyrics (Karaoke)',
                        desc: 'Syllable sweep timed to song vocals'
                      },
                      {
                        id: 'narrative_descriptions',
                        label: '📖 Descriptive Story Narration',
                        desc: 'Text describing what happens on screen'
                      },
                      {
                        id: 'chapter_event_cards',
                        label: '🏷️ Chapter Event Cards',
                        desc: 'Documentary travel acts and banners'
                      },
                      {
                        id: 'hidden',
                        label: '🚫 Subtitles Off',
                        desc: 'Clean presentation without subtitles'
                      }
                    ].map((m) => (
                      <button
                        key={m.id}
                        onClick={() => {
                          setSubtitleMode(m.id);
                          setIsDirty(true);
                        }}
                        className={`p-2 rounded-xl text-left border transition ${
                          subtitleMode === m.id
                            ? 'bg-teal-500/20 border-teal-400 text-teal-300 shadow-md ring-1 ring-teal-400/40'
                            : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700'
                        }`}
                      >
                        <div className="text-[10px] font-bold mb-0.5">{m.label}</div>
                        <div className="text-[8px] text-slate-400 leading-tight">{m.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Inline Scene Narration Editor when narrative_descriptions is selected */}
                {subtitleMode === 'narrative_descriptions' && (
                  <div className="bg-slate-950/90 p-2.5 rounded-xl border border-teal-500/30 space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-[11px] font-bold text-teal-300 flex items-center gap-1">
                          <AlignLeft className="w-3 h-3" /> Scene-by-Scene Story Narration Text
                        </h4>
                        <p className="text-[9px] text-slate-400">
                          Edit the text to describe what is happening in each cut (independent of song lyrics). Click Apply to preview.
                        </p>
                      </div>

                      <button
                        onClick={handleBulkFillAiCaptions}
                        className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-[9px] transition shadow"
                      >
                        <Wand2 className="w-2.5 h-2.5" />
                        <span>Auto-Fill from Media Vision</span>
                      </button>
                    </div>

                    <div className="max-h-32 overflow-y-auto space-y-1 pr-1">
                      {slices.map((slice, idx) => {
                        const currentVal = localCaptions[slice.id] !== undefined
                          ? localCaptions[slice.id]
                          : (slice.custom_caption !== undefined && slice.custom_caption !== null
                              ? slice.custom_caption
                              : (slice.asset?.caption || ''));

                        return (
                          <div key={slice.id} className="flex items-center gap-1.5 bg-slate-900/80 p-1 rounded-lg border border-slate-800 text-xs">
                            <span className="font-mono text-[9px] text-teal-400 px-1 py-0.5 bg-slate-950 rounded shrink-0 font-bold">
                              #{idx + 1} ({slice.timeline_start_sec.toFixed(1)}s)
                            </span>
                            <input
                              type="text"
                              value={currentVal}
                              onChange={(e) => handleLocalCaptionChange(slice.id, e.target.value)}
                              placeholder={`Describe Scene #${idx + 1}...`}
                              className="flex-1 bg-slate-950 border border-slate-700/60 rounded px-1.5 py-0.5 text-[10px] text-white placeholder-slate-600 focus:outline-none focus:border-teal-400"
                            />
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {subtitleMode !== 'hidden' && (
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="space-y-1.5 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                      <label className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">
                        Font Family & Size
                      </label>
                      <select
                        value={fontFamily}
                        onChange={(e) => {
                          setFontFamily(e.target.value);
                          setIsDirty(true);
                        }}
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-teal-400"
                      >
                        <option value="Inter">Inter (Clean Modern Sans)</option>
                        <option value="Montserrat">Montserrat (Display Bold)</option>
                        <option value="JetBrains Mono">JetBrains Mono (Tech Code)</option>
                        <option value="Arial">Arial (Standard Sans)</option>
                        <option value="Playfair Display">Playfair Display (Serif)</option>
                        <option value="Caveat">Caveat (Handwritten)</option>
                      </select>

                      <div className="pt-1">
                        <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                          <span>Font Size</span>
                          <span className="font-mono text-teal-300">{fontSize}px</span>
                        </div>
                        <input
                          type="range"
                          min="28"
                          max="64"
                          value={fontSize}
                          onChange={(e) => {
                            setFontSize(parseInt(e.target.value));
                            setIsDirty(true);
                          }}
                          className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                      <label className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">
                        Highlight Accent Color
                      </label>
                      <div className="flex items-center gap-1.5">
                        {[
                          { hex: '#2dd4bf', label: 'Teal' },
                          { hex: '#38bdf8', label: 'Cyan' },
                          { hex: '#facc15', label: 'Gold' },
                          { hex: '#f43f5e', label: 'Coral' },
                          { hex: '#a3e635', label: 'Lime' },
                          { hex: '#ffffff', label: 'White' }
                        ].map((c) => (
                          <button
                            key={c.hex}
                            onClick={() => {
                              setHighlightColor(c.hex);
                              setIsDirty(true);
                            }}
                            className={`w-5 h-5 rounded-full border transition transform ${
                              highlightColor === c.hex ? 'scale-125 border-white shadow-lg' : 'border-transparent hover:scale-110'
                            }`}
                            style={{ backgroundColor: c.hex }}
                            title={c.label}
                          />
                        ))}
                      </div>

                      <div className="pt-1">
                        <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                          <span>Outline Thickness</span>
                          <span className="font-mono text-cyan-300">{outlineWidth}px</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="6"
                          value={outlineWidth}
                          onChange={(e) => {
                            setOutlineWidth(parseInt(e.target.value));
                            setIsDirty(true);
                          }}
                          className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                      <label className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">
                        Screen Placement
                      </label>
                      <div className="grid grid-cols-3 gap-1">
                        {[
                          { id: 2, label: '⬇️ Bottom' },
                          { id: 5, label: '🎯 Center' },
                          { id: 8, label: '⬆️ Top' }
                        ].map((pos) => (
                          <button
                            key={pos.id}
                            onClick={() => {
                              setAlignment(pos.id);
                              setIsDirty(true);
                            }}
                            className={`py-1 rounded text-xs font-semibold border transition ${
                              alignment === pos.id
                                ? 'bg-teal-500 text-slate-950 border-teal-400 font-bold'
                                : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                            }`}
                          >
                            {pos.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: TITLES, BADGES & WATERMARKS */}
            {activeTab === 'overlays' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <div className="flex items-center justify-between">
                    <h4 className="text-[11px] font-bold text-teal-400 uppercase tracking-wider flex items-center gap-1">
                      <Tag className="w-3 h-3" /> Video Intro Title Card
                    </h4>
                    <button
                      onClick={() => {
                        setIntroEnabled(!introEnabled);
                        setIsDirty(true);
                      }}
                      className={`px-2 py-0.5 rounded text-[9px] font-bold transition ${
                        introEnabled ? 'bg-teal-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {introEnabled ? 'ON' : 'OFF'}
                    </button>
                  </div>

                  <div>
                    <label className="text-[9px] text-slate-400 block mb-0.5">Main Video Title</label>
                    <input
                      type="text"
                      value={introTitle}
                      onChange={(e) => {
                        setIntroTitle(e.target.value);
                        setIsDirty(true);
                      }}
                      placeholder="e.g. Kyoto Memories"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-teal-400"
                    />
                  </div>

                  <div>
                    <label className="text-[9px] text-slate-400 block mb-0.5">Subtitle / Destination Tagline</label>
                    <input
                      type="text"
                      value={introSubtitle}
                      onChange={(e) => {
                        setIntroSubtitle(e.target.value);
                        setIsDirty(true);
                      }}
                      placeholder="e.g. Autumn Adventure • Japan 2026"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-teal-400"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                      <span>Intro Card Duration</span>
                      <span className="font-mono text-teal-300">{introDuration}s</span>
                    </div>
                    <input
                      type="range"
                      min="2.0"
                      max="6.0"
                      step="0.5"
                      value={introDuration}
                      onChange={(e) => {
                        setIntroDuration(parseFloat(e.target.value));
                        setIsDirty(true);
                      }}
                      className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                    />
                  </div>
                </div>

                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1">
                    <Compass className="w-3 h-3" /> Creator Watermark & Badges
                  </h4>

                  <div>
                    <label className="text-[9px] text-slate-400 block mb-0.5">Creator Watermark Handle</label>
                    <input
                      type="text"
                      value={watermarkText}
                      onChange={(e) => {
                        setWatermarkText(e.target.value);
                        setIsDirty(true);
                      }}
                      placeholder="e.g. @MyTravelLog"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-400"
                    />
                  </div>

                  <div className="flex items-center justify-between bg-slate-900 p-1.5 rounded-lg border border-slate-800">
                    <span className="text-[10px] font-medium text-slate-300">Show GPS Location Badges</span>
                    <button
                      onClick={() => {
                        setShowLocationBadge(!showLocationBadge);
                        setIsDirty(true);
                      }}
                      className={`px-2 py-0.5 rounded text-[9px] font-bold transition ${
                        showLocationBadge ? 'bg-cyan-400 text-slate-950' : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {showLocationBadge ? 'ON' : 'OFF'}
                    </button>
                  </div>

                  <div>
                    <label className="text-[9px] text-slate-400 block mb-0.5">Outro End Message</label>
                    <input
                      type="text"
                      value={outroText}
                      onChange={(e) => {
                        setOutroText(e.target.value);
                        setIsDirty(true);
                      }}
                      placeholder="e.g. Memories to cherish forever"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1 text-xs text-white placeholder-slate-600 focus:outline-none focus:border-cyan-400"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: PACING & BEAT SOLVER RULES */}
            {activeTab === 'pacing' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1">
                    <Zap className="w-3 h-3" /> Pacing Style Presets
                  </h4>

                  <div className="space-y-1">
                    {[
                      { id: 'fast', label: '⚡ Fast-Cut Energy', desc: '1-2 beats per cut' },
                      { id: 'balanced', label: '⚖️ Balanced Rhythm', desc: '2-4 beats per cut' },
                      { id: 'cinematic', label: '🎬 Cinematic Slow', desc: '4-8 beats per cut' }
                    ].map((preset) => (
                      <button
                        key={preset.id}
                        onClick={() => handlePacingPresetSelect(preset.id)}
                        className={`w-full p-1.5 rounded-lg text-left border transition ${
                          pacingPreset === preset.id
                            ? 'bg-amber-500/20 border-amber-400 text-amber-300 font-bold'
                            : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                        }`}
                      >
                        <div className="text-[10px] font-bold">{preset.label}</div>
                        <div className="text-[8px] text-slate-400">{preset.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-teal-400 uppercase tracking-wider flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Media Duration Bounds
                  </h4>

                  <div>
                    <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                      <span>Photo Beat Bounds</span>
                      <span className="font-mono text-teal-300">{photoMinBeats}b – {photoMaxBeats}b</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="range"
                        min="1"
                        max="4"
                        value={photoMinBeats}
                        onChange={(e) => {
                          setPhotoMinBeats(parseInt(e.target.value));
                          setIsDirty(true);
                        }}
                        className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                      />
                      <input
                        type="range"
                        min="2"
                        max="8"
                        value={photoMaxBeats}
                        onChange={(e) => {
                          setPhotoMaxBeats(parseInt(e.target.value));
                          setIsDirty(true);
                        }}
                        className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                      <span>Video Clip Beat Bounds</span>
                      <span className="font-mono text-cyan-300">{videoMinBeats}b – {videoMaxBeats}b</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="range"
                        min="2"
                        max="6"
                        value={videoMinBeats}
                        onChange={(e) => {
                          setVideoMinBeats(parseInt(e.target.value));
                          setIsDirty(true);
                        }}
                        className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                      />
                      <input
                        type="range"
                        min="4"
                        max="12"
                        value={videoMaxBeats}
                        onChange={(e) => {
                          setVideoMaxBeats(parseInt(e.target.value));
                          setIsDirty(true);
                        }}
                        className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
                      />
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[9px] text-slate-300">Chorus Action Boost</span>
                    <button
                      onClick={() => {
                        setMotionBoost(!motionBoost);
                        setIsDirty(true);
                      }}
                      className={`px-2 py-0.5 rounded text-[9px] font-bold transition ${
                        motionBoost ? 'bg-teal-400 text-slate-950' : 'bg-slate-800 text-slate-400'
                      }`}
                    >
                      {motionBoost ? 'ACTIVE' : 'OFF'}
                    </button>
                  </div>
                </div>

                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80 flex flex-col justify-between">
                  <div>
                    <h4 className="text-[11px] font-bold text-white uppercase tracking-wider mb-1">
                      Apply Pacing & Solve
                    </h4>
                    <p className="text-[9px] text-slate-400 leading-relaxed mb-2">
                      Recalibrate all timeline cuts instantly according to your customized beat bounds and story pacing.
                    </p>
                  </div>

                  <button
                    onClick={async () => {
                      await handleApplyAllChanges();
                      if (onSolveTimeline) onSolveTimeline();
                    }}
                    disabled={isSolving || !audioTrack}
                    className="w-full py-2 rounded-xl bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 font-bold text-xs shadow-lg shadow-teal-500/20 disabled:opacity-50 transition flex items-center justify-center gap-2"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isSolving ? 'animate-spin' : ''}`} />
                    <span>{isSolving ? 'Solving Timeline...' : 'Apply & Auto-Solve Timeline'}</span>
                  </button>
                </div>
              </div>
            )}

            {/* TAB 5: MASTER AUDIO & BULK TOOLS */}
            {activeTab === 'tools' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-teal-400 uppercase tracking-wider flex items-center gap-1">
                    <Volume2 className="w-3 h-3" /> Audio Dynamics & Mastering
                  </h4>

                  <div>
                    <label className="text-[9px] text-slate-400 block mb-0.5">EBU R128 Target Loudness</label>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        { val: -14, label: '-14 LUFS (YouTube)' },
                        { val: -16, label: '-16 LUFS (Apple)' },
                        { val: -12, label: '-12 LUFS (Club)' }
                      ].map((l) => (
                        <button
                          key={l.val}
                          onClick={() => {
                            setLufsTarget(l.val);
                            setIsDirty(true);
                          }}
                          className={`py-1 rounded text-[9px] font-bold border transition ${
                            lufsTarget === l.val
                              ? 'bg-teal-500 text-slate-950 border-teal-400'
                              : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-700'
                          }`}
                        >
                          {l.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div>
                      <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                        <span>Audio Fade-In</span>
                        <span className="font-mono text-teal-300">{fadeInSec}s</span>
                      </div>
                      <input
                        type="range"
                        min="0.0"
                        max="2.0"
                        step="0.25"
                        value={fadeInSec}
                        onChange={(e) => {
                          setFadeInSec(parseFloat(e.target.value));
                          setIsDirty(true);
                        }}
                        className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                      />
                    </div>
                    <div>
                      <div className="flex justify-between text-[9px] text-slate-400 mb-0.5">
                        <span>Audio Fade-Out</span>
                        <span className="font-mono text-teal-300">{fadeOutSec}s</span>
                      </div>
                      <input
                        type="range"
                        min="0.5"
                        max="4.0"
                        step="0.5"
                        value={fadeOutSec}
                        onChange={(e) => {
                          setFadeOutSec(parseFloat(e.target.value));
                          setIsDirty(true);
                        }}
                        className="w-full h-1 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-teal-400"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-2 bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/80">
                  <h4 className="text-[11px] font-bold text-cyan-400 uppercase tracking-wider flex items-center gap-1">
                    <Layers className="w-3 h-3" /> Bulk Slice Operations
                  </h4>

                  <div className="space-y-1.5">
                    <button
                      onClick={() => onBulkApply && onBulkApply({ action: 'apply_bg_mode', bg_mode: bgMode })}
                      className="w-full py-1 px-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 text-[10px] font-semibold text-left flex items-center justify-between transition"
                    >
                      <span>Apply Current Background ({bgMode}) to All Clips</span>
                      <Check className="w-3 h-3 text-teal-400" />
                    </button>

                    <button
                      onClick={() => onBulkApply && onBulkApply({ action: 'toggle_ken_burns', enable_ken_burns: true })}
                      className="w-full py-1 px-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 text-[10px] font-semibold text-left flex items-center justify-between transition"
                    >
                      <span>Enable Ken Burns Motion on All Photos</span>
                      <Check className="w-3 h-3 text-cyan-400" />
                    </button>

                    <button
                      onClick={() => onBulkApply && onBulkApply({ action: 'toggle_ken_burns', enable_ken_burns: false })}
                      className="w-full py-1 px-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 text-[10px] font-semibold text-left flex items-center justify-between transition"
                    >
                      <span>Disable Ken Burns on All Clips (Static)</span>
                      <RotateCcw className="w-3 h-3 text-slate-400" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
