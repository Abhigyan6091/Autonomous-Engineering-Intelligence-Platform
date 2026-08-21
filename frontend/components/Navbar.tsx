"use client";

import { apiUrl } from "@/lib/api";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  ShieldAlert, 
  Activity, 
  Search, 
  GitPullRequest, 
  FileCheck2, 
  CheckCircle2, 
  AlertTriangle,
  Server
} from "lucide-react";

export function Navbar() {
  const pathname = usePathname();
  const [health, setHealth] = useState<string>("checking");
  const [pendingApprovals, setPendingApprovals] = useState<number>(0);

  useEffect(() => {
    async function checkStatus() {
      try {
        const res = await fetch(apiUrl("/health"));
        if (res.ok) {
          const data = await res.json();
          setHealth(data.status || "healthy");
        } else {
          setHealth("degraded");
        }
      } catch {
        setHealth("offline");
      }

      try {
        const appRes = await fetch(apiUrl("/api/v1/approvals"));
        if (appRes.ok) {
          const apps = await appRes.json();
          setPendingApprovals(apps.length);
        }
      } catch {
        // ignore
      }
    }

    checkStatus();
    const interval = setInterval(checkStatus, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-6">
          <Link href="/" className="flex items-center space-x-3 group">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20 group-hover:scale-105 transition-transform">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-300">
                AEIP
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs font-mono px-2 py-0.5 rounded bg-sky-950/70 text-sky-400 border border-sky-800/60">
                AUTONOMOUS PLATFORM
              </span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center space-x-1">
            <Link
              href="/"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/" 
                  ? "bg-slate-800 text-sky-400" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              Command Center
            </Link>
            <Link
              href="/audit"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/audit" 
                  ? "bg-slate-800 text-sky-400" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              System Audits
            </Link>
            <Link
              href="/repositories"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                pathname === "/repositories"
                  ? "bg-slate-800 text-sky-400"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              Repositories
            </Link>
            <Link
              href="/approvals"
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors relative flex items-center space-x-1.5 ${
                pathname === "/approvals" 
                  ? "bg-slate-800 text-sky-400" 
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <span>Approvals</span>
              {pendingApprovals > 0 && (
                <span className="h-5 w-5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 text-xs flex items-center justify-center font-mono">
                  {pendingApprovals}
                </span>
              )}
            </Link>
          </nav>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-900/90 border border-slate-800 text-xs font-mono">
            <span
              className={`h-2 w-2 rounded-full ${
                health === "healthy"
                  ? "bg-emerald-400 shadow-sm shadow-emerald-400"
                  : health === "degraded"
                  ? "bg-amber-400"
                  : "bg-rose-500"
              }`}
            />
            <span className="text-slate-400">Control Plane:</span>
            <span
              className={
                health === "healthy"
                  ? "text-emerald-400 font-semibold"
                  : health === "degraded"
                  ? "text-amber-400"
                  : "text-rose-400"
              }
            >
              {health.toUpperCase()}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
}
