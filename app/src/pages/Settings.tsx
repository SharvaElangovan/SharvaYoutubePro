import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";

interface YouTubeSettings {
  client_id: string;
  client_secret: string;
  is_authenticated: boolean;
  channel_name: string | null;
}

export default function Settings() {
  const [settings, setSettings] = useState<YouTubeSettings>({
    client_id: "",
    client_secret: "",
    is_authenticated: false,
    channel_name: null,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const result = await invoke<YouTubeSettings>("get_youtube_settings");
      setSettings(result);
    } catch (error) {
      console.error("Failed to load settings:", error);
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await invoke("save_youtube_settings", {
        clientId: settings.client_id,
        clientSecret: settings.client_secret,
      });
      setMessage({ type: "success", text: "Settings saved successfully!" });
    } catch (error) {
      setMessage({ type: "error", text: `Failed to save: ${error}` });
    } finally {
      setSaving(false);
    }
  };

  const authenticateYouTube = async () => {
    setMessage(null);
    try {
      await invoke("authenticate_youtube");
      setMessage({
        type: "success",
        text: "Authentication started. Complete it in your browser, then click 'Refresh Status'.",
      });
    } catch (error) {
      setMessage({ type: "error", text: `Authentication failed: ${error}` });
    }
  };

  const disconnectYouTube = async () => {
    setMessage(null);
    try {
      await invoke("disconnect_youtube");
      setSettings((prev) => ({
        ...prev,
        is_authenticated: false,
        channel_name: null,
      }));
      setMessage({ type: "success", text: "YouTube account disconnected." });
    } catch (error) {
      setMessage({ type: "error", text: `Failed to disconnect: ${error}` });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white text-xl">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold text-white">Settings</h1>
        <button
          onClick={loadSettings}
          className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-colors flex items-center gap-2"
        >
          <span>🔄</span> Refresh Status
        </button>
      </div>

      {message && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            message.type === "success"
              ? "bg-green-500/20 border border-green-500 text-green-200"
              : "bg-red-500/20 border border-red-500 text-red-200"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20 mb-6">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span>📺</span> YouTube API Configuration
        </h2>
        <p className="text-slate-300 text-sm mb-6">
          To upload videos to YouTube, you need to set up OAuth 2.0 credentials
          in the{" "}
          <a
            href="https://console.cloud.google.com/apis/credentials"
            target="_blank"
            rel="noopener noreferrer"
            className="text-purple-400 hover:text-purple-300 underline"
          >
            Google Cloud Console
          </a>
          . Enable the YouTube Data API v3 and create OAuth 2.0 credentials.
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Client ID
            </label>
            <input
              type="text"
              value={settings.client_id}
              onChange={(e) =>
                setSettings((prev) => ({ ...prev, client_id: e.target.value }))
              }
              placeholder="Enter your OAuth 2.0 Client ID"
              className="w-full px-4 py-3 bg-black/30 border border-white/20 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Client Secret
            </label>
            <input
              type="password"
              value={settings.client_secret}
              onChange={(e) =>
                setSettings((prev) => ({
                  ...prev,
                  client_secret: e.target.value,
                }))
              }
              placeholder="Enter your OAuth 2.0 Client Secret"
              className="w-full px-4 py-3 bg-black/30 border border-white/20 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500"
            />
          </div>

          <button
            onClick={saveSettings}
            disabled={saving}
            className="w-full py-3 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-600/50 text-white font-medium rounded-lg transition-colors"
          >
            {saving ? "Saving..." : "Save Credentials"}
          </button>
        </div>
      </div>

      <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-6 border border-white/20">
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span>🔗</span> YouTube Account
        </h2>

        {settings.is_authenticated ? (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-green-500/20 border border-green-500/50 rounded-lg">
              <span className="text-2xl">✅</span>
              <div>
                <p className="text-green-200 font-medium">Connected</p>
                {settings.channel_name && (
                  <p className="text-green-300 text-sm">
                    Channel: {settings.channel_name}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={disconnectYouTube}
              className="w-full py-3 bg-red-600 hover:bg-red-700 text-white font-medium rounded-lg transition-colors"
            >
              Disconnect YouTube Account
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3 p-4 bg-yellow-500/20 border border-yellow-500/50 rounded-lg">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="text-yellow-200 font-medium">Not Connected</p>
                <p className="text-yellow-300 text-sm">
                  Save your credentials first, then authenticate.
                </p>
              </div>
            </div>
            <button
              onClick={authenticateYouTube}
              disabled={!settings.client_id || !settings.client_secret}
              className="w-full py-3 bg-red-600 hover:bg-red-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              <span>▶️</span> Connect YouTube Account
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
