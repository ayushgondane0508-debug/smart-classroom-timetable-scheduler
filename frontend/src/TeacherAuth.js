import { useEffect, useState } from "react";
import { KeyRound, LogOut } from "lucide-react";
import "@/scheduler.css";
import { api, errorText } from "@/client";
import AccountSecurity from "@/AccountSecurity";
import { ScheduleBoard } from "@/TeacherPortal";

function TeacherLogin({ onLogin }) {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async event => {
    event.preventDefault(); setBusy(true); setError("");
    try { const { data } = await api.post("/auth/login", form); if (data.role !== "teacher") { await api.post("/auth/logout"); setError("This is an admin account. Use the admin workspace at /scheduler."); return; } onLogin(data); }
    catch (err) { setError(errorText(err)); } finally { setBusy(false); }
  };
  return <div className="scheduler-login" data-testid="teacher-login-page"><div className="login-glow teal"/><div className="login-card"><div className="scheduler-mark">SC</div><p className="scheduler-kicker">Faculty sign in</p><h1>Your week, one tap away</h1><p className="login-copy">Sign in with the email and password your admin created for you to see your personal schedule.</p><form onSubmit={submit} data-testid="teacher-login-form"><label>Email<input type="email" required value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} data-testid="teacher-email-input"/></label><label>Password<input type="password" required value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} data-testid="teacher-password-input"/></label>{error && <div className="scheduler-error" data-testid="teacher-login-error">{error}</div>}<button className="primary-button full-button" disabled={busy} data-testid="teacher-login-submit">{busy ? "Signing in…" : "Sign in"}</button></form><p className="login-hint">Admin? <a href="/scheduler" data-testid="teacher-login-admin-link">Open the admin workspace</a></p><a className="back-landing" href="/">← Back to product overview</a></div></div>;
}

export function TeacherWorkspace({ user, onLogout }) {
  const [state, setState] = useState({ loading: true, data: null, error: "" });
  const [security, setSecurity] = useState(false);
  useEffect(() => { api.get("/me/schedule").then(res => setState({ loading: false, data: res.data, error: "" })).catch(err => setState({ loading: false, data: null, error: errorText(err) })); }, []);
  if (state.loading) return <div className="scheduler-loading"><div className="scheduler-spinner"/> Loading your schedule…</div>;
  return <div className="teacher-portal" data-testid="teacher-workspace">
    <div className="portal-glow"/>
    <header className="portal-header"><div className="portal-brand"><span className="scheduler-mark small">SC</span><span>Smart<strong>Classroom</strong></span></div><div className="portal-actions"><button className={`ghost-button ${security ? "active" : ""}`} onClick={() => setSecurity(!security)} data-testid="teacher-security-toggle"><KeyRound size={14}/> Password</button><button className="ghost-button" onClick={onLogout} data-testid="teacher-logout-button"><LogOut size={14}/> Log out</button></div></header>
    {security && <div className="portal-security"><AccountSecurity dark/></div>}
    {state.error ? <div className="scheduler-error portal-inline-error" data-testid="teacher-workspace-error">{state.error}</div> : <ScheduleBoard data={state.data} kicker="Signed in as faculty" testId="workspace"/>}
    <footer className="portal-footer">Signed in as {user.email} · your schedule updates whenever the admin publishes a new timetable</footer>
  </div>;
}

export default function TeacherAuth() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);
  useEffect(() => { api.get("/auth/me").then(res => setUser(res.data)).catch(() => setUser(false)).finally(() => setChecking(false)); }, []);
  const logout = async () => { await api.post("/auth/logout"); setUser(false); };
  if (checking) return <div className="scheduler-loading"><div className="scheduler-spinner"/> Checking session…</div>;
  if (user && user.role === "teacher") return <TeacherWorkspace user={user} onLogout={logout}/>;
  if (user && user.role === "admin") return <div className="scheduler-loading portal-error" data-testid="teacher-login-admin-notice"><p>You are signed in as the administrator.</p><a href="/scheduler">Open the admin workspace</a><button className="ghost-button" onClick={logout} data-testid="teacher-login-switch-account">Sign out to switch account</button></div>;
  return <TeacherLogin onLogin={setUser}/>;
}
