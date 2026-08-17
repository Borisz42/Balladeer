import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Sparkles,
  Plus,
  Trash2,
  EyeOff,
  RotateCcw,
  Clock,
  Check,
  AlertCircle,
  Wand2,
  FileText,
  ListOrdered
} from 'lucide-react';
import { rephraseDiary } from '../api';

function formatLocalDate(d) {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function getDayOfWeek(dateStr) {
  if (!dateStr) return '';
  try {
    const parts = dateStr.split('-');
    if (parts.length === 3) {
      const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
      return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
    }
  } catch (e) {
    return '';
  }
  return '';
}

function generateDaysRange(startStr, finishStr, existingDays = []) {
  if (!startStr || !finishStr) return [];
  const start = new Date(startStr);
  const finish = new Date(finishStr);
  if (isNaN(start.getTime()) || isNaN(finish.getTime()) || start > finish) {
    return [];
  }

  const generated = [];
  const cur = new Date(start);
  let dayNum = 1;

  while (cur <= finish) {
    const curStr = formatLocalDate(cur);
    const existing = existingDays.find(
      (d) => d.date === curStr || d.day_number === dayNum
    );

    generated.push({
      id: existing?.id || `day_${dayNum}_${curStr}`,
      day_number: dayNum,
      date: curStr,
      title: existing?.title || `Day ${dayNum}`,
      events: existing?.events || '',
      is_active: existing ? existing.is_active : true,
      is_discarded: existing ? !!existing.is_discarded : false
    });

    cur.setDate(cur.getDate() + 1);
    dayNum++;
  }

  return generated;
}

export default function StructuredDiaryInput({
  initialDays = [],
  initialNarrativeText = '',
  initialStartDate = '',
  initialFinishDate = '',
  onChange
}) {
  const today = formatLocalDate(new Date());
  const threeDaysLater = formatLocalDate(new Date(Date.now() + 2 * 24 * 60 * 60 * 1000));

  const [startDate, setStartDate] = useState(initialStartDate || today);
  const [finishDate, setFinishDate] = useState(initialFinishDate || threeDaysLater);
  const [days, setDays] = useState([]);
  const [rephrasingDayId, setRephrasingDayId] = useState(null);
  const [isRephrasingAll, setIsRephrasingAll] = useState(false);
  const [showRawText, setShowRawText] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState(null);

  // Initialize days
  useEffect(() => {
    if (initialDays && initialDays.length > 0) {
      setDays(initialDays);
      if (initialStartDate) setStartDate(initialStartDate);
      if (initialFinishDate) setFinishDate(initialFinishDate);
    } else if (initialNarrativeText) {
      // Parse days from narrative text
      const parsed = parseNarrativeToDays(initialNarrativeText, startDate, finishDate);
      setDays(parsed);
    } else {
      const generated = generateDaysRange(startDate, finishDate);
      setDays(generated);
    }
  }, []);

  // Emit changes to parent
  useEffect(() => {
    if (days.length > 0 && onChange) {
      const formattedNarrative = buildFormattedNarrative(days);
      onChange(days, formattedNarrative, { startDate, finishDate });
    }
  }, [days, startDate, finishDate]);

  function parseNarrativeToDays(text, sDate, fDate) {
    const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return generateDaysRange(sDate, fDate);

    const parsedDays = [];
    let curDate = new Date(sDate);
    let dayCounter = 1;

    for (const line of lines) {
      const match = line.match(/^(?:day|stage|act)\s*(\d+)(?:\s*\(([^)]*)\))?:\s*(.*)$/i);
      if (match) {
        const dNum = parseInt(match[1]) || dayCounter;
        const dDate = match[2] || formatLocalDate(curDate);
        const events = match[3] || '';
        parsedDays.push({
          id: `day_${dNum}_${dDate}`,
          day_number: dNum,
          date: dDate,
          title: `Day ${dNum}`,
          events,
          is_active: true,
          is_discarded: false
        });
        curDate.setDate(curDate.getDate() + 1);
        dayCounter = dNum + 1;
      } else {
        parsedDays.push({
          id: `day_${dayCounter}_${formatLocalDate(curDate)}`,
          day_number: dayCounter,
          date: formatLocalDate(curDate),
          title: `Day ${dayCounter}`,
          events: line,
          is_active: true,
          is_discarded: false
        });
        curDate.setDate(curDate.getDate() + 1);
        dayCounter++;
      }
    }
    return parsedDays;
  }

  function buildFormattedNarrative(daysList) {
    const activeDays = daysList.filter((d) => !d.is_discarded && d.is_active);
    return activeDays
      .map((d) => {
        const datePart = d.date ? ` (${d.date})` : '';
        return `Day ${d.day_number}${datePart}: ${d.events.trim()}`;
      })
      .join('\n');
  }

  const handleDateRangeRegenerate = () => {
    const updated = generateDaysRange(startDate, finishDate, days);
    setDays(updated);
    showNotice(`Generated ${updated.length} days from ${startDate} to ${finishDate}`);
  };

  const handleUpdateDay = (index, updates) => {
    const updated = [...days];
    updated[index] = { ...updated[index], ...updates };
    setDays(updated);
  };

  const handleToggleDiscard = (index) => {
    const updated = [...days];
    const isCurrentlyDiscarded = !!updated[index].is_discarded;
    updated[index] = {
      ...updated[index],
      is_discarded: !isCurrentlyDiscarded,
      is_active: isCurrentlyDiscarded // activate if was discarded, deactivate if discarding
    };
    setDays(updated);
    showNotice(
      isCurrentlyDiscarded
        ? `Day ${updated[index].day_number} restored to story.`
        : `Day ${updated[index].day_number} discarded from montage.`
    );
  };

  const handleAddDay = () => {
    const lastDay = days[days.length - 1];
    let nextDate = today;
    let nextDayNum = days.length + 1;

    if (lastDay && lastDay.date) {
      try {
        const d = new Date(lastDay.date);
        d.setDate(d.getDate() + 1);
        nextDate = formatLocalDate(d);
        nextDayNum = lastDay.day_number + 1;
      } catch (e) {
        // fallback
      }
    }

    const newDay = {
      id: `day_${nextDayNum}_${nextDate}`,
      day_number: nextDayNum,
      date: nextDate,
      title: `Day ${nextDayNum}`,
      events: '',
      is_active: true,
      is_discarded: false
    };

    setDays([...days, newDay]);
    setFinishDate(nextDate);
  };

  const handleRemoveDay = (index) => {
    const updated = days.filter((_, i) => i !== index);
    // Renumber days
    const renumbered = updated.map((d, i) => ({
      ...d,
      day_number: i + 1,
      title: d.title.startsWith('Day ') ? `Day ${i + 1}` : d.title
    }));
    setDays(renumbered);
  };

  const handleRephraseSingleDay = async (index) => {
    const day = days[index];
    setRephrasingDayId(day.id);
    try {
      const res = await rephraseDiary({
        text: day.events,
        day_number: day.day_number,
        date: day.date,
        mode: 'single_day'
      });
      if (res.rephrased_text) {
        handleUpdateDay(index, { events: res.rephrased_text });
        showNotice(`Day ${day.day_number} re-phrased and spelling corrected!`);
      }
    } catch (err) {
      alert('AI Re-phrase failed: ' + err.message);
    } finally {
      setRephrasingDayId(null);
    }
  };

  const handleRephraseAllDays = async () => {
    if (days.length === 0) return;
    setIsRephrasingAll(true);
    try {
      const res = await rephraseDiary({
        days: days,
        mode: 'structured_days'
      });
      if (res.rephrased_days) {
        setDays(res.rephrased_days);
        showNotice('All active days re-phrased with AI & spelling errors fixed!');
      }
    } catch (err) {
      alert('AI Re-phrase failed: ' + err.message);
    } finally {
      setIsRephrasingAll(false);
    }
  };

  const handleLoadSampleItinerary = () => {
    const s = '2026-08-17';
    const f = '2026-08-19';
    setStartDate(s);
    setFinishDate(f);
    const sample = [
      {
        id: 'sample_1',
        day_number: 1,
        date: '2026-08-17',
        title: 'Day 1 - Kyoto Arrival',
        events: 'Arrived in Kyoto amidst gentle autumn rain. Walked through the historic Gion district under red paper lanterns.',
        is_active: true,
        is_discarded: false
      },
      {
        id: 'sample_2',
        day_number: 2,
        date: '2026-08-18',
        title: 'Day 2 - Bamboo Grove',
        events: 'Morning stroll through the whispering Arashiyama bamboo forest. Golden sunlight piercing through the towering stalks.',
        is_active: true,
        is_discarded: false
      },
      {
        id: 'sample_3',
        day_number: 3,
        date: '2026-08-19',
        title: 'Day 3 - Tokyo Neon',
        events: 'Shinkansen bullet train to Tokyo. Neon lights blazing across the bustling Shibuya crossing at midnight.',
        is_active: true,
        is_discarded: false
      }
    ];
    setDays(sample);
    showNotice('Loaded sample Kyoto & Tokyo itinerary.');
  };

  const showNotice = (msg) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 3500);
  };

  const activeCount = days.filter((d) => !d.is_discarded).length;
  const discardedCount = days.filter((d) => d.is_discarded).length;

  return (
    <div className="space-y-4">
      {/* Toast Notice */}
      {feedbackMsg && (
        <div className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-teal-500/10 border border-teal-500/30 text-teal-300 text-xs animate-fadeIn">
          <Check className="w-3.5 h-3.5 text-teal-400" />
          <span>{feedbackMsg}</span>
        </div>
      )}

      {/* Date Range Controls Bar */}
      <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-teal-400" />
            <span className="text-xs font-semibold text-slate-300">Trip Dates:</span>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1">
              <span className="text-[11px] text-slate-400 font-mono">Start</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-transparent text-xs text-white focus:outline-none font-mono cursor-pointer"
              />
            </div>

            <span className="text-slate-500 text-xs">to</span>

            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1">
              <span className="text-[11px] text-slate-400 font-mono">Finish</span>
              <input
                type="date"
                value={finishDate}
                onChange={(e) => setFinishDate(e.target.value)}
                className="bg-transparent text-xs text-white focus:outline-none font-mono cursor-pointer"
              />
            </div>

            <button
              type="button"
              onClick={handleDateRangeRegenerate}
              className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs border border-slate-700 font-medium transition"
              title="Apply date range and sync day list"
            >
              Update Dates
            </button>
          </div>
        </div>

        {/* Quick Stats & View Switcher */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-300 border border-teal-500/20">
            {activeCount} Active {activeCount === 1 ? 'Day' : 'Days'}
          </span>
          {discardedCount > 0 && (
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
              {discardedCount} Discarded
            </span>
          )}

          <button
            type="button"
            onClick={handleLoadSampleItinerary}
            className="text-xs text-teal-400 hover:text-teal-300 underline font-medium ml-2"
          >
            Sample Diary
          </button>
        </div>
      </div>

      {/* Action Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-1">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleRephraseAllDays}
            disabled={isRephrasingAll || days.length === 0}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gradient-to-r from-teal-500/20 to-cyan-500/20 hover:from-teal-500/30 hover:to-cyan-500/30 text-teal-300 border border-teal-500/40 text-xs font-bold transition shadow-sm"
          >
            <Sparkles className={`w-3.5 h-3.5 text-teal-400 ${isRephrasingAll ? 'animate-spin' : ''}`} />
            {isRephrasingAll ? 'Re-phrasing All Days...' : 'AI Re-phrase All Days & Fix Spelling'}
          </button>

          <button
            type="button"
            onClick={handleAddDay}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium transition"
          >
            <Plus className="w-3.5 h-3.5 text-teal-400" />
            Add Day
          </button>
        </div>

        <button
          type="button"
          onClick={() => setShowRawText(!showRawText)}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition font-mono"
        >
          {showRawText ? <ListOrdered className="w-3.5 h-3.5" /> : <FileText className="w-3.5 h-3.5" />}
          {showRawText ? 'Switch to Card View' : 'Preview Narrative Text'}
        </button>
      </div>

      {/* Raw Text Preview Mode */}
      {showRawText ? (
        <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Formatted Multi-Act Narrative Text:</span>
            <span className="font-mono text-[11px] text-teal-400">{activeCount} active acts</span>
          </div>
          <pre className="p-3 bg-slate-900/90 rounded-lg border border-slate-800 text-xs font-mono text-slate-200 whitespace-pre-wrap leading-relaxed">
            {buildFormattedNarrative(days) || '(No active day events written yet)'}
          </pre>
        </div>
      ) : (
        /* Structured Day Cards List */
        <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1">
          {days.length === 0 ? (
            <div className="p-8 text-center border border-dashed border-slate-800 rounded-xl space-y-2 text-slate-400">
              <Calendar className="w-8 h-8 mx-auto text-slate-600" />
              <p className="text-sm">No days in itinerary.</p>
              <button
                type="button"
                onClick={handleDateRangeRegenerate}
                className="px-3 py-1.5 rounded-lg bg-teal-500 text-slate-950 text-xs font-bold"
              >
                Generate from Date Range
              </button>
            </div>
          ) : (
            days.map((day, idx) => {
              const isDiscarded = !!day.is_discarded;
              const isRephrasingThis = rephrasingDayId === day.id;
              const weekday = getDayOfWeek(day.date);

              return (
                <div
                  key={day.id || idx}
                  className={`p-3.5 rounded-xl border transition-all duration-200 ${
                    isDiscarded
                      ? 'bg-slate-950/60 border-slate-800/60 opacity-60'
                      : 'bg-slate-900/90 border-slate-700/80 shadow-md hover:border-slate-600'
                  }`}
                >
                  {/* Card Header */}
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold px-2.5 py-0.5 rounded-md font-mono ${
                          isDiscarded
                            ? 'bg-slate-800 text-slate-400'
                            : 'bg-teal-500/20 text-teal-300 border border-teal-500/30'
                        }`}
                      >
                        Day {day.day_number}
                      </span>

                      {/* Date Field */}
                      <div className="flex items-center gap-1.5 bg-slate-950 border border-slate-800 rounded px-2 py-0.5">
                        <input
                          type="date"
                          value={day.date || ''}
                          disabled={isDiscarded}
                          onChange={(e) => handleUpdateDay(idx, { date: e.target.value })}
                          className="bg-transparent text-xs text-slate-300 focus:outline-none font-mono cursor-pointer"
                        />
                        {weekday && (
                          <span className="text-[11px] text-slate-400 font-sans border-l border-slate-800 pl-1.5">
                            {weekday}
                          </span>
                        )}
                      </div>

                      {/* Discarded/Active Badge */}
                      {isDiscarded ? (
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          Discarded / Excluded
                        </span>
                      ) : (
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          Active
                        </span>
                      )}
                    </div>

                    {/* Card Actions */}
                    <div className="flex items-center gap-1.5">
                      {/* Re-phrase Single Day Button */}
                      {!isDiscarded && (
                        <button
                          type="button"
                          onClick={() => handleRephraseSingleDay(idx)}
                          disabled={isRephrasingThis || !day.events.trim()}
                          className="flex items-center gap-1 px-2.5 py-1 rounded bg-teal-950/40 hover:bg-teal-900/60 text-teal-300 border border-teal-800/60 text-[11px] font-semibold transition disabled:opacity-40"
                          title="Re-phrase this day's events and fix spelling with AI"
                        >
                          <Wand2 className={`w-3 h-3 text-teal-400 ${isRephrasingThis ? 'animate-spin' : ''}`} />
                          {isRephrasingThis ? 'Re-phrasing...' : 'Re-phrase'}
                        </button>
                      )}

                      {/* Discard / Bring Back Button */}
                      <button
                        type="button"
                        onClick={() => handleToggleDiscard(idx)}
                        className={`flex items-center gap-1 px-2.5 py-1 rounded text-[11px] font-medium border transition ${
                          isDiscarded
                            ? 'bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-300 border-emerald-800/60'
                            : 'bg-amber-950/30 hover:bg-amber-900/50 text-amber-300 border-amber-800/50'
                        }`}
                        title={isDiscarded ? 'Bring back this day to the musical story' : 'Discard this day from the montage'}
                      >
                        {isDiscarded ? (
                          <>
                            <RotateCcw className="w-3 h-3" />
                            Bring Back
                          </>
                        ) : (
                          <>
                            <EyeOff className="w-3 h-3" />
                            Discard
                          </>
                        )}
                      </button>

                      {/* Delete Custom Day Button */}
                      {days.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveDay(idx)}
                          className="p-1 rounded text-slate-500 hover:text-rose-400 hover:bg-slate-800 transition"
                          title="Delete day entry"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Card Body: Event Text Area */}
                  {isDiscarded ? (
                    <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/40 text-xs text-slate-500 flex items-center justify-between">
                      <span className="italic">
                        Day {day.day_number} events are excluded from the musical narrative. Click &quot;Bring Back&quot; to restore.
                      </span>
                    </div>
                  ) : (
                    <div>
                      <textarea
                        rows={2}
                        value={day.events || ''}
                        onChange={(e) => handleUpdateDay(idx, { events: e.target.value })}
                        placeholder={`Write events, sights, emotions, or places visited on Day ${day.day_number}...`}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 transition leading-relaxed font-sans"
                      />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
