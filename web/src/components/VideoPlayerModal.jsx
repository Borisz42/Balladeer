import React from 'react';
import { X, Download, Film, Sparkles } from 'lucide-react';

export default function VideoPlayerModal({ isOpen, onClose, project, videoUrl }) {
  if (!isOpen || !videoUrl) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
      <div className="glass-panel w-full max-w-4xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-teal-500/20 text-teal-400 flex items-center justify-center">
              <Film className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">Rendered Video Montage</h2>
              <p className="text-xs text-slate-400 font-mono">
                {project?.title} • Hardware-accelerated NVENC MP4
              </p>
            </div>
          </div>

          <a
            href={videoUrl}
            download={`${project?.title || 'montage'}.mp4`}
            className="flex items-center gap-1.5 bg-teal-500 hover:bg-teal-400 text-slate-950 px-4 py-1.5 rounded-lg text-xs font-bold transition shadow-md shadow-teal-500/20"
          >
            <Download className="w-3.5 h-3.5" />
            Download MP4
          </a>
        </div>

        {/* Video Player */}
        <div className="rounded-xl overflow-hidden bg-black border border-slate-800 aspect-video shadow-2xl flex items-center justify-center">
          <video
            controls
            autoPlay
            className="w-full h-full object-contain"
            src={videoUrl}
          />
        </div>
      </div>
    </div>
  );
}
