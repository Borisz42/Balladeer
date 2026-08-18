import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import NewProjectModal from './components/NewProjectModal';
import DiaryEditorModal from './components/DiaryEditorModal';
import AssetGallery from './components/AssetGallery';
import AssetDetailPane from './components/AssetDetailPane';
import VideoPlayerPane from './components/VideoPlayerPane';
import MusicStudio from './components/MusicStudio';
import TimelineEditor from './components/TimelineEditor';
import AssetSwapModal from './components/AssetSwapModal';
import ModelManagerModal from './components/ModelManagerModal';
import ProjectManagerModal from './components/ProjectManagerModal';
import RenameProjectModal from './components/RenameProjectModal';
import DeleteConfirmModal from './components/DeleteConfirmModal';
import {
  fetchHealth,
  fetchSystemSettings,
  updateSystemSettings,
  listProjects,
  getProject,
  createProject,
  renameProject,
  deleteProject,
  batchDeleteProjects,
  updateProjectDiary,
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

  // Active selected asset for Inspector
  const [selectedAsset, setSelectedAsset] = useState(null);

  // Synchronized Global Real-Time Playback State
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const audioRef = useRef(null);

  const [isNewProjectModalOpen, setIsNewProjectModalOpen] = useState(false);
  const [isDiaryModalOpen, setIsDiaryModalOpen] = useState(false);
  const [activeSwapSlice, setActiveSwapSlice] = useState(null);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [isProjectManagerOpen, setIsProjectManagerOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
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

  // Smooth 60 FPS real-time render clock when playing
  useEffect(() => {
    let animId;
    if (isPlaying) {
      const tick = () => {
        if (audioRef.current) {
          setCurrentTime(audioRef.current.currentTime);
        }
        animId = requestAnimationFrame(tick);
      };
      animId = requestAnimationFrame(tick);
    }
    return () => {
      if (animId) cancelAnimationFrame(animId);
    };
  }, [isPlaying]);

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

      // Keep selectedAsset in sync
      if (selectedAsset && detail.assets) {
        const found = detail.assets.find((a) => a.id === selectedAsset.id);
        if (found) setSelectedAsset(found);
      } else if (detail.assets && detail.assets.length > 0 && !selectedAsset) {
        setSelectedAsset(detail.assets[0]);
      }
    } catch (err) {
      console.error('Failed to load project detail:', err);
    } finally {
      setIsLoading(false);
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

  const handleSeek = (newTime) => {
    if (audioRef.current) {
      audioRef.current.currentTime = newTime;
    }
    setCurrentTime(newTime);
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

  const handleRenameProject = async (id, newTitle) => {
    try {
      await renameProject(id, newTitle);
      setProjects((prev) =>
        prev.map((p) => (p.id === id ? { ...p, title: newTitle } : p))
      );
      if (currentProjectId === id) {
        setProjectDetail((prev) =>
          prev ? { ...prev, project: { ...prev.project, title: newTitle } } : prev
        );
      }
    } catch (err) {
      console.error('Failed to rename project:', err);
      throw err;
    }
  };

  const handleDeleteProject = async (id) => {
    setIsDeleting(true);
    try {
      await deleteProject(id);
      const remaining = projects.filter((p) => p.id !== id);
      setProjects(remaining);

      if (currentProjectId === id) {
        if (remaining.length > 0) {
          setCurrentProjectId(remaining[0].id);
        } else {
          setCurrentProjectId('');
          setProjectDetail(null);
          setSelectedAsset(null);
        }
      }
      setIsDeleteModalOpen(false);
    } catch (err) {
      console.error('Failed to delete project:', err);
      alert('Failed to delete project: ' + err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleBatchDeleteProjects = async (ids) => {
    if (!ids || ids.length === 0) return;
    setIsDeleting(true);
    try {
      await batchDeleteProjects(ids);
      const idSet = new Set(ids);
      const remaining = projects.filter((p) => !idSet.has(p.id));
      setProjects(remaining);

      if (idSet.has(currentProjectId)) {
        if (remaining.length > 0) {
          setCurrentProjectId(remaining[0].id);
        } else {
          setCurrentProjectId('');
          setProjectDetail(null);
          setSelectedAsset(null);
        }
      }
    } catch (err) {
      console.error('Failed to batch delete projects:', err);
      alert('Failed to delete projects: ' + err.message);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSaveDiary = async (title, narrativeText, configOverride) => {
    if (!currentProjectId) return;
    try {
      await updateProjectDiary(currentProjectId, { title, narrativeText, configOverride });
      await loadProjectDetail(currentProjectId);
      await loadHealthAndProjects();
    } catch (err) {
      console.error('Failed to save project diary:', err);
      throw err;
    }
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

  const renderedVideoUrl = projectDetail?.rendered_video_url
    ? `http://localhost:8000${projectDetail.rendered_video_url}`
    : null;

  return (
    <div className="h-screen bg-[#070b14] text-slate-100 flex flex-col overflow-hidden">
      {/* Hidden Central Master Audio Node */}
      {projectDetail?.audio_track && (
        <audio
          ref={audioRef}
          src={`http://localhost:8000/api/projects/${projectDetail?.project?.id}/audio/master`}
          onEnded={() => setIsPlaying(false)}
        />
      )}

      <Header
        projects={projects}
        currentProject={projectDetail?.project}
        onSelectProject={setCurrentProjectId}
        onOpenNewProject={() => setIsNewProjectModalOpen(true)}
        onOpenDiary={() => setIsDiaryModalOpen(true)}
        onOpenProjectManager={() => setIsProjectManagerOpen(true)}
        onOpenRenameProject={() => setIsRenameModalOpen(true)}
        onOpenDeleteProject={() => setIsDeleteModalOpen(true)}
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
        <div className="bg-slate-900 border-b border-teal-500/30 px-6 py-2 flex items-center justify-between text-xs font-mono shrink-0">
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

      {/* Main Premiere Pro-Style Multi-Pane Viewport */}
      <main className="flex-1 w-full p-3 overflow-hidden">
        {!projectDetail ? (
          <div className="h-full flex flex-col items-center justify-center text-center space-y-4">
            <div className="w-16 h-16 rounded-2xl bg-teal-500/20 text-teal-400 flex items-center justify-center mx-auto shadow-xl shadow-teal-500/20">
              <Sparkles className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-bold text-white">Welcome to Balladeer</h2>
            <p className="text-sm text-slate-400 max-w-md mx-auto">
              Create your first project to turn your travel diary, photos, and video clips into a beat-synced AI musical montage.
            </p>
            <div className="flex items-center gap-3 justify-center">
              <button
                onClick={() => setIsNewProjectModalOpen(true)}
                className="px-5 py-2.5 rounded-xl bg-teal-500 hover:bg-teal-400 text-slate-950 font-bold text-sm shadow-lg shadow-teal-500/20 transition"
              >
                Create New Project
              </button>
              {projects.length > 0 && (
                <button
                  onClick={() => setIsProjectManagerOpen(true)}
                  className="px-5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-sm border border-slate-700 transition"
                >
                  Manage Projects ({projects.length})
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-12 grid-rows-2 gap-3 h-full overflow-hidden">
            {/* Top Row: 3 Windows (1/3 each) */}
            {/* Top Left (Col 1/3): Source Media */}
            <div className="col-span-12 lg:col-span-4 min-h-0 h-full overflow-hidden">
              <AssetGallery
                project={projectDetail.project}
                assets={projectDetail.assets || []}
                selectedAsset={selectedAsset}
                onSelectAsset={setSelectedAsset}
                onUploadFiles={handleUploadFiles}
                onIndexDirectory={handleIndexDirectory}
                onIndexPending={handleIndexPending}
                onAssetUpdated={() => loadProjectDetail(currentProjectId)}
                isLoading={isLoading}
              />
            </div>

            {/* Top Middle (Col 2/3): Review Selected Media */}
            <div className="col-span-12 lg:col-span-4 min-h-0 h-full overflow-hidden">
              <AssetDetailPane
                project={projectDetail.project}
                asset={selectedAsset}
                onAssetUpdated={() => loadProjectDetail(currentProjectId)}
              />
            </div>

            {/* Top Right (Col 3/3): Real-Time Program Monitor & Final Movie */}
            <div className="col-span-12 lg:col-span-4 min-h-0 h-full overflow-hidden">
              <VideoPlayerPane
                project={projectDetail.project}
                audioTrack={projectDetail.audio_track}
                slices={projectDetail.timeline_slices || []}
                currentTime={currentTime}
                isPlaying={isPlaying}
                onTogglePlay={handleTogglePlay}
                onSeek={handleSeek}
                videoUrl={renderedVideoUrl}
              />
            </div>

            {/* Bottom Row: 2 Windows (1/3 Music Studio, 2/3 Big Timeline) */}
            {/* Bottom Left (Col 1/3): Music Module */}
            <div className="col-span-12 lg:col-span-4 min-h-0 h-full overflow-hidden">
              <MusicStudio
                project={projectDetail.project}
                audioTrack={projectDetail.audio_track}
                onGenerateMusic={handleGenerateMusic}
                onUploadAudio={handleUploadCustomAudio}
                onOpenDiary={() => setIsDiaryModalOpen(true)}
                isGenerating={isGeneratingMusic}
                health={health}
              />
            </div>

            {/* Bottom Right (Col 2/3): Big Timeline */}
            <div className="col-span-12 lg:col-span-8 min-h-0 h-full overflow-hidden">
              <TimelineEditor
                project={projectDetail.project}
                audioTrack={projectDetail.audio_track}
                slices={projectDetail.timeline_slices || []}
                currentTime={currentTime}
                isPlaying={isPlaying}
                onTogglePlay={handleTogglePlay}
                onSeek={handleSeek}
                onOpenSwapModal={(slice) => setActiveSwapSlice(slice)}
                onUpdateSliceBeatCount={handleUpdateSliceBeatCount}
                onSplitSlice={handleSplitSlice}
                onReorderSlices={handleReorderSlices}
                onSolveTimeline={handleSolveTimeline}
                onRenderVideo={handleRenderVideo}
                isSolving={isSolvingTimeline}
                isRendering={isRendering}
              />
            </div>
          </div>
        )}
      </main>

      <NewProjectModal
        isOpen={isNewProjectModalOpen}
        onClose={() => setIsNewProjectModalOpen(false)}
        onCreate={handleCreateProject}
      />

      <ProjectManagerModal
        isOpen={isProjectManagerOpen}
        onClose={() => setIsProjectManagerOpen(false)}
        projects={projects}
        currentProjectId={currentProjectId}
        onSelectProject={setCurrentProjectId}
        onOpenNewProject={() => setIsNewProjectModalOpen(true)}
        onRenameProject={handleRenameProject}
        onDeleteProject={handleDeleteProject}
        onBatchDeleteProjects={handleBatchDeleteProjects}
      />

      <RenameProjectModal
        isOpen={isRenameModalOpen}
        onClose={() => setIsRenameModalOpen(false)}
        project={projectDetail?.project}
        onRename={handleRenameProject}
      />

      <DeleteConfirmModal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        project={projectDetail?.project}
        onConfirm={() => handleDeleteProject(currentProjectId)}
        isDeleting={isDeleting}
      />

      <DiaryEditorModal
        isOpen={isDiaryModalOpen}
        onClose={() => setIsDiaryModalOpen(false)}
        project={projectDetail?.project}
        onSave={handleSaveDiary}
      />

      <AssetSwapModal
        isOpen={!!activeSwapSlice}
        onClose={() => setActiveSwapSlice(null)}
        project={projectDetail?.project}
        slice={activeSwapSlice}
        onAssetSwapped={() => loadProjectDetail(currentProjectId)}
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
