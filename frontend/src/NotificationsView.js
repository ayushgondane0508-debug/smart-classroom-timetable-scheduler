import { useEffect, useState } from "react";
import { Mail, MailCheck, MailWarning, Send } from "lucide-react";
import { api, errorText } from "@/client";

const statusLabel = { sent: "Delivered", skipped: "Logged (no API key)", failed: "Failed" };

export default function NotificationsView({ timetable, onNotify }) {
  const [state, setState] = useState({ configured: false, sender: "", items: [] });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => { try { const { data } = await api.get("/notifications"); setState(data); } catch (err) { setError(errorText(err)); } };
  useEffect(() => { load(); }, []);
  const send = async () => { setBusy(true); try { await onNotify(); await load(); } finally { setBusy(false); } };
  const counts = state.items.reduce((acc, item) => ({ ...acc, [item.status]: (acc[item.status] || 0) + 1 }), {});
  return <div data-testid="notifications-page">
    <div className="page-intro"><div><p className="scheduler-kicker">Email schedule alerts</p><h1>Teacher notifications</h1><p>Every time a timetable is generated or set active, teachers with an email address receive their updated week.</p></div><button className="primary-button" onClick={send} disabled={!timetable || busy} data-testid="send-alerts-button"><Send size={15}/> {busy ? "Sending…" : "Send alerts for active timetable"}</button></div>
    <div className={`provider-banner ${state.configured ? "ok" : "warn"}`} data-testid="email-provider-status">{state.configured ? <MailCheck size={17}/> : <MailWarning size={17}/>}<div><strong>{state.configured ? "Resend connected" : "Resend not configured — alerts are logged only"}</strong><small>{state.configured ? `Emails are sent from ${state.sender}.` : "Add RESEND_API_KEY in backend/.env to deliver real emails. Alerts still appear here so you can verify who would be notified."}</small></div></div>
    <div className="stat-grid analytics-top three"><div className="stat-card"><div className="stat-icon"><Mail size={17}/></div><p>Total alerts</p><strong data-testid="alerts-total">{state.items.length}</strong></div><div className="stat-card"><div className="stat-icon teal"><MailCheck size={17}/></div><p>Delivered</p><strong data-testid="alerts-sent">{counts.sent || 0}</strong></div><div className="stat-card"><div className="stat-icon amber"><MailWarning size={17}/></div><p>Logged / failed</p><strong data-testid="alerts-pending">{(counts.skipped || 0) + (counts.failed || 0)}</strong></div></div>
    {error && <div className="scheduler-error">{error}</div>}
    <div className="panel table-panel">{state.items.length ? <div className="data-table-wrap"><table className="data-table" data-testid="notifications-table"><thead><tr><th>Teacher</th><th>Timetable</th><th>Sessions</th><th>Status</th><th>When</th></tr></thead><tbody>{state.items.map(item => <tr key={item.id} data-testid={`notification-row-${item.id}`}><td><div className="table-primary"><span className="table-avatar"><Mail size={14}/></span><div><strong>{item.teacher_name}</strong><small>{item.email}</small></div></div></td><td>{item.timetable_name}</td><td>{item.sessions}</td><td><span className={`status-pill ${item.status}`} title={item.error || ""}>{statusLabel[item.status] || item.status}</span></td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div> : <div className="empty-state" data-testid="notifications-empty"><Mail size={28}/><h3>No alerts yet</h3><p>Add email addresses to teachers, then generate or activate a timetable to notify them.</p></div>}</div>
  </div>;
}
