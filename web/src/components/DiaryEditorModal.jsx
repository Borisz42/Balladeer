import React, { useState, useEffect } from 'react';
import { X, BookOpen, Save, Sparkles, Check, AlertCircle, Wand2, CheckCircle2 } from 'lucide-react';
import StructuredDiaryInput from './StructuredDiaryInput';
import { draftTravelLog, approveTravelLog } from '../api';

export default function DiaryEditorModal({ isOpen, onClose, project, onSave, onApprove }) {
  const [title, setTitle] = useState('');
  const [currentDays, setCurrentDays] = useState([]);
  const [currentNarrativeText, setCurrentNarrativeText] = useState('');
  const [dateRange, setDateRange] = useState({ startDate: '', finishDate: '' });
  const [isSaving, setIsSaving] = useState(false);
  const [isDrafting, setIsDrafting] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [approvalSuccess, setApprovalSuccess] = useState(false);

  const isApproved = project?.config_override?.travel_log_approved ?? true;
  const isAutoDraftMode = project?.config_override?.travel_log_mode === 'auto_draft';

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
      setApprovalSuccess(false);
    }
  }, [project, isOpen]);

  if (!isOpen || !project) return null;

  const handleDiaryChange = (days, narrativeText, { startDate, finishDate }) => {
    setCurrentDays(days);
    setCurrentNarrativeText(narrativeText);
    setDateRange({ startDate, finishDate });
  };

  const handleDraftFromMedia = async () => {
    setIsDrafting(true);
    try {
      const res = await draftTravelLog(project.id);
      if (res.draft) {
        setCurrentDays(res.draft.diary_days || []);
        setCurrentNarrativeText(res.draft.narrative_text || '');
        setDateRange({
          startDate: res.draft.start_date || '',
          finishDate: res.draft.finish_date || ''
        });
      }
    } catch (err) {
      alert('Failed to draft travel log from media: ' + err.message);
    } finally {
      setIsDrafting(false);
    }
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

  const handleApproveAndCalculateRelevance = async () => {
    setIsApproving(true);
    try {
      const existingConfig = project.config_override || {};
      const updatedConfig = {
        ...existingConfig,
        start_date: dateRange.startDate,
        finish_date: dateRange.finishDate,
        diary_days: currentDays
      };

      if (onApprove) {
        await onApprove(title, currentNarrativeText, updatedConfig);
      } else {
        await approveTravelLog(project.id, {
          title,
          narrativeText: currentNarrativeText,
          configOverride: updatedConfig
        });
      }

      setApprovalSuccess(true);
      setTimeout(() => {
        setApprovalSuccess(false);
        onClose();
      }, 900);
    } catch (err) {
      alert('Failed to approve travel log: ' + err.message);
    } finally {
      setIsApproving(false);
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
                <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded border ${
                  isApproved
                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                    : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                }`}>
                  {isApproved ? 'Approved & Scored' : 'Approval Pending'}
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Structure itinerary dates, toggle discarded days, and polish travel notes with AI.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDraftFromMedia}
              disabled={isDrafting}
              className="flex items-center gap-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition shadow-sm"
              title="Auto-draft itinerary from imported media descriptions and dates"
            >
              <Wand2 className={`w-3.5 h-3.5 ${isDrafting ? 'animate-spin' : ''}`} />
              <span>{isDrafting ? 'Drafting Log...' : 'Draft from Media'}</span>
            </button>

            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
              title="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="py-4 space-y-4 overflow-y-auto flex-1 pr-1">
          {/* Unapproved Notice Banner */}
          {!isApproved && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-200">
                <span className="font-bold">Travel Log Review Required:</span> Media relevance scores are pending. Once you verify and approve this itinerary, the system will calculate visual relevance metrics for all media assets.
              </div>
            </div>
          )}

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
            key={`diary_${currentDays.length}_${dateRange.startDate}`}
            initialDays={currentDays}
            initialNarrativeText={currentNarrativeText}
            initialStartDate={dateRange.startDate}
            initialFinishDate={dateRange.finishDate}
            onChange={handleDiaryChange}
          />
        </div>

        {/* Modal Footer */}
        <div className="pt-4 border-t border-slate-800 flex items-center justify-between shrink-0">
          <div className="text-xs text-slate-400">
            {isApproved
              ? 'Saving will sync media asset tags and narrative acts.'
              : 'Approving calculates relevance scores across all media.'}
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-800 transition font-medium"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving || saveSuccess || isApproving}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition border ${
                saveSuccess
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                  : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border-slate-700'
              }`}
            >
              {saveSuccess ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  Saved
                </>
              ) : isSaving ? (
                'Saving...'
              ) : (
                <>
                  <Save className="w-3.5 h-3.5" />
                  Save Draft
                </>
              )}
            </button>

            <button
              type="button"
              onClick={handleApproveAndCalculateRelevance}
              disabled={isApproving || approvalSuccess || isSaving}
              className={`flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-bold transition shadow-lg ${
                approvalSuccess
                  ? 'bg-emerald-500 text-slate-950 shadow-emerald-500/20'
                  : 'bg-gradient-to-r from-teal-500 to-cyan-500 hover:from-teal-400 hover:to-cyan-400 text-slate-950 shadow-teal-500/20'
              }`}
            >
              {approvalSuccess ? (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  Approved &amp; Scored!
                </>
              ) : isApproving ? (
                'Scoring Media...'
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  {isApproved ? 'Approve & Recalculate Scores' : 'Approve & Calculate Relevance'}
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

