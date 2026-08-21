"use client";

import { apiUrl } from "@/lib/api";

import React, { useState } from "react";
import Link from "next/link";
import { Navbar } from "@/components/Navbar";
import { 
  ShieldCheck, 
  Search, 
  FileCode, 
  Lock, 
  Layers, 
  ArrowRight,
  Sparkles,
  CheckCircle2,
  AlertTriangle
} from "lucide-react";

export default function AuditSuitePage() {
  const [targetRepo, setTargetRepo] = useState<string>("demo-repo-001");
  const [selectedAuditTypes, setSelectedAuditTypes] = useState<string[]>([
    "security_vulnerabilities",
    "dead_code",
    "test_coverage_gaps",
    "architecture_compliance"
  ]);
  const [submitting, setSubmitting] = useState<boolean>(false);

  function toggleAuditType(key: string) {
    if (selectedAuditTypes.includes(key)) {
      setSelectedAuditTypes(selectedAuditTypes.filter(k => k !== key));
    } else {
      setSelectedAuditTypes([...selectedAuditTypes, key]);
    }
  }

  async function handleLaunchAudit() {
    setSubmitting(true);
    try {
      const res = await fetch(apiUrl("/api/v1/investigations"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: "demo-project-001",
          objective: `Comprehensive System Audit of repository '${targetRepo}'. Audit scopes: ${selectedAuditTypes.join(", ")}. Identify security flaws, unindexed queries, anti-patterns, and coverage deficiencies.`,
          mode: "audit",
          priority: "high",
          metadata: {
            workspace_path: "./demo_repo/checkout-api",
            audit_types: selectedAuditTypes,
          }
        })
      });

      if (res.ok) {
        const data = await res.json();
        window.location.href = `/investigations/${data.id}`;
      }
    } catch (err) {
      alert("Failed to launch audit: " + err);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#070b14] text-slate-100 flex flex-col font-sans">
      <Navbar />

      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div className="glass-panel-glow p-8 rounded-2xl border border-sky-500/30 space-y-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/30">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Repository & System Audit Suite</h1>
              <p className="text-sm text-slate-400">
                Autonomous static analysis, dependency vulnerability scanning, AST inspection, and architectural verification.
              </p>
            </div>
          </div>
        </div>

        <div className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-6">
          <h3 className="text-sm font-mono font-bold text-white uppercase tracking-wider">
            Audit Configuration
          </h3>

          <div className="space-y-2">
            <label className="text-xs font-mono text-slate-400 uppercase">Target Repository</label>
            <select
              value={targetRepo}
              onChange={(e) => setTargetRepo(e.target.value)}
              className="w-full rounded-xl bg-slate-950 border border-slate-700 p-3 text-sm text-slate-100 font-mono"
            >
              <option value="demo-repo-001">checkout-api (Python / FastAPI / SQLAlchemy)</option>
              <option value="billing-service">billing-service (TypeScript / Node.js)</option>
              <option value="auth-gateway">auth-gateway (Go / gRPC)</option>
            </select>
          </div>

          <div className="space-y-3">
            <label className="text-xs font-mono text-slate-400 uppercase">Audit Scopes</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {[
                { id: "security_vulnerabilities", label: "Security & Vulnerability Analysis", desc: "SQL injection, bare exceptions, unsafe deserialization" },
                { id: "dead_code", label: "Dead Code & Anti-Patterns", desc: "Unused imports, unreachable blocks, duplicate handlers" },
                { id: "test_coverage_gaps", label: "Test Coverage & Critical Paths", desc: "Missing integration tests on state-modifying endpoints" },
                { id: "architecture_compliance", label: "Architectural & SLA Review", desc: "Missing database indexes, unbounded memory structures" }
              ].map(({ id, label, desc }) => (
                <div
                  key={id}
                  onClick={() => toggleAuditType(id)}
                  className={`p-4 rounded-xl border cursor-pointer transition-all ${
                    selectedAuditTypes.includes(id)
                      ? "bg-sky-950/40 border-sky-500/50 shadow-md shadow-sky-950"
                      : "bg-slate-950/40 border-slate-800 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={selectedAuditTypes.includes(id)}
                      onChange={() => {}}
                      className="rounded border-slate-700 text-sky-500"
                    />
                    <span className="text-sm font-semibold text-white">{label}</span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 pl-6">{desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 flex justify-end">
            <button
              onClick={handleLaunchAudit}
              disabled={submitting || selectedAuditTypes.length === 0}
              className="px-6 py-3 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-sm shadow-lg shadow-sky-900/40 flex items-center space-x-2 disabled:opacity-50"
            >
              <Sparkles className="w-4 h-4" />
              <span>{submitting ? "Dispatching Audit Agents..." : "Start System Audit"}</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
