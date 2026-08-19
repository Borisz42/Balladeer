import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  X,
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  Volume2,
  Mic,
  Music,
  Plus,
  Trash2,
  Check,
  Clock,
  Sliders,
  FileText,
  AlignLeft,
  FastForward,
  Rewind,
  ArrowRight,
  Disc3,
  HelpCircle
} from 'lucide-react';

export default function LyricEditorModal({
  isOpen,
  onClose,
  project,
  audioTrack,
  onUpdateLyrics,
  onRealignLyrics,
  isRealigning = false
}) {
  if (!isOpen || !audioTrack) return null;

  const [activeTab, setActiveTab] = useState('lines'); // 'lines' | 'words' | 'raw_text'
  const [activeStem, setActiveStem] = useState('vocals'); // 'vocals' | 'master'
  const defaultDraft = useMemo(() => {
    if (project?.narrative_text?.trim()) {
      const pLines = project.narrative_text.split('\n').map((l) => l.trim()).filter(Boolean);
      if (pLines.length > 0) {
        return `[Verse 1]\n${pLines.slice(0, 2).join('\n')}\n\n[Chorus]\nChasing the light across the sky\nEvery moment flying by\n\n[Verse 2]\n${pLines.slice(2, 4).join('\n') || 'Memories carved in golden light'}`;
      }
    }
    return `[Verse 1]\nWalking down the morning trail\nWind in the sails and sun on the sea\n\n[Chorus]\nChasing the light across the sky\nEvery moment flying by`;
  }, [project?.narrative_text]);

  const [lyricsText, setLyricsText] = useState(audioTrack.lyrics || defaultDraft);
  const [words, setWords] = useState(
    (audioTrack.aligned_lyrics || []).map((w, idx) => ({
      ...w,
      _id: `w_${idx}_${Date.now()}`
    }))
  );

  const lyrConfig = project?.config_override?.lyrics_style || {};
  const [enableWordHighlight, setEnableWordHighlight] = useState(
    lyrConfig.enable_word_highlight !== undefined ? lyrConfig.enable_word_highlight : true
  );

  // Audio Playback in Modal
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [activeWordIdx, setActiveWordIdx] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Keep state updated when audioTrack changes
  useEffect(() => {
    if (audioTrack) {
      setLyricsText(audioTrack.lyrics || defaultDraft);
      setWords(
        (audioTrack.aligned_lyrics || []).map((w, idx) => ({
          ...w,
          _id: `w_${idx}_${Date.now()}`
        }))
      );
    }
  }, [audioTrack, defaultDraft]);

  // Audio Time Update listener
  const handleTimeUpdate = () => {
    if (audioRef.current) {
      const t = audioRef.current.currentTime;
      setCurrentTime(t);

      // Find active word
      const foundIdx = words.findIndex((w) => t >= w.snapped_start && t <= w.snapped_end);
      setActiveWordIdx(foundIdx !== -1 ? foundIdx : null);
    }
  };

  const handleTogglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const handlePlayWordSnippet = (wordObj) => {
    if (!audioRef.current) return;
    const startT = Math.max(0, wordObj.start - 0.05);
    const endT = wordObj.end + 0.15;
    audioRef.current.currentTime = startT;
    audioRef.current.play();
    setIsPlaying(true);

    const checkStop = () => {
      if (audioRef.current && audioRef.current.currentTime >= endT) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else if (audioRef.current && !audioRef.current.paused) {
        requestAnimationFrame(checkStop);
      }
    };
    requestAnimationFrame(checkStop);
  };

  const handlePlayLineSnippet = (lineWords) => {
    if (!audioRef.current || !lineWords.length) return;
    const startT = Math.max(0, lineWords[0].start - 0.05);
    const endT = lineWords[lineWords.length - 1].end + 0.2;
    audioRef.current.currentTime = startT;
    audioRef.current.play();
    setIsPlaying(true);

    const checkStop = () => {
      if (audioRef.current && audioRef.current.currentTime >= endT) {
        audioRef.current.pause();
        setIsPlaying(false);
      } else if (audioRef.current && !audioRef.current.paused) {
        requestAnimationFrame(checkStop);
      }
    };
    requestAnimationFrame(checkStop);
  };

  // Group words into lines based on line_index or punctuation / natural grouping
  const lines = useMemo(() => {
    const grouped = [];
    let currentLineIdx = null;
    let currentLineWords = [];

    words.forEach((w, idx) => {
      const lIdx = w.line_index !== undefined && w.line_index !== null ? w.line_index : Math.floor(idx / 5);
      if (currentLineIdx === null || lIdx === currentLineIdx) {
        currentLineWords.push({ ...w, _globalIdx: idx });
        currentLineIdx = lIdx;
      } else {
        if (currentLineWords.length > 0) {
          grouped.push({
            lineIndex: currentLineIdx,
            words: currentLineWords,
            text: currentLineWords.map((cw) => cw.word).join(' '),
            start: currentLineWords[0].start,
            end: currentLineWords[currentLineWords.length - 1].end,
            snapped_start: currentLineWords[0].snapped_start,
            snapped_end: currentLineWords[currentLineWords.length - 1].snapped_end
          });
        }
        currentLineWords = [{ ...w, _globalIdx: idx }];
        currentLineIdx = lIdx;
      }
    });

    if (currentLineWords.length > 0) {
      grouped.push({
        lineIndex: currentLineIdx,
        words: currentLineWords,
        text: currentLineWords.map((cw) => cw.word).join(' '),
        start: currentLineWords[0].start,
        end: currentLineWords[currentLineWords.length - 1].end,
        snapped_start: currentLineWords[0].snapped_start,
        snapped_end: currentLineWords[currentLineWords.length - 1].snapped_end
      });
    }

    return grouped;
  }, [words]);

  // Word editing handlers
  const handleUpdateWordText = (globalIdx, newText) => {
    setWords((prev) => {
      const updated = [...prev];
      updated[globalIdx] = { ...updated[globalIdx], word: newText };
      return updated;
    });
  };

  const handleUpdateWordTimes = (globalIdx, newStart, newEnd) => {
    const beatGrid = audioTrack.beat_grid || [];
    const tol = 0.25;

    const snapVal = (val) => {
      if (!beatGrid.length) return { snapped: Math.round(val * 10000) / 10000, beatIdx: null };
      let minDiff = Infinity;
      let closestBeat = val;
      let closestIdx = null;
      beatGrid.forEach((b, bIdx) => {
        const diff = Math.abs(val - b);
        if (diff < minDiff) {
          minDiff = diff;
          closestBeat = b;
          closestIdx = bIdx;
        }
      });
      if (minDiff <= tol) {
        return { snapped: Math.round(closestBeat * 10000) / 10000, beatIdx: closestIdx };
      }
      return { snapped: Math.round(val * 10000) / 10000, beatIdx: null };
    };

    setWords((prev) => {
      const updated = [...prev];
      const target = updated[globalIdx];
      const s = Math.max(0, Math.round(newStart * 10000) / 10000);
      const e = Math.max(s + 0.05, Math.round(newEnd * 10000) / 10000);
      const { snapped: sStart, beatIdx } = snapVal(s);
      const { snapped: sEnd } = snapVal(e);

      updated[globalIdx] = {
        ...target,
        start: s,
        end: e,
        snapped_start: sStart,
        snapped_end: Math.max(sStart + 0.08, sEnd),
        beat_index: beatIdx
      };
      return updated;
    });
  };

  const handleNudgeWord = (globalIdx, deltaSec) => {
    const target = words[globalIdx];
    if (!target) return;
    const newStart = Math.max(0, target.start + deltaSec);
    const newEnd = Math.max(newStart + 0.1, target.end + deltaSec);
    handleUpdateWordTimes(globalIdx, newStart, newEnd);
  };

  const handleNudgeFromWordOnward = (fromGlobalIdx, deltaSec) => {
    setWords((prev) => {
      return prev.map((w, idx) => {
        if (idx < fromGlobalIdx) return w;
        const newStart = Math.max(0, w.start + deltaSec);
        const newEnd = Math.max(newStart + 0.1, w.end + deltaSec);
        return {
          ...w,
          start: Math.round(newStart * 10000) / 10000,
          end: Math.round(newEnd * 10000) / 10000,
          snapped_start: Math.max(0, Math.round((w.snapped_start + deltaSec) * 10000) / 10000),
          snapped_end: Math.max(0.1, Math.round((w.snapped_end + deltaSec) * 10000) / 10000)
        };
      });
    });
  };

  const handleInsertWordAfter = (globalIdx) => {
    const target = words[globalIdx];
    const newStart = target ? target.end + 0.05 : 0;
    const newEnd = newStart + 0.4;
    const newWord = {
      word: 'new',
      start: Math.round(newStart * 10000) / 10000,
      end: Math.round(newEnd * 10000) / 10000,
      snapped_start: Math.round(newStart * 10000) / 10000,
      snapped_end: Math.round(newEnd * 10000) / 10000,
      beat_index: target?.beat_index ?? null,
      line_index: target?.line_index ?? 0,
      _id: `w_new_${Date.now()}`
    };

    setWords((prev) => {
      const updated = [...prev];
      updated.splice(globalIdx + 1, 0, newWord);
      return updated;
    });
  };

  const handleDeleteWord = (globalIdx) => {
    setWords((prev) => prev.filter((_, idx) => idx !== globalIdx));
  };

  const handleSnapAllToBeats = () => {
    const beatGrid = audioTrack.beat_grid || [];
    if (!beatGrid.length) return;

    setWords((prev) => {
      return prev.map((w) => {
        let minDiffS = Infinity;
        let closestBeatS = w.start;
        let beatIdx = null;

        beatGrid.forEach((b, bIdx) => {
          const diff = Math.abs(w.start - b);
          if (diff < minDiffS) {
            minDiffS = diff;
            closestBeatS = b;
            beatIdx = bIdx;
          }
        });

        let minDiffE = Infinity;
        let closestBeatE = w.end;
        beatGrid.forEach((b) => {
          const diff = Math.abs(w.end - b);
          if (diff < minDiffE) {
            minDiffE = diff;
            closestBeatE = b;
          }
        });

        const sStart = minDiffS <= 0.35 ? closestBeatS : w.start;
        const sEnd = minDiffE <= 0.35 ? closestBeatE : w.end;

        return {
          ...w,
          snapped_start: Math.round(sStart * 10000) / 10000,
          snapped_end: Math.max(Math.round(sStart * 10000) / 10000 + 0.1, Math.round(sEnd * 10000) / 10000),
          beat_index: minDiffS <= 0.35 ? beatIdx : w.beat_index
        };
      });
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const cleanedWords = words.map(({ _id, _globalIdx, ...w }) => w);
      await onUpdateLyrics({
        lyrics: lyricsText,
        aligned_lyrics: cleanedWords,
        auto_snap: false,
        enable_word_highlight: enableWordHighlight
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      alert(`Failed to save lyrics: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleTriggerRealign = async () => {
    if (!onRealignLyrics) return;
    try {
      await onRealignLyrics(lyricsText);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      alert(`Re-alignment failed: ${err.message}`);
    }
  };

  const handleAddFirstLine = () => {
    const newWord1 = {
      _id: `w_${Date.now()}_1`,
      word: 'Walking',
      start: 0.5,
      end: 1.2,
      snapped_start: 0.5,
      snapped_end: 1.2,
      beat_index: 0,
      line_index: 0
    };
    const newWord2 = {
      _id: `w_${Date.now()}_2`,
      word: 'under',
      start: 1.3,
      end: 1.8,
      snapped_start: 1.3,
      snapped_end: 1.8,
      beat_index: 1,
      line_index: 0
    };
    const newWord3 = {
      _id: `w_${Date.now()}_3`,
      word: 'sunlight',
      start: 1.9,
      end: 2.6,
      snapped_start: 1.9,
      snapped_end: 2.6,
      beat_index: 2,
      line_index: 0
    };
    setWords([newWord1, newWord2, newWord3]);
    setLyricsText('Walking under sunlight');
  };

  const totalDuration = audioTrack?.beat_grid?.length
    ? (audioTrack.beat_grid[audioTrack.beat_grid.length - 1] || 30.0) + 1.0
    : 30.0;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-5xl h-[92vh] max-h-[850px] flex flex-col shadow-2xl overflow-hidden">
        {/* MODAL HEADER */}
        <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between bg-slate-950/80 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-teal-500/20 text-teal-400 flex items-center justify-center font-bold">
              <Mic className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-bold text-white tracking-wide">
                  Interactive Lyric & Timestamp Editor
                </h2>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-teal-950 text-teal-400 border border-teal-800 font-mono font-semibold">
                  MMS_FA + Beat Snapped
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-mono">
                Fine-tune word text, correct misheard lyrics, and nudge vocal timestamps.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-1.5 bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 px-3.5 py-1.5 rounded-lg text-xs font-bold transition shadow-md shadow-teal-500/20"
            >
              {saveSuccess ? (
                <>
                  <Check className="w-3.5 h-3.5 text-slate-950" />
                  <span>Saved!</span>
                </>
              ) : (
                <>
                  <Disc3 className="w-3.5 h-3.5" />
                  <span>{isSaving ? 'Saving...' : 'Apply to Timeline'}</span>
                </>
              )}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* AUDIO CONTROL STRIP */}
        <div className="px-4 py-2.5 bg-slate-950 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-3 shrink-0">
          {/* Audio Source Stem Selector & Playback */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleTogglePlay}
              className="w-7 h-7 rounded-lg bg-teal-500 hover:bg-teal-400 text-slate-950 flex items-center justify-center font-bold shadow transition"
              title={isPlaying ? 'Pause' : 'Play'}
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 ml-0.5" />}
            </button>

            <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-0.5 text-[10px] font-semibold">
              <button
                onClick={() => setActiveStem('vocals')}
                className={`px-2 py-0.5 rounded transition ${
                  activeStem === 'vocals' ? 'bg-teal-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                🎤 Vocals Only
              </button>
              <button
                onClick={() => setActiveStem('master')}
                className={`px-2 py-0.5 rounded transition ${
                  activeStem === 'master' ? 'bg-teal-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-white'
                }`}
              >
                🎵 Full Master
              </button>
            </div>

            <div className="font-mono text-[11px] text-slate-300 ml-1">
              <span className="text-teal-400 font-bold">{currentTime.toFixed(2)}s</span>
              <span className="text-slate-500"> / {totalDuration.toFixed(2)}s</span>
            </div>

            <audio
              ref={audioRef}
              src={`http://localhost:8000/api/projects/${project?.id}/audio/${activeStem}`}
              onTimeUpdate={handleTimeUpdate}
              onEnded={() => setIsPlaying(false)}
            />
          </div>

          {/* Karaoke Word Highlight Mode Toggle */}
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-1.5 text-[11px] text-slate-300 cursor-pointer bg-slate-900 px-2.5 py-1 rounded-lg border border-slate-800">
              <input
                type="checkbox"
                checked={enableWordHighlight}
                onChange={(e) => setEnableWordHighlight(e.target.checked)}
                className="rounded border-slate-700 text-teal-500 w-3.5 h-3.5"
              />
              <span className="font-medium">Karaoke Word Highlighting</span>
            </label>

            <button
              onClick={handleSnapAllToBeats}
              className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-teal-300 border border-slate-700 px-2.5 py-1 rounded-lg text-[11px] font-semibold transition"
              title="Snap all word starts and ends to nearest Librosa beats"
            >
              <Sliders className="w-3 h-3 text-teal-400" />
              <span>Snap All to Beats</span>
            </button>
          </div>
        </div>

        {/* TAB CONTROLS */}
        <div className="px-4 pt-2.5 pb-2 bg-slate-900/60 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1 bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab('lines')}
              className={`px-3 py-1 rounded-md font-semibold flex items-center gap-1.5 transition ${
                activeTab === 'lines' ? 'bg-teal-500 text-slate-950 shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <AlignLeft className="w-3 h-3" />
              <span>Line-by-Line Grouped</span>
              <span className="text-[10px] opacity-75 font-mono">({lines.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('words')}
              className={`px-3 py-1 rounded-md font-semibold flex items-center gap-1.5 transition ${
                activeTab === 'words' ? 'bg-teal-500 text-slate-950 shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <Sliders className="w-3 h-3" />
              <span>Word Table & Timing</span>
              <span className="text-[10px] opacity-75 font-mono">({words.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('raw_text')}
              className={`px-3 py-1 rounded-md font-semibold flex items-center gap-1.5 transition ${
                activeTab === 'raw_text' ? 'bg-teal-500 text-slate-950 shadow' : 'text-slate-400 hover:text-white'
              }`}
            >
              <FileText className="w-3 h-3" />
              <span>Raw Lyrics & AI Align</span>
            </button>
          </div>

          <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
            <span>{words.length} Aligned Words</span>
            <span>•</span>
            <span>{audioTrack?.bpm || 120} BPM</span>
          </div>
        </div>

        {/* TAB BODY */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* TAB 1: LINE-BY-LINE GROUPED VIEW */}
          {activeTab === 'lines' && (
            <div className="space-y-4">
              <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/80 text-xs text-slate-300 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-teal-400 font-bold">ℹ️ Tip:</span>
                  <span>
                    Lyrics are displayed line-by-line in subtitles and video. You can override word texts or nudge individual word timestamps below.
                  </span>
                </div>
              </div>

              {lines.length === 0 ? (
                <div className="bg-slate-950/80 rounded-2xl border border-dashed border-slate-700/80 p-8 text-center space-y-4 my-4">
                  <div className="w-12 h-12 rounded-2xl bg-teal-500/10 text-teal-400 flex items-center justify-center mx-auto">
                    <Music className="w-6 h-6" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="text-sm font-bold text-white">No Aligned Lyrics on Audio Track</h3>
                    <p className="text-xs text-slate-400 max-w-md mx-auto">
                      This audio track has no vocal lyrics or alignment data. You can draft rhyming lyrics from your travel narrative or add custom words directly.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                    <button
                      onClick={() => {
                        setLyricsText(defaultDraft);
                        setActiveTab('raw_text');
                      }}
                      className="flex items-center gap-1.5 bg-teal-500 hover:bg-teal-400 text-slate-950 px-4 py-2 rounded-xl text-xs font-bold transition shadow"
                    >
                      <Sparkles className="w-4 h-4" />
                      <span>Draft & AI Align Lyrics</span>
                    </button>
                    <button
                      onClick={handleAddFirstLine}
                      className="flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 px-4 py-2 rounded-xl text-xs font-semibold transition"
                    >
                      <Plus className="w-4 h-4" />
                      <span>Add Line Manually</span>
                    </button>
                  </div>
                </div>
              ) : (
                lines.map((line, lIdx) => {
                  const isLineActive = currentTime >= line.start && currentTime <= line.end;

                  return (
                    <div
                      key={lIdx}
                      className={`rounded-xl border transition-all p-3.5 space-y-3 ${
                        isLineActive
                          ? 'bg-slate-950/90 border-teal-500/80 shadow-lg shadow-teal-500/10'
                          : 'bg-slate-950/40 border-slate-800/80 hover:border-slate-700'
                      }`}
                    >
                    {/* Line Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800/80">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 rounded bg-teal-950 text-teal-300 font-mono text-[10px] font-bold border border-teal-800/60">
                          Line #{lIdx + 1}
                        </span>
                        <div className="font-mono text-[10px] text-slate-400">
                          ⏱️ {line.start.toFixed(2)}s – {line.end.toFixed(2)}s ({(line.end - line.start).toFixed(2)}s)
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handlePlayLineSnippet(line.words)}
                          className="flex items-center gap-1 bg-slate-800 hover:bg-slate-700 text-cyan-300 px-2 py-0.5 rounded text-[10px] font-semibold border border-slate-700 transition"
                          title="Preview vocal audio for this whole line"
                        >
                          <Play className="w-2.5 h-2.5" /> Play Line
                        </button>

                        <button
                          onClick={() => handleNudgeFromWordOnward(line.words[0]._globalIdx, 0.1)}
                          className="flex items-center gap-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded text-[9px] font-mono border border-slate-700"
                          title="Shift this line and all subsequent words later by +0.10s"
                        >
                          <FastForward className="w-2.5 h-2.5" /> +0.1s All
                        </button>
                        <button
                          onClick={() => handleNudgeFromWordOnward(line.words[0]._globalIdx, -0.1)}
                          className="flex items-center gap-0.5 bg-slate-800 hover:bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded text-[9px] font-mono border border-slate-700"
                          title="Shift this line and all subsequent words earlier by -0.10s"
                        >
                          <Rewind className="w-2.5 h-2.5" /> -0.1s All
                        </button>
                      </div>
                    </div>

                    {/* Word Tokens Grid in Line */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-2.5">
                      {line.words.map((wObj) => {
                        const gIdx = wObj._globalIdx;
                        const isWordActive = activeWordIdx === gIdx;

                        return (
                          <div
                            key={wObj._id || gIdx}
                            className={`p-2.5 rounded-lg border transition-all space-y-2 flex flex-col justify-between ${
                              isWordActive
                                ? 'bg-teal-950/40 border-teal-400 shadow-md scale-[1.01]'
                                : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                            }`}
                          >
                            {/* Word Text Input Override */}
                            <div className="flex items-center justify-between gap-1.5">
                              <div className="flex items-center gap-1 min-w-0 flex-1">
                                <span className="text-[9px] font-mono text-slate-500">#{gIdx + 1}</span>
                                <input
                                  type="text"
                                  value={wObj.word}
                                  onChange={(e) => handleUpdateWordText(gIdx, e.target.value)}
                                  className="w-full bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 text-xs font-bold text-white focus:border-teal-500 focus:outline-none"
                                  placeholder="Word..."
                                />
                              </div>

                              <button
                                onClick={() => handlePlayWordSnippet(wObj)}
                                className="w-5 h-5 rounded bg-slate-800 hover:bg-teal-500 hover:text-slate-950 text-teal-400 flex items-center justify-center transition shrink-0"
                                title="Listen to this word"
                              >
                                <Play className="w-2.5 h-2.5" />
                              </button>
                            </div>

                            {/* Timing Inputs (Start / End) */}
                            <div className="grid grid-cols-2 gap-1.5 font-mono text-[10px]">
                              <div>
                                <label className="text-[8px] text-slate-400 uppercase">Start (s)</label>
                                <div className="flex items-center gap-0.5">
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={wObj.start}
                                    onChange={(e) =>
                                      handleUpdateWordTimes(gIdx, parseFloat(e.target.value) || 0, wObj.end)
                                    }
                                    className="w-full bg-slate-950 border border-slate-700 rounded px-1 py-0.5 text-teal-300 font-bold outline-none"
                                  />
                                </div>
                              </div>

                              <div>
                                <label className="text-[8px] text-slate-400 uppercase">End (s)</label>
                                <div className="flex items-center gap-0.5">
                                  <input
                                    type="number"
                                    step="0.05"
                                    value={wObj.end}
                                    onChange={(e) =>
                                      handleUpdateWordTimes(gIdx, wObj.start, parseFloat(e.target.value) || 0)
                                    }
                                    className="w-full bg-slate-950 border border-slate-700 rounded px-1 py-0.5 text-teal-300 font-bold outline-none"
                                  />
                                </div>
                              </div>
                            </div>

                            {/* Nudge & Action Steppers */}
                            <div className="flex items-center justify-between gap-1 pt-1 border-t border-slate-800/60 text-[9px] font-mono">
                              <div className="flex items-center gap-0.5">
                                <button
                                  onClick={() => handleNudgeWord(gIdx, -0.05)}
                                  className="px-1 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold"
                                  title="Shift 50ms earlier"
                                >
                                  -50ms
                                </button>
                                <button
                                  onClick={() => handleNudgeWord(gIdx, 0.05)}
                                  className="px-1 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold"
                                  title="Shift 50ms later"
                                >
                                  +50ms
                                </button>
                              </div>

                              <div className="flex items-center gap-0.5">
                                <button
                                  onClick={() => handleInsertWordAfter(gIdx)}
                                  className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-400"
                                  title="Insert word after this"
                                >
                                  <Plus className="w-2.5 h-2.5" />
                                </button>
                                <button
                                  onClick={() => handleDeleteWord(gIdx)}
                                  className="p-1 rounded bg-slate-800 hover:bg-rose-900 text-rose-400"
                                  title="Delete word"
                                >
                                  <Trash2 className="w-2.5 h-2.5" />
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              }))}
            </div>
          )}

          {/* TAB 2: FLAT WORD TABLE VIEW */}
          {activeTab === 'words' && (
            <div className="bg-slate-950/70 rounded-xl border border-slate-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left font-mono text-xs">
                  <thead className="bg-slate-900 border-b border-slate-800 text-[10px] text-slate-400 uppercase tracking-wider">
                    <tr>
                      <th className="p-2.5 w-12 text-center">#</th>
                      <th className="p-2.5 min-w-[140px]">Word Text</th>
                      <th className="p-2.5 w-28">Start (sec)</th>
                      <th className="p-2.5 w-28">End (sec)</th>
                      <th className="p-2.5 w-24">Duration</th>
                      <th className="p-2.5 w-28">Beat Snap</th>
                      <th className="p-2.5 w-32 text-center">Quick Nudge</th>
                      <th className="p-2.5 w-28 text-center">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {words.map((w, idx) => {
                      const isActive = activeWordIdx === idx;
                      const dur = (w.end - w.start).toFixed(2);

                      return (
                        <tr
                          key={w._id || idx}
                          className={`transition ${
                            isActive ? 'bg-teal-950/40 text-teal-300 font-bold' : 'hover:bg-slate-900/60'
                          }`}
                        >
                          <td className="p-2.5 text-center text-slate-500 text-[10px]">{idx + 1}</td>
                          <td className="p-2.5">
                            <input
                              type="text"
                              value={w.word}
                              onChange={(e) => handleUpdateWordText(idx, e.target.value)}
                              className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs text-white font-bold focus:border-teal-500 focus:outline-none"
                            />
                          </td>
                          <td className="p-2.5">
                            <input
                              type="number"
                              step="0.05"
                              value={w.start}
                              onChange={(e) =>
                                handleUpdateWordTimes(idx, parseFloat(e.target.value) || 0, w.end)
                              }
                              className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-1 text-xs text-teal-300 outline-none font-bold"
                            />
                          </td>
                          <td className="p-2.5">
                            <input
                              type="number"
                              step="0.05"
                              value={w.end}
                              onChange={(e) =>
                                handleUpdateWordTimes(idx, w.start, parseFloat(e.target.value) || 0)
                              }
                              className="w-full bg-slate-900 border border-slate-700 rounded px-1.5 py-1 text-xs text-teal-300 outline-none font-bold"
                            />
                          </td>
                          <td className="p-2.5 text-slate-400 text-[11px]">{dur}s</td>
                          <td className="p-2.5">
                            {w.beat_index !== null && w.beat_index !== undefined ? (
                              <span className="px-1.5 py-0.5 rounded bg-teal-950 text-teal-400 border border-teal-800 text-[10px] font-bold">
                                Beat #{w.beat_index + 1}
                              </span>
                            ) : (
                              <span className="text-[10px] text-slate-500">Unsnapped</span>
                            )}
                          </td>
                          <td className="p-2.5">
                            <div className="flex items-center justify-center gap-1">
                              <button
                                onClick={() => handleNudgeWord(idx, -0.05)}
                                className="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px]"
                              >
                                -50ms
                              </button>
                              <button
                                onClick={() => handleNudgeWord(idx, 0.05)}
                                className="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px]"
                              >
                                +50ms
                              </button>
                            </div>
                          </td>
                          <td className="p-2.5 text-center">
                            <div className="flex items-center justify-center gap-1">
                              <button
                                onClick={() => handlePlayWordSnippet(w)}
                                className="p-1 rounded bg-slate-800 hover:bg-teal-500 hover:text-slate-950 text-teal-400"
                                title="Listen to word"
                              >
                                <Play className="w-3 h-3" />
                              </button>
                              <button
                                onClick={() => handleInsertWordAfter(idx)}
                                className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-400"
                                title="Insert word after"
                              >
                                <Plus className="w-3 h-3" />
                              </button>
                              <button
                                onClick={() => handleDeleteWord(idx)}
                                className="p-1 rounded bg-slate-800 hover:bg-rose-900 text-rose-400"
                                title="Delete word"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: RAW LYRICS & AI ALIGNMENT VIEW */}
          {activeTab === 'raw_text' && (
            <div className="space-y-4">
              <div className="bg-slate-950/70 p-3.5 rounded-xl border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-teal-400" />
                    Full Rhyming Song Lyrics
                  </label>
                  <button
                    onClick={handleTriggerRealign}
                    disabled={isRealigning || !lyricsText.trim()}
                    className="flex items-center gap-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 px-3 py-1 rounded-lg text-xs font-bold transition shadow"
                  >
                    <Sparkles className={`w-3.5 h-3.5 ${isRealigning ? 'animate-spin' : ''}`} />
                    <span>{isRealigning ? 'Aligning with AI...' : 'Re-align with MMS_FA'}</span>
                  </button>
                </div>
                <p className="text-[11px] text-slate-400">
                  Edit song structure, verse lines, or chorus sections. Click <strong>"Re-align with MMS_FA"</strong> to re-run the TorchAudio CTC trellis alignment model against your vocal track.
                </p>
                <textarea
                  rows={12}
                  value={lyricsText}
                  onChange={(e) => setLyricsText(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-700 rounded-xl p-3 font-mono text-xs text-white leading-relaxed focus:outline-none focus:border-teal-500"
                  placeholder="[Verse 1]&#10;Walking down the cobblestone road...&#10;&#10;[Chorus]&#10;Under the golden sunset sky..."
                />
              </div>
            </div>
          )}
        </div>

        {/* MODAL FOOTER */}
        <div className="px-4 py-3 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400 shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
            <span>Timeline changes sync live upon clicking "Apply to Timeline".</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-800 text-slate-300 transition font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="flex items-center gap-1.5 bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-slate-950 px-4 py-1.5 rounded-lg font-bold transition shadow"
            >
              <Check className="w-3.5 h-3.5" />
              <span>{isSaving ? 'Applying...' : 'Apply to Timeline'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
