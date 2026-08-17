import React, { useState, useEffect } from 'react';
import { X, BookOpen, Save, Sparkles, Check, AlertCircle } from 'lucide-react';
import StructuredDiaryInput from './StructuredDiaryInput';

export default function DiaryEditorModal({ isOpen, onClose, project, onSave }) {
  const [title, setTitle] = useState('');
  const [currentDays, setCurrentDays] = useState([]);
  const [currentNarrativeText, setCurrentNarrativeText] = useState('');
  const [dateRange, setDateRange] = useState({ startDate: '', finishDate: '' });
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (project) {
      setTitle(project.title || '');
      const cfg = project.config_override || {};
      const initDays = cfg.diary_days || [];
      setCurrentDays(initDays);
      setCurrentNarrativeText(project.narrative_text || '');
      setDateRange({
        startDate: cfg.start_date || '',
        finishDate: cfg.finish_date || ''
      });
      setSaveSuccess(false);
    }
  }, [project, isOpen]);

  if (!isOpen || !project) return null;

  const handleDiaryChange = (days, narrativeText, { startDate, finishDate }) => {
    setCurrentDays(days);
    setCurrentNarrativeText(narrativeText);
    setDateRange({ startDate, finishDate });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const existingConfig = project.config_override || {};
      const updatedConfig = {
        ...existingConfig,
        start_date: dateRange.startDate,
        finish_date: dateRange.finishDate,
        diary_days: currentDays
      };

      await onSave(title, currentNarrativeText, updatedConfig);
      setSaveSuccess(true);
      setTimeout(() => {
        setSaveSuccess(false);
        onClose();
      }, 800);
    } catch (err) {
      alert('Failed to save diary changes: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="glass-panel w-full max-w-3xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative max-h-[92vh] flex flex-col">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-teal-500/20 to-cyan-500/20 border border-teal-500/30 text-teal-400 flex items-center justify-center shadow-lg shadow-teal-500/10">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white">Trip Diary &amp; Day-by-Day Schedule</h2>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-400 border border-teal-500/30">
                  Live Project Editor
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Structure itinerary dates, toggle discarded days, and polish travel notes with AI.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="py-4 space-y-4 overflow-y-auto flex-1 pr-1">
          {/* Project Title Field */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Project Title
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3.5 py-2 text-sm text-white focus:outline-none focus:border-teal-500 font-semibold"
            />
          </div>

          {/* Structured Day-by-Day Input Component */}
          <StructuredDiaryInput
            initialDays={project.config_override?.diary_days}
            initialNarrativeText={project.narrative_text}
            initialStartDate={project.config_override?.start_date}
            initialFinishDate={project.config_override?.finish_date}
            onChange={handleDiaryChange}
          />
        </div>

        {/* Modal Footer */}
        <div className="pt-4 border-t border-slate-800 flex items-center justify-between shrink-0">
          <div className="text-xs text-slate-400">
            Saving will sync media asset tags and update narrative acts.
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-800 transition font-medium"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving || saveSuccess}
              className={`flex items-center gap-1.5 px-5 py-2 rounded-lg text-sm font-bold transition shadow-lg ${
                saveSuccess
                  ? 'bg-emerald-500 text-slate-950 shadow-emerald-500/20'
                  : 'bg-teal-500 hover:bg-teal-400 text-slate-950 shadow-teal-500/20'
              }`}
            >
              {saveSuccess ? (
                <>
                  <Check className="w-4 h-4" />
                  Saved!
                </>
              ) : isSaving ? (
                'Saving...'
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Save &amp; Sync Diary
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
