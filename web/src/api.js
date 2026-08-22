const API_BASE = 'http://localhost:8000/api';

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  return res.json();
}

export async function fetchSystemSettings() {
  const res = await fetch(`${API_BASE}/system/settings`);
  if (!res.ok) throw new Error('Failed to fetch system settings');
  return res.json();
}

export async function updateSystemSettings({ gemini_api_key, only_local_ai, local_model } = {}) {
  const res = await fetch(`${API_BASE}/system/settings`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      gemini_api_key: gemini_api_key !== undefined ? gemini_api_key : null,
      only_local_ai: only_local_ai !== undefined ? only_local_ai : null,
      local_model: local_model !== undefined ? local_model : null
    })
  });
  if (!res.ok) throw new Error('Failed to update system settings');
  return res.json();
}


export async function listProjects() {
  const res = await fetch(`${API_BASE}/projects`);
  return res.json();
}

export async function getProject(id) {
  const res = await fetch(`${API_BASE}/projects/${id}`);
  if (!res.ok) throw new Error('Failed to fetch project');
  return res.json();
}

export async function createProject(title, narrativeText, configOverride = null) {
  const res = await fetch(`${API_BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      narrative_text: narrativeText,
      config_override: configOverride
    })
  });
  if (!res.ok) throw new Error('Failed to create project');
  return res.json();
}

export async function updateProjectDiary(id, { title, narrativeText, configOverride }) {
  const res = await fetch(`${API_BASE}/projects/${id}/diary`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      narrative_text: narrativeText,
      config_override: configOverride
    })
  });
  if (!res.ok) throw new Error('Failed to update project diary');
  return res.json();
}

export async function renameProject(id, title) {
  const res = await fetch(`${API_BASE}/projects/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title })
  });
  if (!res.ok) throw new Error('Failed to rename project');
  return res.json();
}

export async function rephraseDiary(params) {
  const res = await fetch(`${API_BASE}/projects/rephrase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  if (!res.ok) throw new Error('Failed to rephrase diary');
  return res.json();
}

export async function draftTravelLog(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/draft-travel-log`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to draft travel log' }));
    throw new Error(err.detail || 'Failed to draft travel log');
  }
  return res.json();
}

export async function approveTravelLog(projectId, { title, narrativeText, configOverride } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/approve-travel-log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      narrative_text: narrativeText,
      config_override: configOverride
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to approve travel log' }));
    throw new Error(err.detail || 'Failed to approve travel log');
  }
  return res.json();
}

export async function syncProjectDiaryDates(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/sync-diary-dates`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to sync diary dates');
  return res.json();
}

export async function deleteProject(id) {
  const res = await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete project');
  return res.json();
}

export async function batchDeleteProjects(projectIds) {
  const res = await fetch(`${API_BASE}/projects/batch-delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_ids: projectIds })
  });
  if (!res.ok) throw new Error('Failed to batch delete projects');
  return res.json();
}

export async function uploadMediaFiles(projectId, files) {
  const formData = new FormData();
  for (const file of files) {
    formData.append('files', file);
  }
  const res = await fetch(`${API_BASE}/projects/${projectId}/upload`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) throw new Error('Failed to upload media');
  return res.json();
}

export async function indexDirectory(projectId, directoryPath) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/index-directory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ directory_path: directoryPath })
  });
  if (!res.ok) throw new Error('Failed to index directory');
  return res.json();
}

export async function indexPendingMedia(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/index-pending`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to index pending media');
  return res.json();
}

export async function updateAsset(projectId, assetId, updates) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/assets/${assetId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  });
  if (!res.ok) throw new Error('Failed to update asset');
  return res.json();
}

export async function reindexAsset(projectId, assetId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/assets/${assetId}/reindex`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to reindex asset');
  return res.json();
}

export async function fetchAssetSegments(projectId, assetId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/assets/${assetId}/segments`);
  if (!res.ok) throw new Error('Failed to fetch video segments');
  return res.json();
}

export async function fetchAssetFrameScores(projectId, assetId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/assets/${assetId}/frame-scores`);
  if (!res.ok) throw new Error('Failed to fetch frame scores');
  return res.json();
}

export async function toggleAssetInclusion(projectId, assetId, { include, thresholdScore, delta } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/assets/${assetId}/toggle-inclusion`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      include: !!include,
      threshold_score: thresholdScore !== undefined ? thresholdScore : null,
      delta: delta !== undefined ? delta : 0.15
    })
  });
  if (!res.ok) throw new Error('Failed to toggle asset inclusion');
  return res.json();
}

export async function analyzeMusicTimeline(projectId, { pacingPreset, photoSec, videoSecMax, defaultThreshold, dailyThresholds } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/music/analyze-timeline`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pacing_preset: pacingPreset || 'balanced',
      photo_sec: photoSec !== undefined ? photoSec : null,
      video_sec_max: videoSecMax !== undefined ? videoSecMax : null,
      default_inclusion_threshold: defaultThreshold !== undefined ? defaultThreshold : 70.0,
      daily_inclusion_thresholds: dailyThresholds || null
    })
  });
  if (!res.ok) throw new Error('Failed to analyze music timeline');
  return res.json();
}

