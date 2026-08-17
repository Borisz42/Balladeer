import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import NewProjectModal from './components/NewProjectModal';
import AssetGallery from './components/AssetGallery';
import MusicStudio from './components/MusicStudio';
import TimelineEditor from './components/TimelineEditor';
import AssetSwapModal from './components/AssetSwapModal';
import VideoPlayerModal from './components/VideoPlayerModal';
import ModelManagerModal from './components/ModelManagerModal';
import {
  fetchHealth,
  fetchSystemSettings,
  updateSystemSettings,
  listProjects,
  getProject,
  createProject,
  uploadMediaFiles,
  indexDirectory,
  indexPendingMedia,
  generateMusic,
  uploadCustomAudio,
  solveTimeline,
  updateSlice,
  splitSlice,
  reorderSlices,
  renderVideo,
  subscribeProjectProgress,
  shutdownServer
} from './api';
import { Sparkles, Activity, CheckCircle2, AlertCircle, PowerOff, Check } from 'lucide-react';

export default function App() {
  const [health, setHealth] = useState(null);
  const [systemSettings, setSystemSettings] = useState(null);
  const [projects, setProjects] = useState([]);
  const [currentProjectId, setCurrentProjectId] = useState('');
  const [projectDetail, setProjectDetail] = useState(null);

  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [activeSwapSlice, setActiveSwapSlice] = useState(null);
  const [isVideoModalOpen, setIsVideoModalOpen] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [isShuttingDown, setIsShuttingDown] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [isGeneratingMusic, setIsGeneratingMusic] = useState(false);
  const [isSolvingTimeline, setIsSolvingTimeline] = useState(false);
  const [isRendering, setIsRendering] = useState(false);

  // SSE Live Progress State
  const [liveProgress, setLiveProgress] = useState(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    loadHealthAndProjects();
  }, []);

  useEffect(() => {
    if (currentProjectId) {
      loadProjectDetail(currentProjectId);

      // Setup SSE subscription
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
      eventSourceRef.current = subscribeProjectProgress(currentProjectId, (data) => {
        setLiveProgress(data);
        if (data.progress >= 100) {
          setTimeout(() => setLiveProgress(null), 3000);
        }
      });
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [currentProjectId]);

  const loadHealthAndProjects = async () => {
    try {
      const [hData, sData, pList] = await Promise.all([
        fetchHealth(),
        fetchSystemSettings().catch(() => null),
        listProjects()
      ]);
      setHealth(hData);
      setSystemSettings(sData);
      setProjects(pList);
      if (pList.length > 0 && !currentProjectId) {
        setCurrentProjectId(pList[0].id);
      }
    } catch (err) {
      console.error('Failed to load initial data:', err);
    }
  };

  const loadProjectDetail = async (id) => {
    setIsLoading(true);
    try {
      const detail = await getProject(id);
      setProjectDetail(detail);
    } catch (err) {
      console.error('Failed to load project detail:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleLocalAi = async (newValue) => {
    try {
      const updated = await updateSystemSettings({ only_local_ai: newValue });
      setSystemSettings(updated);
    } catch (err) {
      alert('Failed to toggle Local AI mode: ' + err.message);
    }
  };

  const handleCreateProject = async (title, narrativeText, configOverride) => {
    const newProj = await createProject(title, narrativeText, configOverride);
    await loadHealthAndProjects();
    setCurrentProjectId(newProj.id);
  };

  const handleUploadFiles = async (files) => {
    if (!currentProjectId) return;
    setIsLoading(true);
    try {
      await uploadMediaFiles(currentProjectId, files);
      await loadProjectDetail(currentProjectId);
    } catch (err) {
      alert('Upload failed: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleIndexDirectory = async (dirPath) => {
    if (!currentProjectId) return;
    setIsLoading(true);
    try {
      await indexDirectory(currentProjectId, dirPath);
      await loadProjectDetail(currentProjectId);
    } catch (err) {
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const handleIndexPending = async () => {
    if (!currentProjectId) return;
    setIsLoading(true);
    try {
      await indexPendingMedia(currentProjectId);
      await loadProjectDetail(currentProjectId);
    } catch (err) {
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const handleGenerateMusic = async (params) => {
    if (!currentProjectId) return;
    setIsGeneratingMusic(true);
    try {
      await generateMusic(currentProjectId, params);
      const detail = await getProject(currentProjectId);
      setProjectDetail(detail);
      
      // If assets are already indexed, automatically solve timeline
      if (detail.assets && detail.assets.length > 0) {
        try {
          await solveTimeline(currentProjectId);
          await loadProjectDetail(currentProjectId);
        } catch (solveErr) {
          console.warn('Timeline auto-solve deferred:', solveErr);
        }
      }
    } catch (err) {
      alert('Music generation failed: ' + err.message);
    } finally {
      setIsGeneratingMusic(false);
    }
  };

  const handleUploadCustomAudio = async (audioFile, bpm, isInstrumental) => {
    if (!currentProjectId) return;
    setIsGeneratingMusic(true);
    try {
      await uploadCustomAudio(currentProjectId, audioFile, { bpm, is_instrumental: isInstrumental });
      const detail = await getProject(currentProjectId);
      setProjectDetail(detail);

      if (detail.assets && detail.assets.length > 0) {
        try {
          await solveTimeline(currentProjectId);
          await loadProjectDetail(currentProjectId);
        } catch (solveErr) {
          console.warn('Timeline auto-solve deferred:', solveErr);
        }
      }
    } catch (err) {
      alert('Custom audio processing failed: ' + err.message);
    } finally {
      setIsGeneratingMusic(false);
    }
  };

  const handleSolveTimeline = async () => {
    if (!currentProjectId) return;
    setIsSolvingTimeline(true);
    try {
      await solveTimeline(currentProjectId);
      await loadProjectDetail(currentProjectId);
    } catch (err) {
      alert('Timeline solving: ' + err.message);
    } finally {
      setIsSolvingTimeline(false);
    }
  };

  const handleUpdateSliceBeatCount = async (sliceId, newBeatCount) => {
    try {
      await updateSlice(sliceId, { beat_count: newBeatCount });
      await loadProjectDetail(currentProjectId);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSplitSlice = async (sliceId, splitAtBeat) => {
    try {
      await splitSlice(currentProjectId, sliceId, splitAtBeat);
      await loadProjectDetail(currentProjectId);
    } catch (err) {
      alert('Split failed: ' + err.message);
    }
  };

  const handleReorderSlices = async (orderedIds) => {
    try {
      await reorderSlices(currentProjectId, orderedIds);
      await loadProjectDetail(currentProjectId);
    } catch (err) {
      console.error(err);
    }
  };

  const handleRenderVideo = async () => {
    if (!currentProjectId) return;
    setIsRendering(true);
    try {
      await renderVideo(currentProjectId);
      const checkInterval = setInterval(async () => {
        const detail = await getProject(currentProjectId);
        setProjectDetail(detail);
        if (detail.project.status === 'completed' || detail.rendered_video_url) {
          clearInterval(checkInterval);
          setIsRendering(false);
          setIsVideoModalOpen(true);
        } else if (detail.project.status === 'error') {
          clearInterval(checkInterval);
          setIsRendering(false);
          alert('Render failed: ' + detail.project.error_message);
        }
      }, 2000);
    } catch (err) {
      setIsRendering(false);
      alert('Render trigger failed: ' + err.message);
    }
  };

  const handleShutdown = async () => {
    const ok = window.confirm(
      'Are you sure you want to shut down the Balladeer server?\n\nSQLite database WAL checkpoints and GPU memory buffers will be cleanly released.'
    );
    if (!ok) return;

    try {
      await shutdownServer();
      setIsShuttingDown(true);
    } catch (err) {
      console.error('Shutdown request error:', err);
      setIsShuttingDown(true);
    }
  };

  if (isShuttingDown) {
    return (
      <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col items-center justify-center p-6 select-none">
        <div className="glass-panel max-w-md w-full rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-8 text-center space-y-4">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto shadow-xl shadow-emerald-500/10">
            <Check className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-white">Balladeer Server Stopped</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Database WAL checkpoints and GPU memory buffers have been cleanly flushed and released.
          </p>
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 text-xs font-mono text-slate-400">
            You may now safely close this browser tab and the Command Prompt window.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col">
      <Header
        projects={projects}
        currentProject={projectDetail?.project}
        onSelectProject={setCurrentProjectId}
        onOpenNewProject={() => setIsNewProjectModalOpen(true)}
        onOpenModelManager={() => setIsModelModalOpen(true)}
        onShutdown={handleShutdown}
        health={health}
        systemSettings={systemSettings}
        onToggleLocalAi={handleToggleLocalAi}
        onRefresh={() => {
          loadHealthAndProjects();
          if (currentProjectId) loadProjectDetail(currentProjectId);
        }}
      />

      {/* Live SSE Progress Toast Ribbon */}
      {liveProgress && (
        <div className="bg-slate-900 border-b border-teal-500/30 px-6 py-2.5 flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2 text-teal-300">
            <Activity className="w-4 h-4 animate-spin text-teal-400" />
            <span>
              [{liveProgress.phase.toUpperCase()}] {liveProgress.message}
            </span>
          </div>
          <div className="flex items-center gap-3 w-48">
            <div className="flex-1 bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
              <div
                className="bg-gradient-to-r from-teal-500 to-cyan-400 h-full transition-all duration-300"
                style={{ width: `${liveProgress.progress}%` }}
              />
            </div>
            <span className="font-bold text-white">{liveProgress.progress}%</span>
          </div>
        </div>
      )}

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6">
        {!projectDetail ? (
          <div className="py-24 text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-teal-500/20 text-teal-400 flex items-center justify-center mx-auto shadow-xl shadow-teal-500/20">
              <Sparkles className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-white">Welcome to Balladeer</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Create your first project to turn your travel diary, photos, and video clips into a beat-synced AI musical montage.
            </p>
            <button
              onClick={() => setIsNewProjectModalOpen(true)}
              className="px-5 py-2.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-sm shadow-lg shadow-teal-500/20 transition"
            >
              Create New Project
            </button>
          </div>
        ) : (
          <>
            <AssetGallery
              project={projectDetail.project}
              assets={projectDetail.assets}
              onUploadFiles={handleUploadFiles}
              onIndexDirectory={handleIndexDirectory}
              onIndexPending={handleIndexPending}
              onAssetUpdated={() => loadProjectDetail(currentProjectId)}
              isLoading={isLoading}
            />

            <MusicStudio
              project={projectDetail.project}
              audioTrack={projectDetail.audio_track}
              onGenerateMusic={handleGenerateMusic}
              onUploadAudio={handleUploadCustomAudio}
              isGenerating={isGeneratingMusic}
              health={health}
            />

            <TimelineEditor
              project={projectDetail.project}
              audioTrack={projectDetail.audio_track}
              slices={projectDetail.timeline_slices}
              onOpenSwapModal={(slice) => setActiveSwapSlice(slice)}
              onUpdateSliceBeatCount={handleUpdateSliceBeatCount}
              onSplitSlice={handleSplitSlice}
              onReorderSlices={handleReorderSlices}
              onSolveTimeline={handleSolveTimeline}
              onRenderVideo={handleRenderVideo}
              isSolving={isSolvingTimeline}
              isRendering={isRendering}
            />
          </>
        )}
      </main>

      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onCreate={handleCreateProject}
      />

      <AssetSwapModal
        isOpen={!!activeSwapSlice}
        onClose={() => setActiveSwapSlice(null)}
        project={projectDetail?.project}
        slice={activeSwapSlice}
        onAssetSwapped={() => loadProjectDetail(currentProjectId)}
      />

      <VideoPlayerModal
        isOpen={isVideoModalOpen}
        onClose={() => setIsVideoModalOpen(false)}
        project={projectDetail?.project}
        videoUrl={projectDetail?.rendered_video_url ? `http://localhost:8000${projectDetail.rendered_video_url}` : null}
      />

      <ModelManagerModal
        isOpen={isModelModalOpen}
        onClose={() => {
          setIsModelModalOpen(false);
          loadHealthAndProjects();
        }}
      />
    </div>
  );
}
