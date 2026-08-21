"use client";

import { apiUrl } from "@/lib/api";

import React, { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { 
  Terminal, 
  GitPullRequest, 
  Search, 
  ShieldAlert, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ArrowLeft, 
  Cpu, 
  Activity, 
  FileText, 
  Code, 
  Database, 
  BarChart3, 
  RotateCw,
  Sparkles,
  Check,
  X
} from "lucide-react";

interface SSEEvent {
  event_type: string;
  payload: any;
  timestamp: string;
}

export default function InvestigationDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [investigation, setInvestigation] = useState<any>(null);
  const [tasks, setTasks] = useState<any[]>([]);
  const [hypotheses, setHypotheses] = useState<any[]>([]);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [report, setReport] = useState<any>(null);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [activeTab, setActiveTab] = useState<"stream" | "hypotheses" | "evidence" | "remediation" | "report">("stream");

  const [approvalModal, setApprovalModal] = useState<boolean>(false);
  const [actionNotes, setActionNotes] = useState<string>("");
  const [submittingAction, setSubmittingAction] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const eventStreamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    loadAllData();

    // Setup Server-Sent Events (SSE) Stream
    const eventSource = new EventSource(apiUrl(`/api/v1/events/${id}/stream`));

    eventSource.onmessage = (e) => {
      try {
        const parsed = JSON.parse(e.data);
        setEvents((prev) => [...prev, parsed]);
        // Auto-refresh investigation state when events arrive
        loadAllData();
      } catch (err) {
        console.error("SSE parse error", err);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [id]);

  useEffect(() => {
    // Auto-scroll event stream
    if (eventStreamRef.current) {
      eventStreamRef.current.scrollTop = eventStreamRef.current.scrollHeight;
    }
  }, [events]);

  async function loadAllData() {
    try {
      const [invRes, taskRes, hypRes, evRes] = await Promise.all([
        fetch(apiUrl(`/api/v1/investigations/${id}`)),
        fetch(apiUrl(`/api/v1/investigations/${id}/tasks`)),
        fetch(apiUrl(`/api/v1/investigations/${id}/hypotheses`)),
        fetch(apiUrl(`/api/v1/investigations/${id}/evidence`)),
      ]);

      if (invRes.ok) setInvestigation(await invRes.json());
      if (taskRes.ok) setTasks(await taskRes.json());
      if (hypRes.ok) setHypotheses(await hypRes.json());
      if (evRes.ok) setEvidence(await evRes.json());

      // Attempt to load report if completed
      try {
        const repRes = await fetch(apiUrl(`/api/v1/investigations/${id}/report`));
        if (repRes.ok) setReport(await repRes.json());
      } catch {
        // report not ready yet
      }
    } catch (err) {
      console.error("Failed to load investigation data", err);
    }
  }

  async function handleApproval(decision: "approve" | "reject") {
    setSubmittingAction(true);
    setActionError(null);
    try {
      // Find pending approval for this investigation
      const appListRes = await fetch(apiUrl("/api/v1/approvals"));
      if (!appListRes.ok) {
        setActionError(`Could not load pending approvals (HTTP ${appListRes.status}).`);
        return;
      }

      const apps = await appListRes.json();
      const targetApp = apps.find(
        (a: { investigation_id: string }) => a.investigation_id === id
      );

      if (!targetApp) {
        // Silently doing nothing here is what made the buttons look dead.
        setActionError(
          "No pending approval exists for this investigation. An approval is only created once a remediation patch is proposed."
        );
        return;
      }

      const res = await fetch(
        apiUrl(`/api/v1/approvals/${targetApp.id}/${decision}`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notes: actionNotes }),
        }
      );

      if (!res.ok) {
        const detail = await res.text();
        setActionError(
          `Backend rejected the ${decision} (HTTP ${res.status}): ${detail.slice(0, 200)}`
        );
        return;
      }

      setActionError(null);
      setApprovalModal(false);
      loadAllData();
    } catch (err) {
      setActionError(
        `Action failed: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setSubmittingAction(false);
    }
  }

  if (!investigation) {
    return (
      <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <p className="text-slate-400 font-mono">Loading investigation workspace...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Breadcrumb & Header */}
        <div className="space-y-3">
          <Link
            href="/"
            className="inline-flex items-center text-xs font-mono text-slate-400 hover:text-sky-400 transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5 mr-1" />
            Back to Command Center
          </Link>

          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 glass-panel p-6 rounded-2xl border border-slate-800">
            <div className="space-y-1.5 flex-1">
              <div className="flex items-center space-x-3">
                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-medium ${
                    investigation.mode === "incident"
                      ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                      : "bg-sky-500/10 text-sky-400 border border-sky-500/30"
                  }`}
                >
                  {investigation.mode.toUpperCase()}
                </span>
                <span
                  className={`px-2.5 py-0.5 rounded text-xs font-mono ${
                    investigation.status === "completed"
                      ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                      : investigation.status === "awaiting_approval"
                      ? "bg-amber-950 text-amber-300 border border-amber-800 animate-pulse"
                      : "bg-sky-950 text-sky-300 border border-sky-800"
                  }`}
                >
                  {investigation.status.toUpperCase()}
                </span>
                <span className="text-xs font-mono text-slate-400">ID: {investigation.id}</span>
              </div>
              <h1 className="text-xl font-bold text-white leading-snug">{investigation.objective}</h1>
            </div>

            {investigation.status === "awaiting_approval" && (
              <button
                onClick={() => setApprovalModal(true)}
                className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-sm shadow-lg shadow-amber-500/20 flex items-center space-x-2"
              >
                <ShieldAlert className="w-4 h-4" />
                <span>Review Consequential Action</span>
              </button>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800 space-x-2">
          {[
            { key: "stream", label: "Live Telemetry & Tasks", icon: Activity },
            { key: "hypotheses", label: `Hypotheses (${hypotheses.length})`, icon: Sparkles },
            { key: "evidence", label: `Evidence Matrix (${evidence.length})`, icon: Database },
            { key: "remediation", label: "Proposed Remediation", icon: Code },
            { key: "report", label: "Audit Report", icon: FileText },
          ].map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key as any)}
              className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-mono border-b-2 transition-colors ${
                activeTab === key
                  ? "border-sky-400 text-sky-300 bg-sky-950/20 font-semibold"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/40"
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </button>
          ))}
        </div>

        {/* Tab 1: Live Event Stream & Specialist Tasks */}
        {activeTab === "stream" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Task Decomposition DAG */}
            <div className="lg:col-span-1 glass-panel p-5 rounded-2xl border border-slate-800 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Cpu className="w-4 h-4 text-sky-400" />
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                    Specialist Agents
                  </h3>
                </div>
                <span className="text-xs font-mono text-slate-400">{tasks.length} tasks</span>
              </div>

              <div className="space-y-3">
                {tasks.length === 0 ? (
                  <p className="text-xs text-slate-400 font-mono">Decomposing investigation tasks...</p>
                ) : (
                  tasks.map((t) => (
                    <div
                      key={t.id}
                      className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-1.5"
                    >
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span className="font-semibold text-sky-400">{t.assigned_agent}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] ${
                            t.status === "completed"
                              ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                              : "bg-sky-950 text-sky-300 border border-sky-800"
                          }`}
                        >
                          {t.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-300">{t.description}</p>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Live SSE Stream Console */}
            <div className="lg:col-span-2 glass-panel p-5 rounded-2xl border border-slate-800 space-y-3 flex flex-col h-[520px]">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <Terminal className="w-4 h-4 text-emerald-400" />
                  <h3 className="text-sm font-bold text-white uppercase tracking-wider font-mono">
                    Live Telemetry Stream
                  </h3>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                  <span className="text-xs font-mono text-emerald-400">STREAMING</span>
                </div>
              </div>

              <div
                ref={eventStreamRef}
                className="flex-1 overflow-y-auto font-mono text-xs p-4 bg-black/70 rounded-xl space-y-2.5 border border-slate-900"
              >
                {events.length === 0 ? (
                  <p className="text-slate-400">Connecting to investigation audit stream...</p>
                ) : (
                  events.map((e, idx) => (
                    <div key={idx} className="space-y-0.5 border-l-2 border-slate-800 pl-3 py-1">
                      <div className="flex items-center space-x-2 text-[11px]">
                        <span className="text-sky-400 font-semibold">{e.event_type}</span>
                        <span className="text-slate-400">{new Date(e.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <p className="text-slate-300 font-mono text-[11px] whitespace-pre-wrap">
                        {typeof e.payload === "string" ? e.payload : JSON.stringify(e.payload, null, 2)}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Interactive Hypothesis Tree */}
        {activeTab === "hypotheses" && (
          <div className="space-y-4">
            {hypotheses.length === 0 ? (
              <div className="glass-panel p-12 rounded-2xl text-center text-slate-400 font-mono">
                Agents are evaluating evidence to formulate hypotheses...
              </div>
            ) : (
              <div className="grid gap-4">
                {hypotheses.map((h, idx) => (
                  <div
                    key={h.id}
                    className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="flex items-center space-x-3">
                        <span className="text-base font-bold font-mono text-slate-400">#{idx + 1}</span>
                        <span
                          className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold ${
                            h.confidence_tier === "highly_supported"
                              ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                              : h.confidence_tier === "strong"
                              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
                              : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                          }`}
                        >
                          TIER: {h.confidence_tier.toUpperCase()}
                        </span>
                        <span className="text-xs font-mono text-slate-400">Status: {h.status}</span>
                      </div>

                      <div className="flex items-center space-x-3">
                        <span className="text-xs font-mono text-slate-400">Confidence:</span>
                        <div className="w-32 bg-slate-800 rounded-full h-2.5 overflow-hidden">
                          <div
                            className="bg-gradient-to-r from-sky-400 to-emerald-400 h-2.5 rounded-full"
                            style={{ width: `${(h.confidence * 100).toFixed(0)}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono font-bold text-white">
                          {(h.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    <p className="text-base font-semibold text-white leading-relaxed">{h.statement}</p>

                    {h.critique_notes && (
                      <div className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80 text-xs font-mono text-slate-300 space-y-1">
                        <span className="font-semibold text-amber-400">CRITIC REVIEW:</span>
                        <p>{h.critique_notes}</p>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-4 text-xs font-mono text-slate-400">
                      <span>Supporting Evidence: {h.supporting_evidence_count}</span>
                      <span>Contradicting Evidence: {h.contradicting_evidence_count}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Evidence Matrix */}
        {activeTab === "evidence" && (
          <div className="space-y-4">
            {evidence.length === 0 ? (
              <div className="glass-panel p-12 rounded-2xl text-center text-slate-400 font-mono">
                No evidence items recorded yet.
              </div>
            ) : (
              <div className="grid gap-4">
                {evidence.map((e) => (
                  <div
                    key={e.id}
                    className="glass-panel p-5 rounded-2xl border border-slate-800 space-y-3"
                  >
                    <div className="flex items-center justify-between text-xs font-mono">
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800 uppercase">
                          {e.source_type}
                        </span>
                        <span className="text-slate-300 font-semibold">{e.source}</span>
                      </div>
                      <span className="text-slate-500">{new Date(e.timestamp).toLocaleTimeString()}</span>
                    </div>

                    {e.summary && (
                      <p className="text-sm text-slate-200 font-medium">{e.summary}</p>
                    )}

                    <pre className="p-3 rounded-xl bg-black/60 text-slate-300 text-xs font-mono overflow-x-auto max-h-48">
                      {e.content}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Remediation Proposal & Diff */}
        {activeTab === "remediation" && (
          <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center space-x-2">
                <Code className="w-5 h-5 text-sky-400" />
                <h3 className="text-lg font-bold text-white">Targeted Remediation Patch</h3>
              </div>
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                HUMAN APPROVAL REQUIRED BEFORE APPLYING
              </span>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-slate-400 uppercase">Unified Git Diff</label>
              <pre className="p-4 rounded-xl bg-slate-950 font-mono text-xs text-emerald-400 border border-slate-800 overflow-x-auto">
{`diff --git a/app/db/models.py b/app/db/models.py
--- a/app/db/models.py
+++ b/app/db/models.py
@@ -14,3 +14,3 @@ class InventoryItem(Base):
     id = Column(String(36), primary_key=True)
-    product_id = Column(String(64), nullable=False)
+    product_id = Column(String(64), nullable=False, index=True)
     warehouse_id = Column(String(64), nullable=False)`}
              </pre>
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t border-slate-800">
              <button
                onClick={() => setApprovalModal(true)}
                className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-sm shadow-lg shadow-emerald-900/40"
              >
                Approve & Execute Patch
              </button>
            </div>
          </div>
        )}

        {/* Tab 5: Final Audit Report */}
        {activeTab === "report" && (
          <div className="glass-panel p-8 rounded-2xl border border-slate-800 space-y-6">
            {report ? (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-white">Autonomous Investigation Report</h2>
                  <p className="text-xs font-mono text-slate-400 mt-1">Generated: {report.generated_at}</p>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                  <h4 className="text-xs font-mono text-sky-400 uppercase font-semibold">Executive Summary</h4>
                  <p className="text-sm text-slate-200">{report.executive_summary}</p>
                </div>

                {report.root_cause && (
                  <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-800/60 space-y-2">
                    <h4 className="text-xs font-mono text-rose-400 uppercase font-semibold">Established Root Cause</h4>
                    <p className="text-sm text-slate-200">{report.root_cause}</p>
                  </div>
                )}

                <div className="space-y-2">
                  <h4 className="text-xs font-mono text-slate-400 uppercase font-semibold">Recommendations</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-slate-300">
                    {(report.recommendations || []).map((r: string, idx: number) => (
                      <li key={idx}>{r}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-slate-400 font-mono">
                Investigation report will be generated upon completion.
              </div>
            )}
          </div>
        )}
      </main>

      {/* Human Approval Modal */}
      {approvalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="glass-panel-glow bg-slate-900 border border-amber-500/40 w-full max-w-lg rounded-2xl p-6 space-y-6">
            <div className="flex items-center space-x-3 text-amber-400 border-b border-slate-800 pb-4">
              <ShieldAlert className="w-6 h-6" />
              <h3 className="text-lg font-bold text-white">Human Consequential Action Gate</h3>
            </div>

            <p className="text-sm text-slate-300">
              The autonomous agent is requesting permission to apply the code patch and trigger verification tests in an isolated branch.
            </p>

            <div>
              <label className="block text-xs font-mono text-slate-400 uppercase mb-1">
                Audit Log Notes / Operator Comments
              </label>
              <textarea
                rows={3}
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                placeholder="Optional review rationale or sign-off notes..."
                className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100 focus:outline-none focus:border-amber-400"
              />
            </div>

            {actionError && (
              <div className="rounded-lg border border-rose-500/40 bg-rose-950/40 p-3 text-xs text-rose-300">
                {actionError}
              </div>
            )}

            <div className="flex items-center justify-between pt-4 border-t border-slate-800">
              <button
                type="button"
                onClick={() => handleApproval("reject")}
                disabled={submittingAction}
                className="px-4 py-2.5 rounded-xl bg-rose-950 text-rose-300 hover:bg-rose-900 font-semibold text-xs border border-rose-800"
              >
                {submittingAction ? "Processing..." : "Reject Action"}
              </button>

              <button
                type="button"
                onClick={() => handleApproval("approve")}
                disabled={submittingAction}
                className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-900/50"
              >
                {submittingAction ? "Processing..." : "Sign-off & Approve"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
