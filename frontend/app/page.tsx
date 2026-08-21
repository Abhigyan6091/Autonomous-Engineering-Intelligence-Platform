"use client";

import { API_BASE_URL, apiUrl } from "@/lib/api";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  ArrowRight, 
  Plus, 
  Terminal, 
  Layers, 
  Cpu, 
  Database, 
  Activity, 
  ShieldCheck, 
  Flame, 
  ExternalLink,
  Sparkles,
  Zap
} from "lucide-react";

interface Investigation {
  id: string;
  project_id: string;
  objective: string;
  mode: "incident" | "audit" | "remediation";
  status: string;
  priority: string;
  confidence: number | null;
  budget_tokens_used: number;
  budget_tool_calls_used: number;
  created_at: string;
}

interface Finding {
  id: string;
  investigation_id: string;
  claim: string;
  confidence: number;
  confidence_tier: string;
  severity: string;
  category: string;
  is_root_cause: boolean;
  evidence_count: number;
}

export default function DashboardPage() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  // New investigation form state
  const [objective, setObjective] = useState<string>("");
  const [mode, setMode] = useState<"incident" | "audit" | "remediation">("incident");
  const [priority, setPriority] = useState<string>("critical");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    const timer = setInterval(fetchData, 8000);
    return () => clearInterval(timer);
  }, []);

  async function fetchData() {
    try {
      const [invRes, findRes] = await Promise.all([
        fetch(apiUrl("/api/v1/investigations")),
        fetch(apiUrl("/api/v1/findings"))
      ]);

      if (invRes.ok) {
        const invData = await invRes.json();
        setInvestigations(invData.items || []);
      }
      if (findRes.ok) {
        const findData = await findRes.json();
        setFindings(findData || []);
      }

      if (!invRes.ok) {
        setError(`Backend returned ${invRes.status} for /api/v1/investigations.`);
      } else {
        setError(null);
      }
    } catch (err) {
      setError(
        `Cannot reach the backend at ${API_BASE_URL}. Is it running? (${err instanceof Error ? err.message : String(err)})`
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateInvestigation(e: React.FormEvent) {
    e.preventDefault();
    if (!objective.trim()) return;

    setSubmitting(true);
    try {
      const res = await fetch(apiUrl("/api/v1/investigations"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "demo-project-001",
          objective: objective.trim(),
          mode: mode,
          priority: priority,
          metadata: {
            workspace_path: "./demo_repo/checkout-api",
            service_name: "checkout-api",
          }
        })
      });

      if (res.ok) {
        const data = await res.json();
        setIsModalOpen(false);
        setObjective("");
        setFormError(null);
        fetchData();
        // Redirect to detail page
        window.location.href = `/investigations/${data.id}`;
      } else {
        // Surface the backend's reason rather than failing silently.
        const detail = await res.text();
        setFormError(`Backend rejected the request (${res.status}): ${detail.slice(0, 300)}`);
      }
    } catch (err) {
      setFormError(
        `Could not reach the backend at ${API_BASE_URL}. ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Top Hero Banner */}
        <div className="relative rounded-2xl p-8 overflow-hidden glass-panel-glow border border-sky-500/20 bg-gradient-to-r from-slate-900/90 via-slate-900/60 to-indigo-950/40">
          <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div className="space-y-2 max-w-2xl">
              <div className="flex items-center space-x-2">
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-sky-500/10 text-sky-400 border border-sky-500/30">
                  <Zap className="w-3.5 h-3.5 mr-1" />
                  LangGraph Autonomous Core v0.1
                </span>
                <span className="text-xs text-slate-400 font-mono">Parallel Specialist Agents Active</span>
              </div>
              <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
                Engineering Intelligence Platform
              </h1>
              <p className="text-slate-300 text-sm leading-relaxed">
                Autonomous root cause investigation, evidence correlation, hypothesis validation, and verified remediation for mission-critical software systems.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => {
                  setMode("incident");
                  setIsModalOpen(true);
                }}
                className="inline-flex items-center px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-amber-600 hover:from-rose-500 hover:to-amber-500 text-white font-medium text-sm shadow-lg shadow-rose-900/30 transition-all hover:scale-[1.02]"
              >
                <Flame className="w-4 h-4 mr-2" />
                Investigate Incident
              </button>

              <button
                onClick={() => {
                  setMode("audit");
                  setIsModalOpen(true);
                }}
                className="inline-flex items-center px-5 py-2.5 rounded-xl glass-panel hover:bg-slate-800 text-slate-200 font-medium text-sm border border-slate-700 transition-all hover:scale-[1.02]"
              >
                <ShieldCheck className="w-4 h-4 mr-2 text-sky-400" />
                Run System Audit
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 p-4 flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-semibold text-rose-200">Backend unreachable</p>
              <p className="text-rose-300/90 font-mono text-xs mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Live Metrics Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <div className="glass-panel p-5 rounded-xl border border-slate-800 flex items-center space-x-4">
            <div className="p-3 rounded-lg bg-sky-950/80 text-sky-400 border border-sky-800/40">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-mono text-slate-400 uppercase tracking-wider">Total Investigations</p>
              <p className="text-2xl font-bold text-white mt-1">{investigations.length}</p>
            </div>
          </div>

          <div className="glass-panel p-5 rounded-xl border border-slate-800 flex items-center space-x-4">
            <div className="p-3 rounded-lg bg-rose-950/80 text-rose-400 border border-rose-800/40">
              <Flame className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-mono text-slate-400 uppercase tracking-wider">Active Incidents</p>
              <p className="text-2xl font-bold text-white mt-1">
                {investigations.filter(i => i.mode === "incident" && i.status !== "completed").length}
              </p>
            </div>
          </div>

          <div className="glass-panel p-5 rounded-xl border border-slate-800 flex items-center space-x-4">
            <div className="p-3 rounded-lg bg-emerald-950/80 text-emerald-400 border border-emerald-800/40">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-mono text-slate-400 uppercase tracking-wider">Confirmed Findings</p>
              <p className="text-2xl font-bold text-white mt-1">{findings.length}</p>
            </div>
          </div>

          <div className="glass-panel p-5 rounded-xl border border-slate-800 flex items-center space-x-4">
            <div className="p-3 rounded-lg bg-indigo-950/80 text-indigo-400 border border-indigo-800/40">
              <Cpu className="w-6 h-6" />
            </div>
            <div>
              <p className="text-xs font-mono text-slate-400 uppercase tracking-wider">Autonomous Agents</p>
              <p className="text-2xl font-bold text-white mt-1">5 Specialists</p>
            </div>
          </div>
        </div>

        {/* Investigations List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <h2 className="text-xl font-bold text-white tracking-tight">Active & Recent Investigations</h2>
              <span className="text-xs font-mono text-slate-400">({investigations.length} registered)</span>
            </div>
            <button
              onClick={fetchData}
              className="text-xs text-sky-400 hover:text-sky-300 transition-colors font-mono"
            >
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="glass-panel p-12 rounded-xl text-center text-slate-400">
              Loading investigations telemetry...
            </div>
          ) : investigations.length === 0 ? (
            <div className="glass-panel p-12 rounded-xl text-center space-y-4">
              <AlertCircle className="w-12 h-12 text-slate-500 mx-auto" />
              <p className="text-slate-300">No investigations recorded yet.</p>
              <button
                onClick={() => setIsModalOpen(true)}
                className="px-4 py-2 rounded-lg bg-sky-600 text-white text-sm hover:bg-sky-500"
              >
                Launch First Investigation
              </button>
            </div>
          ) : (
            <div className="grid gap-4">
              {investigations.map((inv) => (
                <Link
                  key={inv.id}
                  href={`/investigations/${inv.id}`}
                  className="glass-panel p-5 rounded-xl border border-slate-800 hover:border-sky-500/40 transition-all hover:bg-slate-900/60 group block"
                >
                  <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center space-x-3">
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-medium ${
                            inv.mode === "incident"
                              ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                              : inv.mode === "audit"
                              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
                              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                          }`}
                        >
                          {inv.mode.toUpperCase()}
                        </span>

                        <span
                          className={`px-2 py-0.5 rounded text-xs font-mono ${
                            inv.status === "completed"
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                              : inv.status === "running" || inv.status === "planning"
                              ? "bg-sky-950 text-sky-300 border border-sky-800 animate-pulse"
                              : inv.status === "awaiting_approval"
                              ? "bg-amber-950 text-amber-300 border border-amber-800"
                              : "bg-slate-800 text-slate-400"
                          }`}
                        >
                          STATUS: {inv.status.toUpperCase()}
                        </span>

                        <span className="text-xs font-mono text-slate-500">ID: {inv.id}</span>
                      </div>

                      <p className="text-base font-semibold text-white group-hover:text-sky-300 transition-colors line-clamp-2">
                        {inv.objective}
                      </p>

                      <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-400 pt-1">
                        <span>Tokens: {inv.budget_tokens_used.toLocaleString()}</span>
                        <span>Tool Calls: {inv.budget_tool_calls_used}</span>
                        {inv.confidence !== null && (
                          <span className="text-emerald-400 font-semibold">
                            Confidence: {(inv.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                        <span className="text-slate-500">{new Date(inv.created_at).toLocaleString()}</span>
                      </div>
                    </div>

                    <div className="flex items-center text-sky-400 font-medium text-sm group-hover:translate-x-1 transition-transform">
                      <span>Inspect</span>
                      <ArrowRight className="w-4 h-4 ml-1" />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* New Investigation Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="glass-panel-glow bg-slate-900 border border-slate-700 w-full max-w-2xl rounded-2xl p-6 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-sky-400" />
                <h3 className="text-lg font-bold text-white">Launch Autonomous Investigation</h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateInvestigation} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                  Investigation Mode
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {(["incident", "audit", "remediation"] as const).map((m) => (
                    <button
                      type="button"
                      key={m}
                      onClick={() => setMode(m)}
                      className={`py-2 px-3 rounded-lg text-xs font-mono font-semibold border transition-all ${
                        mode === m
                          ? "bg-sky-600 text-white border-sky-400 shadow-md shadow-sky-900/50"
                          : "bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-800"
                      }`}
                    >
                      {m.toUpperCase()}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-mono text-slate-300 uppercase mb-1">
                  Investigation Objective / Incident Report
                </label>
                <textarea
                  rows={4}
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  placeholder="Describe the incident symptoms, latency regressions, error traces, or audit goals..."
                  className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100 focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 font-sans"
                  required
                />
              </div>

              {formError && (
                <div className="rounded-lg border border-rose-500/40 bg-rose-950/40 p-3 text-xs font-mono text-rose-300">
                  {formError}
                </div>
              )}

              <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-medium text-sm shadow-lg shadow-sky-900/50 transition-all disabled:opacity-50"
                >
                  {submitting ? "Spawning LangGraph Agents..." : "Start Investigation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
