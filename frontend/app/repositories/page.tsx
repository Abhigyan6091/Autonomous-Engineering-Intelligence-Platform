"use client";

import { apiUrl } from "@/lib/api";

import React, { useEffect, useState } from "react";
import { Navbar } from "@/components/Navbar";
import {
  GitBranch,
  FolderGit2,
  Plus,
  AlertCircle,
  HardDrive,
  Check,
} from "lucide-react";

interface Repository {
  id: string;
  project_id: string;
  name: string;
  url: string | null;
  local_path: string | null;
  branch: string;
  language: string | null;
  framework: string | null;
  created_at: string;
}

const DEFAULT_PROJECT_ID = "demo-project-001";

/** Derive a repo name from a GitHub URL or a filesystem path. */
export function deriveRepoName(source: string): string {
  const trimmed = source.trim().replace(/\.git$/, "").replace(/\/+$/, "");
  const last = trimmed.split("/").pop() ?? "";
  return last || "repository";
}

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState<boolean>(false);

  const [sourceKind, setSourceKind] = useState<"github" | "local">("github");
  const [url, setUrl] = useState<string>("");
  const [localPath, setLocalPath] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [branch, setBranch] = useState<string>("main");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    fetchRepos();
  }, []);

  async function fetchRepos() {
    try {
      const res = await fetch(apiUrl("/api/v1/repositories"));
      if (res.ok) {
        setRepos(await res.json());
        setError(null);
      } else {
        setError(`Could not load repositories (HTTP ${res.status}).`);
      }
    } catch (err) {
      setError(
        `Cannot reach the backend. ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleAddRepo(e: React.FormEvent) {
    e.preventDefault();
    const source = sourceKind === "github" ? url : localPath;
    if (!source.trim()) {
      setFormError(
        sourceKind === "github"
          ? "Paste a GitHub URL."
          : "Enter the folder path on this machine."
      );
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const res = await fetch(apiUrl("/api/v1/repositories"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: DEFAULT_PROJECT_ID,
          name: name.trim() || deriveRepoName(source),
          url: sourceKind === "github" ? url.trim() : null,
          local_path: sourceKind === "local" ? localPath.trim() : null,
          branch: branch.trim() || "main",
        }),
      });

      if (!res.ok) {
        const detail = await res.text();
        setFormError(`Backend rejected it (HTTP ${res.status}): ${detail.slice(0, 200)}`);
        return;
      }

      setModalOpen(false);
      setUrl("");
      setLocalPath("");
      setName("");
      setBranch("main");
      fetchRepos();
    } catch (err) {
      setFormError(
        `Could not add repository. ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-2xl font-bold text-white flex items-center space-x-3">
              <FolderGit2 className="w-6 h-6 text-sky-400" />
              <span>Repositories</span>
            </h1>
            <p className="text-sm text-slate-400">
              Targets available to investigations. Add a GitHub URL or point at a
              local folder.
            </p>
          </div>

          <button
            onClick={() => setModalOpen(true)}
            className="inline-flex items-center px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-medium text-sm shadow-lg shadow-sky-900/40"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Repository
          </button>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 p-4 flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-rose-300">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="glass-panel p-12 rounded-xl text-center text-slate-400">
            Loading repositories...
          </div>
        ) : repos.length === 0 ? (
          <div className="glass-panel p-12 rounded-xl text-center space-y-4">
            <FolderGit2 className="w-12 h-12 text-slate-600 mx-auto" />
            <p className="text-slate-300">No repositories registered yet.</p>
            <button
              onClick={() => setModalOpen(true)}
              className="px-4 py-2 rounded-lg bg-sky-600 text-white text-sm hover:bg-sky-500"
            >
              Add your first repository
            </button>
          </div>
        ) : (
          <div className="grid gap-3">
            {repos.map((repo) => (
              <div
                key={repo.id}
                className="glass-panel p-5 rounded-xl border border-slate-800 flex items-start justify-between gap-4"
              >
                <div className="space-y-2 min-w-0">
                  <div className="flex items-center space-x-3">
                    {repo.url ? (
                      <GitBranch className="w-4 h-4 text-slate-300 flex-shrink-0" />
                    ) : (
                      <HardDrive className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                    )}
                    <span className="font-semibold text-white truncate">
                      {repo.name}
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs font-mono bg-slate-800 text-slate-300 border border-slate-700">
                      {repo.branch}
                    </span>
                  </div>

                  <p className="text-xs font-mono text-slate-400 break-all">
                    {repo.url || repo.local_path}
                  </p>

                  <div className="flex flex-wrap gap-3 text-xs font-mono text-slate-500">
                    {repo.language && <span>{repo.language}</span>}
                    {repo.framework && <span>{repo.framework}</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="glass-panel-glow bg-slate-900 border border-slate-700 w-full max-w-xl rounded-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h3 className="text-lg font-bold text-white flex items-center space-x-2">
                <FolderGit2 className="w-5 h-5 text-sky-400" />
                <span>Add Repository</span>
              </h3>
              <button
                onClick={() => setModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleAddRepo} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setSourceKind("github")}
                  className={`py-2.5 px-3 rounded-lg text-xs font-mono font-semibold border transition-all flex items-center justify-center space-x-2 ${
                    sourceKind === "github"
                      ? "bg-sky-600 text-white border-sky-400"
                      : "bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-800"
                  }`}
                >
                  <GitBranch className="w-4 h-4" />
                  <span>GITHUB URL</span>
                </button>
                <button
                  type="button"
                  onClick={() => setSourceKind("local")}
                  className={`py-2.5 px-3 rounded-lg text-xs font-mono font-semibold border transition-all flex items-center justify-center space-x-2 ${
                    sourceKind === "local"
                      ? "bg-sky-600 text-white border-sky-400"
                      : "bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-800"
                  }`}
                >
                  <HardDrive className="w-4 h-4" />
                  <span>LOCAL FOLDER</span>
                </button>
              </div>

              {sourceKind === "github" ? (
                <div>
                  <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                    GitHub Repository URL
                  </label>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://github.com/owner/repo"
                    className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                    Local Folder Path
                  </label>
                  <input
                    value={localPath}
                    onChange={(e) => setLocalPath(e.target.value)}
                    placeholder="./demo_repo/checkout-api"
                    className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Path as seen by the backend process. Browsers cannot read a
                    folder picker&apos;s absolute path, so type or paste it.
                  </p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                    Display Name
                  </label>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder={
                      deriveRepoName(sourceKind === "github" ? url : localPath) ||
                      "auto"
                    }
                    className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100 focus:outline-none focus:border-sky-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                    Branch
                  </label>
                  <input
                    value={branch}
                    onChange={(e) => setBranch(e.target.value)}
                    placeholder="main"
                    className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                  />
                </div>
              </div>

              {formError && (
                <div className="rounded-lg border border-rose-500/40 bg-rose-950/40 p-3 text-xs font-mono text-rose-300">
                  {formError}
                </div>
              )}

              <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-medium text-sm disabled:opacity-50 inline-flex items-center"
                >
                  {submitting ? (
                    "Registering..."
                  ) : (
                    <>
                      <Check className="w-4 h-4 mr-2" />
                      Add Repository
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
