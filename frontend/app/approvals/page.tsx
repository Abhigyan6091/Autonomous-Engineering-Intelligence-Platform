"use client";

import { apiUrl } from "@/lib/api";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { 
  ShieldAlert, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  ArrowRight, 
  Code,
  FileCheck2,
  AlertTriangle
} from "lucide-react";

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedApproval, setSelectedApproval] = useState<any>(null);
  const [notes, setNotes] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    fetchApprovals();
  }, []);

  async function fetchApprovals() {
    try {
      const res = await fetch(apiUrl("/api/v1/approvals"));
      if (res.ok) {
        setApprovals(await res.json());
        setError(null);
      } else {
        setError(`Could not load approvals (HTTP ${res.status}).`);
      }
    } catch (err) {
      setError(
        `Cannot reach the backend. ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleAction(decision: "approve" | "reject") {
    if (!selectedApproval) return;
    setSubmitting(true);
    try {
      // Without checking the response a 404/409 closed the modal as if it worked.
      const res = await fetch(
        apiUrl(`/api/v1/approvals/${selectedApproval.id}/${decision}`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ notes }),
        }
      );

      if (!res.ok) {
        const detail = await res.text();
        setError(
          `Backend rejected the ${decision} (HTTP ${res.status}): ${detail.slice(0, 200)}`
        );
        return;
      }

      setError(null);
      setSelectedApproval(null);
      setNotes("");
      fetchApprovals();
    } catch (err) {
      setError(
        `Action failed: ${err instanceof Error ? err.message : String(err)}`
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {error && (
          <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 p-4 text-sm text-rose-300">
            {error}
          </div>
        )}

        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-2">
          <div className="flex items-center space-x-3">
            <ShieldAlert className="w-6 h-6 text-amber-400" />
            <h1 className="text-2xl font-bold text-white">Human Approval Gate & Governance</h1>
          </div>
          <p className="text-sm text-slate-400">
            Consequential actions (code patch application, test branch creation, pull request publication) require explicit operator review.
          </p>
        </div>

        {loading ? (
          <div className="text-center py-12 text-slate-400 font-mono">Loading approval queues...</div>
        ) : approvals.length === 0 ? (
          <div className="glass-panel p-12 rounded-2xl text-center space-y-3">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto" />
            <h3 className="text-lg font-bold text-white">All Approval Queues Clear</h3>
            <p className="text-sm text-slate-400">No autonomous actions currently awaiting human sign-off.</p>
          </div>
        ) : (
          <div className="grid gap-4">
            {approvals.map((app) => (
              <div
                key={app.id}
                className="glass-panel p-6 rounded-2xl border border-amber-500/30 space-y-4"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-3">
                    <span className="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      RISK: {app.risk_level.toUpperCase()}
                    </span>
                    <span className="text-xs font-mono text-slate-400">Action: {app.action}</span>
                  </div>
                  <span className="text-xs font-mono text-slate-500">
                    Requested: {new Date(app.requested_at).toLocaleTimeString()}
                  </span>
                </div>

                <p className="text-base font-semibold text-white">{app.description}</p>

                {app.payload?.patch && (
                  <pre className="p-3 rounded-xl bg-slate-950 text-emerald-400 text-xs font-mono border border-slate-800 overflow-x-auto max-h-36">
                    {app.payload.patch}
                  </pre>
                )}

                <div className="flex items-center justify-between pt-2">
                  <Link
                    href={`/investigations/${app.investigation_id}`}
                    className="text-xs font-mono text-sky-400 hover:text-sky-300"
                  >
                    View Associated Investigation →
                  </Link>

                  <button
                    onClick={() => setSelectedApproval(app)}
                    className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs"
                  >
                    Review & Decide
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Decision Modal */}
      {selectedApproval && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="glass-panel-glow bg-slate-900 border border-amber-500/40 w-full max-w-lg rounded-2xl p-6 space-y-6">
            <h3 className="text-lg font-bold text-white">Review Action #{selectedApproval.id.slice(0, 8)}</h3>
            <p className="text-xs text-slate-300">{selectedApproval.description}</p>

            <div>
              <label className="block text-xs font-mono text-slate-400 uppercase mb-1">Operator Notes</label>
              <textarea
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Rationale for approval / rejection..."
                className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100"
              />
            </div>

            <div className="flex items-center justify-between pt-4 border-t border-slate-800">
              <button
                onClick={() => handleAction("reject")}
                disabled={submitting}
                className="px-4 py-2.5 rounded-xl bg-rose-950 text-rose-300 font-semibold text-xs border border-rose-800"
              >
                Reject
              </button>
              <button
                onClick={() => handleAction("approve")}
                disabled={submitting}
                className="px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-lg shadow-emerald-900/50"
              >
                {submitting ? "Applying..." : "Approve & Execute"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
