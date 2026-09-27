"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api, demoAuth, humanize } from "@/lib/api";
import { roles, type Role } from "@/lib/types";
import { Icon } from "./icon";

const Session = createContext<{role: Role}>({role: "analyst"});
export const useSession = () => useContext(Session);
export function Shell({children}: {children: React.ReactNode}) {
  const [role, setRole] = useState<Role>("analyst");
  const [status, setStatus] = useState<"checking" | "ready" | "unavailable">("checking");
  const pathname = usePathname();
  useEffect(() => {
    const controller = new AbortController();
    api("/api/ready", role, {signal: controller.signal}).then(() => setStatus("ready")).catch(() => { if (!controller.signal.aborted) setStatus("unavailable"); });
    return () => controller.abort();
  }, [role]);
  return <Session value={{role}}><div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="Knowledge Copilot home"><span className="brand-mark"><span /><span /><span /></span><span>Knowledge<span className="brand-sub">COPILOT</span></span></Link>
      <div className="workspace-label">ENTERPRISE WORKSPACE</div>
      <nav className="nav" aria-label="Main navigation">
        <Link className={pathname === "/" ? "nav-item active" : "nav-item"} href="/"><Icon name="chat" />Knowledge assistant<Icon name="chevron" size={14} /></Link>
        <Link className={pathname.startsWith("/evaluations") ? "nav-item active" : "nav-item"} href="/evaluations"><Icon name="chart" />Evaluations<Icon name="chevron" size={14} /></Link>
      </nav>
      <div className="sidebar-card"><span className="mini-icon"><Icon name="shield" /></span><strong>Evidence comes first.</strong><p>Answers are grounded in the knowledge available to your role.</p><div className="sidebar-rule" /><span>Role-aware retrieval</span><span>Traceable citations</span><span>Explicit uncertainty</span></div>
      <div className="sidebar-footer"><span className={`status-dot ${status}`} /><span>{status === "ready" ? "Knowledge service ready" : status === "checking" ? "Connecting to service" : "Service unavailable"}</span><small>Readiness checked on session change</small></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{pathname.startsWith("/evaluations") ? "Evaluations" : "Knowledge assistant"}</strong></div><div className="session-controls"><span className="badge demo">SYNTHETIC DEMO</span>{demoAuth ? <label className="role-selector"><span>View as</span><select aria-label="Demonstration user role" value={role} onChange={(e) => setRole(e.target.value as Role)}>{roles.map((r) => <option key={r} value={r}>{humanize(r)}</option>)}</select></label> : <span className="badge">Authenticated session</span>}<span className="avatar" aria-hidden="true">{role === "risk_manager" ? "RM" : role.slice(0,2).toUpperCase()}</span></div></header>
      <main id="main-content" key={role}>{children}</main>
      <footer className="page-footer"><Icon name="shield" size={14} /><span>All documents and organizations represented in the demo dataset are synthetic and are not official policies of any financial institution.</span></footer>
    </div>
  </div></Session>;
}
