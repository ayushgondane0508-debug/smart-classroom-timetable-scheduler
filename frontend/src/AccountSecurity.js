import { useState } from "react";
import { KeyRound } from "lucide-react";
import { api, errorText } from "@/client";

export default function AccountSecurity({ dark = false }) {
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm: "" });
  const [state, setState] = useState({ error: "", done: false, busy: false });
  const submit = async event => {
    event.preventDefault();
    if (form.new_password !== form.confirm) { setState({ error: "New passwords do not match.", done: false, busy: false }); return; }
    setState({ error: "", done: false, busy: true });
    try { await api.post("/auth/change-password", { current_password: form.current_password, new_password: form.new_password }); setForm({ current_password: "", new_password: "", confirm: "" }); setState({ error: "", done: true, busy: false }); }
    catch (err) { setState({ error: errorText(err), done: false, busy: false }); }
  };
  return <form className={`panel security-panel ${dark ? "dark" : ""}`} onSubmit={submit} data-testid="change-password-form">
    <div className="panel-heading"><div><p className="scheduler-kicker">Account security</p><h2>Change password</h2></div><KeyRound size={18} className="teal-icon"/></div>
    <div className="form-grid three">
      <label>Current password<input type="password" required value={form.current_password} onChange={e => setForm({ ...form, current_password: e.target.value })} data-testid="current-password-input"/></label>
      <label>New password<input type="password" required minLength={8} value={form.new_password} onChange={e => setForm({ ...form, new_password: e.target.value })} data-testid="new-password-input"/></label>
      <label>Confirm new password<input type="password" required minLength={8} value={form.confirm} onChange={e => setForm({ ...form, confirm: e.target.value })} data-testid="confirm-password-input"/></label>
    </div>
    {state.error && <div className="scheduler-error" data-testid="change-password-error">{state.error}</div>}
    {state.done && <div className="scheduler-success" data-testid="change-password-success">Password updated. Use it the next time you sign in.</div>}
    <button className="primary-button" disabled={state.busy} data-testid="change-password-submit">{state.busy ? "Updating…" : "Update password"}</button>
  </form>;
}
