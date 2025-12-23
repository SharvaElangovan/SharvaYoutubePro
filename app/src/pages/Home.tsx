import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div>
      <header className="text-center mb-12">
        <h1 className="text-5xl font-bold text-white mb-4">
          Welcome to SharvaYoutubePro
        </h1>
        <p className="text-xl text-purple-200">
          Quiz Video Generator & YouTube Uploader
        </p>
      </header>

      <div className="max-w-4xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 hover:border-purple-400 transition-colors">
            <div className="text-4xl mb-4">🎬</div>
            <h2 className="text-xl font-semibold text-white mb-2">
              Create Videos
            </h2>
            <p className="text-slate-300">
              Generate engaging quiz videos for your audience
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 hover:border-purple-400 transition-colors">
            <div className="text-4xl mb-4">📤</div>
            <h2 className="text-xl font-semibold text-white mb-2">
              Upload to YouTube
            </h2>
            <p className="text-slate-300">
              Seamlessly upload your videos to YouTube
            </p>
          </div>

          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 hover:border-purple-400 transition-colors">
            <div className="text-4xl mb-4">📊</div>
            <h2 className="text-xl font-semibold text-white mb-2">
              Manage Content
            </h2>
            <p className="text-slate-300">
              Track and manage all your quiz content
            </p>
          </div>

          <Link
            to="/settings"
            className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 hover:border-purple-400 transition-colors block"
          >
            <div className="text-4xl mb-4">⚙️</div>
            <h2 className="text-xl font-semibold text-white mb-2">Settings</h2>
            <p className="text-slate-300">
              Configure YouTube API and preferences
            </p>
          </Link>
        </div>

        <div className="mt-12 text-center">
          <p className="text-slate-400 text-sm">
            Built with Tauri 2 + React 19 + TypeScript
          </p>
        </div>
      </div>
    </div>
  );
}