export async function generateMusicPrompt(projectId, { styleVibe, suggestedBpm, totalDurationSec, acts } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/music/generate-prompt`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      style_vibe: styleVibe || null,
      suggested_bpm: suggestedBpm || null,
      total_duration_sec: totalDurationSec || null,
      acts: acts || null
    })
  });
  if (!res.ok) throw new Error('Failed to generate music prompt');
  return res.json();
}

export async function generateMusicLyrics(projectId, { flowPrompt, isInstrumental, acts } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/music/generate-lyrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      flow_prompt: flowPrompt || null,
      is_instrumental: !!isInstrumental,
      acts: acts || null
    })
  });
  if (!res.ok) throw new Error('Failed to generate music lyrics');
  return res.json();
}

export async function synthesizeMusicAudio(projectId, { prompt, lyrics, bpm, duration_sec, durationSec, is_instrumental } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/music/analyze-and-align`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: prompt || null,
      lyrics: lyrics || null,
      bpm: bpm || 118.0,
      duration_sec: durationSec || duration_sec || 30.0,
      is_instrumental: is_instrumental || false
    })
  });
  if (!res.ok) throw new Error('Failed to analyze and align music audio');
  return res.json();
}

export async function generateMusic(projectId, { prompt, lyrics, bpm, duration_sec, durationSec, is_instrumental } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/generate-music`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: prompt || null,
      lyrics: lyrics || null,
      bpm: bpm || 120.0,
      duration_sec: durationSec || duration_sec || 30.0,
      is_instrumental: is_instrumental || false
    })
  });
  if (!res.ok) throw new Error('Failed to generate music');
  return res.json();
}

export async function uploadCustomAudio(projectId, audioFile, { bpm, is_instrumental } = {}) {
  const formData = new FormData();
  formData.append('file', audioFile);
  if (bpm) formData.append('bpm', bpm.toString());
  if (is_instrumental !== undefined) formData.append('is_instrumental', is_instrumental.toString());

  const res = await fetch(`${API_BASE}/projects/${projectId}/upload-audio`, {
    method: 'POST',
    body: formData
  });
  if (!res.ok) throw new Error('Failed to upload custom audio');
  return res.json();
}

export async function updateLyrics(projectId, { lyrics, aligned_lyrics, auto_snap, enable_word_highlight } = {}) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/lyrics`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lyrics: lyrics !== undefined ? lyrics : null,
      aligned_lyrics: aligned_lyrics !== undefined ? aligned_lyrics : null,
      auto_snap: auto_snap !== undefined ? auto_snap : true,
      enable_word_highlight: enable_word_highlight !== undefined ? enable_word_highlight : null
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update lyrics' }));
    throw new Error(err.detail || 'Failed to update lyrics');
  }
  return res.json();
}

export async function realignLyrics(projectId, lyrics = null) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/realign-lyrics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lyrics: lyrics || null })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to realign lyrics' }));
    throw new Error(err.detail || 'Failed to realign lyrics');
  }
  return res.json();
}

export async function solveTimeline(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/solve-timeline`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to solve timeline');
  return res.json();
}

export async function updateSlice(sliceId, updates) {
  const res = await fetch(`${API_BASE}/timeline/slices/${sliceId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  });
  if (!res.ok) throw new Error('Failed to update slice');
  return res.json();
}

export async function updateTimelineControls(projectId, controlsConfig) {
  const res = await fetch(`${API_BASE}/timeline/${projectId}/controls`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(controlsConfig)
  });
  if (!res.ok) throw new Error('Failed to update timeline controls');
  return res.json();
}

export async function bulkApplyTimelineEffects(projectId, payload) {
  const res = await fetch(`${API_BASE}/timeline/${projectId}/bulk-apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error('Failed to bulk apply timeline effects');
  return res.json();
}

export async function splitSlice(projectId, sliceId, splitAtBeat) {
  const res = await fetch(`${API_BASE}/timeline/${projectId}/slices/${sliceId}/split`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ split_at_beat: splitAtBeat })
  });
  if (!res.ok) throw new Error('Failed to split slice');
  return res.json();
}

export async function reorderSlices(projectId, orderedSliceIds) {
  const res = await fetch(`${API_BASE}/timeline/${projectId}/reorder`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ordered_slice_ids: orderedSliceIds })
  });
  if (!res.ok) throw new Error('Failed to reorder slices');
  return res.json();
}

export async function getSliceRecommendations(projectId, sliceId) {
  const res = await fetch(`${API_BASE}/timeline/${projectId}/slices/${sliceId}/recommendations`);
  if (!res.ok) throw new Error('Failed to fetch recommendations');
  return res.json();
}

export async function swapSliceAsset(projectId, sliceId, newAssetId) {
  const res = await fetch(`${API_BASE}/timeline/${projectId}/slices/${sliceId}/swap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ new_asset_id: newAssetId })
  });
  if (!res.ok) throw new Error('Failed to swap asset');
  return res.json();
}

export async function renderVideo(projectId) {
  const res = await fetch(`${API_BASE}/projects/${projectId}/render-video`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to trigger render');
  return res.json();
}

export async function fetchModelsStatus() {
  const res = await fetch(`${API_BASE}/models/status`);
  if (!res.ok) throw new Error('Failed to fetch model status');
  return res.json();
}

export async function triggerModelDownload(modelName, token = null) {
  const res = await fetch(`${API_BASE}/models/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_name: modelName, token: token && token.trim() ? token.trim() : null })
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    const msg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
    throw new Error(msg || 'Failed to trigger model download');
  }
  return res.json();
}

export async function shutdownServer() {
  const res = await fetch(`${API_BASE}/system/shutdown`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to shutdown server');
  return res.json();
}

export function subscribeProjectProgress(projectId, onProgress) {
  const source = new EventSource(`${API_BASE}/progress/${projectId}`);
  source.addEventListener('progress', (e) => {
    try {
      const data = JSON.parse(e.data);
      onProgress(data);
    } catch (err) {
      console.error(err);
    }
  });
  return source;
}
